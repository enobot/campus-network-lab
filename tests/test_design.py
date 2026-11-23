"""Static design checks: do the config files in configs/ match the plan in
design/lab-plan.json and follow the lab's own rules?

These read the text of the configs. They do NOT run them on Cisco IOS or
in Packet Tracer; see docs/VERIFICATION.md for the hands-on tests.
"""

import ipaddress
import itertools

import pytest

from labcheck.acl import ANY
from labcheck.iosconfig import expand_port_list
from labcheck.network import acl_entries, router_subinterfaces

PORTS_2960_24TT = [f"FastEthernet0/{n}" for n in range(1, 25)] + ["GigabitEthernet0/1", "GigabitEthernet0/2"]


def routed_vlans(plan):
    return [v for v in plan["vlans"] if v["subnet"]]


def all_static_addresses(plan):
    """Every address that is set by hand: gateways, switch SVIs, static hosts."""
    addresses = [(f"gateway VLAN {v['id']}", v["gateway"]) for v in routed_vlans(plan)]
    addresses += [
        (f"{d['name']} management", d["management_ip"]) for d in plan["devices"] if d["name"] != "R1"
    ]
    addresses += [(h["name"], h["ip"]) for h in plan["hosts"] if h["addressing"] == "static"]
    return addresses


def lines_of(config, interface):
    return config.interface(interface)


# ── Addressing ───────────────────────────────────────────────────────────


def test_subnets_do_not_overlap(plan):
    networks = [ipaddress.IPv4Network(v["subnet"]) for v in routed_vlans(plan)]
    for a, b in itertools.combinations(networks, 2):
        assert not a.overlaps(b), f"{a} overlaps {b}"


def test_subnets_are_private_rfc1918(plan):
    for vlan in routed_vlans(plan):
        assert ipaddress.IPv4Network(vlan["subnet"]).is_private, vlan["subnet"]


def test_gateway_is_first_usable_address(plan):
    for vlan in routed_vlans(plan):
        network = ipaddress.IPv4Network(vlan["subnet"])
        assert vlan["gateway"] == str(next(network.hosts())), f"VLAN {vlan['id']}"


def test_static_addresses_are_unique(plan):
    seen = {}
    for owner, address in all_static_addresses(plan):
        assert address not in seen, f"{address} used by both {seen[address]} and {owner}"
        seen[address] = owner


def test_static_hosts_sit_inside_their_vlan(plan):
    subnet_of = {v["id"]: ipaddress.IPv4Network(v["subnet"]) for v in routed_vlans(plan)}
    for host in plan["hosts"]:
        if host["addressing"] == "static":
            assert ipaddress.IPv4Address(host["ip"]) in subnet_of[host["vlan"]], host["name"]


def test_management_addresses_are_in_the_management_vlan(plan):
    mgmt = next(ipaddress.IPv4Network(v["subnet"]) for v in plan["vlans"] if v["id"] == plan["management_vlan"])
    for device in plan["devices"]:
        assert ipaddress.IPv4Address(device["management_ip"]) in mgmt, device["name"]


# ── VLANs and switching ──────────────────────────────────────────────────


def test_every_switch_defines_the_same_vlans(plan, switches):
    expected = {v["id"]: v["name"] for v in plan["vlans"]}
    for name, config in switches.items():
        assert config.vlans == expected, name


def test_switches_use_vtp_transparent_and_rapid_pvst(switches):
    for name, config in switches.items():
        assert config.has_global("vtp mode transparent"), name
        assert config.has_global("spanning-tree mode rapid-pvst"), name


def test_core_switch_is_spanning_tree_root_for_user_vlans(plan, switches):
    user_vlans = ",".join(str(v) for v in plan["trunk_allowed_vlans"])
    for device in plan["devices"]:
        if device["name"] not in switches:
            continue
        has_root = switches[device["name"]].has_global(f"spanning-tree vlan {user_vlans} root primary")
        assert has_root == bool(device.get("stp_root")), device["name"]


def test_every_switch_port_has_exactly_one_planned_role(plan):
    for switch, roles in plan["switch_port_roles"].items():
        assigned = [port for role in roles for port in expand_port_list(role["ports"])]
        assert sorted(assigned) == sorted(PORTS_2960_24TT), f"{switch}: missing or duplicate ports"


def test_ports_are_configured_as_planned(plan, switches):
    for switch, roles in plan["switch_port_roles"].items():
        config = switches[switch]
        for role in roles:
            for port in expand_port_list(role["ports"]):
                lines = lines_of(config, port)
                where = f"{switch} {port}"
                if role["role"] == "trunk":
                    assert "switchport mode trunk" in lines, where
                    assert "no shutdown" in lines, where
                elif role["role"] == "access":
                    assert "switchport mode access" in lines, where
                    assert f"switchport access vlan {role['vlan']}" in lines, where
                    assert "no shutdown" in lines, where
                    voice = [l for l in lines if l.startswith("switchport voice vlan")]
                    expected_voice = [f"switchport voice vlan {role['voice_vlan']}"] if role.get("voice_vlan") else []
                    assert voice == expected_voice, where
                elif role["role"] == "parked":
                    assert f"switchport access vlan {plan['parking_vlan']}" in lines, where
                    assert "shutdown" in lines and "no shutdown" not in lines, where
                else:
                    pytest.fail(f"Unknown role {role['role']!r}")


