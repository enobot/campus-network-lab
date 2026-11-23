"""Tests for the checking tools themselves.

If the parser or the ACL evaluator were wrong, every design check built on
them would be meaningless, so they get their own known-answer tests first.
"""

import pytest

from labcheck.acl import Packet, evaluate, parse_acl, parse_entry
from labcheck.iosconfig import expand_interface_range, expand_port_list, normalize_interface, parse_config


class TestInterfaceNames:
    def test_abbreviations_are_normalised(self):
        assert normalize_interface("gi0/1") == "GigabitEthernet0/1"
        assert normalize_interface("Fa0/24") == "FastEthernet0/24"
        assert normalize_interface("GigabitEthernet0/0/0.20") == "GigabitEthernet0/0/0.20"
        assert normalize_interface("vlan99") == "Vlan99"

    def test_interface_range_with_several_parts(self):
        assert expand_interface_range("FastEthernet0/3 - 5, GigabitEthernet0/2") == [
            "FastEthernet0/3",
            "FastEthernet0/4",
            "FastEthernet0/5",
            "GigabitEthernet0/2",
        ]

    def test_plan_port_notation(self):
        assert expand_port_list("FastEthernet0/1-2,GigabitEthernet0/1") == [
            "FastEthernet0/1",
            "FastEthernet0/2",
            "GigabitEthernet0/1",
        ]

    def test_backwards_range_is_rejected(self):
        with pytest.raises(ValueError):
            expand_interface_range("FastEthernet0/9 - 3")


class TestConfigParser:
    SAMPLE = """\
enable
configure terminal
hostname TEST-SW
! a comment
vlan 10
 name FACULTY
interface range FastEthernet0/1 - 2
 switchport access vlan 10
interface FastEthernet0/2
 description second block adds to the same port
ip access-list extended WEB
 remark only web
 permit tcp any any eq 80
access-list 10 permit 10.0.0.0 0.0.0.255
line vty 0 15
 transport input ssh
end
write memory
"""

    def test_parses_blocks(self):
        config = parse_config(self.SAMPLE)
        assert config.hostname == "TEST-SW"
        assert config.vlans == {10: "FACULTY"}
        assert config.interface("Fa0/1") == ["switchport access vlan 10"]
        assert config.interface("Fa0/2") == [
            "switchport access vlan 10",
            "description second block adds to the same port",
        ]
        assert config.named_acls["WEB"] == ("extended", ["remark only web", "permit tcp any any eq 80"])
        assert config.numbered_acls["10"] == ["permit 10.0.0.0 0.0.0.255"]
        assert config.lines["vty 0 15"] == ["transport input ssh"]

    def test_exec_commands_are_not_configuration(self):
        config = parse_config(self.SAMPLE)
        assert "enable" not in config.global_lines
        assert "write memory" not in config.global_lines

    def test_indented_line_outside_a_block_is_an_error(self):
        with pytest.raises(ValueError):
            parse_config(" switchport mode access\n")


class TestAclEvaluation:
    def test_first_match_wins(self):
        acl = parse_acl(["deny tcp any any eq 22", "permit ip any any"], "extended")
        assert evaluate(acl, Packet("tcp", "10.0.0.1", "10.0.0.2", dport=22))[0] == "deny"
        assert evaluate(acl, Packet("tcp", "10.0.0.1", "10.0.0.2", dport=80))[0] == "permit"

    def test_implicit_deny_at_the_end(self):
        acl = parse_acl(["permit tcp any any eq 80"], "extended")
        action, entry = evaluate(acl, Packet("udp", "10.0.0.1", "10.0.0.2", dport=53))
        assert action == "deny"
        assert entry is None

    def test_wildcard_masks(self):
        entry = parse_entry("permit ip 10.10.20.0 0.0.0.255 any", "extended")
        assert entry.matches(Packet("icmp", "10.10.20.200", "8.8.8.8", icmp="echo"))
        assert not entry.matches(Packet("icmp", "10.10.21.1", "8.8.8.8", icmp="echo"))

    def test_host_keyword(self):
        entry = parse_entry("permit tcp any host 10.10.30.10 eq 443", "extended")
        assert entry.matches(Packet("tcp", "1.2.3.4", "10.10.30.10", dport=443))
        assert not entry.matches(Packet("tcp", "1.2.3.4", "10.10.30.11", dport=443))

    def test_source_port_and_destination_port(self):
        entry = parse_entry("permit udp any eq 68 any eq 67", "extended")
        assert entry.matches(Packet("udp", "0.0.0.0", "255.255.255.255", sport=68, dport=67))
        assert not entry.matches(Packet("udp", "0.0.0.0", "255.255.255.255", sport=67, dport=68))

    def test_icmp_type_is_respected(self):
        entry = parse_entry("permit icmp any any echo-reply", "extended")
        assert entry.matches(Packet("icmp", "1.1.1.1", "2.2.2.2", icmp="echo-reply"))
        assert not entry.matches(Packet("icmp", "1.1.1.1", "2.2.2.2", icmp="echo"))

    def test_ip_matches_every_protocol(self):
        entry = parse_entry("deny ip any any", "extended")
        assert entry.matches(Packet("udp", "1.1.1.1", "2.2.2.2", dport=53))
        assert entry.matches(Packet("icmp", "1.1.1.1", "2.2.2.2", icmp="echo"))

    def test_standard_acl_checks_source_only(self):
        acl = parse_acl(["permit 10.10.99.0 0.0.0.255"], "standard")
        assert evaluate(acl, Packet("tcp", "10.10.99.50", "10.10.20.1", dport=22))[0] == "permit"
        assert evaluate(acl, Packet("tcp", "10.10.10.21", "10.10.99.2", dport=22))[0] == "deny"

    def test_named_ports_are_understood(self):
        entry = parse_entry("permit tcp any any eq www", "extended")
        assert entry.dport == 80

    def test_remarks_are_skipped(self):
        assert parse_entry("remark anything at all", "extended") is None

    def test_unsupported_syntax_fails_loudly(self):
        with pytest.raises(ValueError):
            parse_entry("permit tcp any any range 1000 2000", "extended")
        with pytest.raises(ValueError):
            parse_entry("permit tcp any any eq 80 log extra", "extended")