def test_access_ports_have_portfast_and_bpduguard(plan, switches):
    for switch, roles in plan["switch_port_roles"].items():
        for role in roles:
            if role["role"] != "access":
                continue
            for port in expand_port_list(role["ports"]):
                lines = lines_of(switches[switch], port)
                assert "spanning-tree portfast" in lines, f"{switch} {port}"
                assert "spanning-tree bpduguard enable" in lines, f"{switch} {port}"


def test_student_ports_use_port_security(plan, switches):
    required = [
        "switchport port-security",
        "switchport port-security maximum 1",
        "switchport port-security mac-address sticky",
        "switchport port-security violation shutdown",
    ]
    for switch, roles in plan["switch_port_roles"].items():
        for role in roles:
            if not role.get("port_security"):
                continue
            for port in expand_port_list(role["ports"]):
                lines = lines_of(switches[switch], port)
                for line in required:
                    assert line in lines, f"{switch} {port} is missing '{line}'"


def test_no_access_port_is_left_in_vlan_1(switches):
    for name, config in switches.items():
        for port, lines in config.interfaces.items():
            if "switchport mode access" in lines:
                assert any(l.startswith("switchport access vlan ") for l in lines), f"{name} {port}"
                assert "switchport access vlan 1" not in lines, f"{name} {port}"


def test_hosts_plug_into_ports_with_their_vlan(plan, switches):
    for host in plan["hosts"]:
        lines = lines_of(switches[host["switch"]], host["port"])
        if host["type"].startswith("IP Phone"):
            assert f"switchport voice vlan {host['vlan']}" in lines, host["name"]
        else:
            assert f"switchport access vlan {host['vlan']}" in lines, host["name"]


# ── Trunks ───────────────────────────────────────────────────────────────


def test_trunk_links_match_on_both_ends(plan, devices, switches):
    allowed = ",".join(str(v) for v in plan["trunk_allowed_vlans"])
    for link in plan["links"]:
        for end in (link["a"], link["b"]):
            if end["device"] not in switches:
                continue
            lines = lines_of(devices[end["device"]], end["port"])
            where = f"{end['device']} {end['port']}"
            assert "switchport mode trunk" in lines, where
            assert f"switchport trunk native vlan {plan['native_vlan']}" in lines, where
            assert f"switchport trunk allowed vlan {allowed}" in lines, where
            assert "switchport nonegotiate" in lines, where


def test_native_vlan_carries_no_users(plan):
    for host in plan["hosts"]:
        assert host["vlan"] != plan["native_vlan"], host["name"]


# ── Router ───────────────────────────────────────────────────────────────


def test_router_has_a_gateway_subinterface_per_routed_vlan(plan, devices):
    subs = {s.vlan: s for s in router_subinterfaces(devices["R1"])}
    for vlan in routed_vlans(plan):
        sub = subs.get(vlan["id"])
        assert sub is not None, f"no subinterface for VLAN {vlan['id']}"
        expected = ipaddress.IPv4Interface(f"{vlan['gateway']}/{ipaddress.IPv4Network(vlan['subnet']).prefixlen}")
        assert sub.interface == expected, f"VLAN {vlan['id']}"
        assert sub.name.endswith(f".{vlan['id']}"), f"subinterface number should match VLAN {vlan['id']}"


def test_router_native_subinterface_matches_trunks_and_has_no_address(plan, devices):
    natives = [s for s in router_subinterfaces(devices["R1"]) if s.native]
    assert len(natives) == 1
    assert natives[0].vlan == plan["native_vlan"]
    assert natives[0].interface is None


def test_router_trunk_interface_is_enabled(plan, devices):
    port = next(l["a"]["port"] for l in plan["links"] if l["a"]["device"] == "R1")
    assert "no shutdown" in devices["R1"].interface(port)


def test_router_acls_are_applied_where_planned(plan, devices):
    applied = {}
    for sub in router_subinterfaces(devices["R1"]):
        if sub.acl_in:
            applied[(sub.name, "in")] = sub.acl_in
        if sub.acl_out:
            applied[(sub.name, "out")] = sub.acl_out
    expected = {
        (interface, direction): acl
        for interface, directions in plan["router_acls"].items()
        for direction, acl in directions.items()
    }
    assert applied == expected


def test_every_defined_router_acl_is_used(devices):
    router = devices["R1"]
    used = set()
    for lines in list(router.interfaces.values()) + list(router.lines.values()):
        for line in lines:
            words = line.split()
            if words[:2] == ["ip", "access-group"] or words[:1] == ["access-class"]:
                used.add(words[2] if words[0] == "ip" else words[1])
    defined = set(router.named_acls) | set(router.numbered_acls)
    assert defined == used, f"unused: {defined - used}, missing: {used - defined}"


def test_acl_addresses_refer_to_real_lab_networks(plan, devices):
    known = {ipaddress.IPv4Network(v["subnet"]) for v in routed_vlans(plan)}
    router = devices["R1"]
    for name in list(router.named_acls) + list(router.numbered_acls):
        for entry in acl_entries(router, name):
            for side in (entry.src, entry.dst):
                if side == ANY:
                    continue
                network = side.as_network()
                assert network is not None, f"{name}: non-contiguous wildcard in '{entry.text}'"
                assert any(network.subnet_of(k) for k in known), f"{name}: '{entry.text}' points outside the lab"


# ── DHCP ─────────────────────────────────────────────────────────────────


def test_dhcp_pools_match_the_plan(plan, devices):
    pools = devices["R1"].dhcp_pools
    dhcp_vlans = [v for v in routed_vlans(plan) if v["dhcp"]]
    assert sorted(pools) == sorted(v["name"] for v in dhcp_vlans)
    for vlan in dhcp_vlans:
        network = ipaddress.IPv4Network(vlan["subnet"])
        lines = pools[vlan["name"]]
        assert f"network {network.network_address} {network.netmask}" in lines, vlan["name"]
        assert f"default-router {vlan['gateway']}" in lines, vlan["name"]
        assert f"dns-server {plan['dns_server']}" in lines, vlan["name"]


def test_dhcp_exclusions_protect_gateways_and_static_devices(plan, devices):
    excluded = [
        (ipaddress.IPv4Address(start), ipaddress.IPv4Address(end)) for start, end in devices["R1"].dhcp_excluded
    ]

    def is_excluded(ip):
        address = ipaddress.IPv4Address(ip)
        return any(start <= address <= end for start, end in excluded)

    dhcp_subnets = [ipaddress.IPv4Network(v["subnet"]) for v in routed_vlans(plan) if v["dhcp"]]
    for owner, address in all_static_addresses(plan):
        if any(ipaddress.IPv4Address(address) in subnet for subnet in dhcp_subnets):
            assert is_excluded(address), f"{owner} ({address}) could be handed out by DHCP"


def test_exclusions_match_the_plan(plan, devices):
    expected = sorted(tuple(v["dhcp_excluded"]) for v in routed_vlans(plan) if v["dhcp"])
    assert sorted(devices["R1"].dhcp_excluded) == expected


# ── Management plane and hardening ───────────────────────────────────────


def test_switch_management_interfaces(plan, switches):
    for device in plan["devices"]:
        if device["name"] not in switches:
            continue
        config = switches[device["name"]]
        mgmt = config.interface(f"Vlan{plan['management_vlan']}")
        assert f"ip address {device['management_ip']} 255.255.255.0" in mgmt, device["name"]
        assert "no shutdown" in mgmt, device["name"]
        assert "shutdown" in config.interface("Vlan1"), device["name"]
        gateway = next(v["gateway"] for v in plan["vlans"] if v["id"] == plan["management_vlan"])
        assert config.has_global(f"ip default-gateway {gateway}"), device["name"]


def test_every_device_allows_ssh_only_from_the_management_vlan(plan, devices):
    mgmt = next(v["subnet"] for v in plan["vlans"] if v["id"] == plan["management_vlan"])
    network = ipaddress.IPv4Network(mgmt)
    expected_acl = [f"permit {network.network_address} {network.hostmask}"]
    for device in plan["devices"]:
        config = devices[device["name"]]
        vty = config.lines.get(f"vty {device['vty_lines']}")
        assert vty is not None, f"{device['name']}: no 'line vty {device['vty_lines']}'"
        assert "transport input ssh" in vty, device["name"]
        assert "login local" in vty, device["name"]
        assert f"access-class {plan['management_acl']} in" in vty, device["name"]
        acl = [l for l in config.numbered_acls[plan["management_acl"]] if not l.startswith("remark")]
        assert acl == expected_acl, device["name"]


def test_every_device_is_ready_for_ssh_version_2(plan, devices):
    for device in plan["devices"]:
        config = devices[device["name"]]
        assert config.hostname == device["name"]
        assert config.has_global(f"ip domain-name {plan['domain']}"), device["name"]
        assert any(l.startswith("crypto key generate rsa") and "2048" in l for l in config.global_lines), device["name"]
        assert config.has_global("ip ssh version 2"), device["name"]
        assert any(l.startswith("username ") and " secret " in l for l in config.global_lines), device["name"]


def test_passwords_are_hashed_or_encrypted(plan, devices):
    for device in plan["devices"]:
        config = devices[device["name"]]
        assert any(l.startswith("enable secret ") for l in config.global_lines), device["name"]
        assert not any(l.startswith("enable password ") for l in config.global_lines), device["name"]
        assert config.has_global("service password-encryption"), device["name"]
        assert not any(" password " in f" {l} " for l in config.global_lines if l.startswith("username ")), device["name"]


def test_console_requires_login(plan, devices):
    for device in plan["devices"]:
        console = devices[device["name"]].lines.get("con 0", [])
        assert "login local" in console, device["name"]
