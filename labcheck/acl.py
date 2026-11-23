"""Evaluate Cisco IOS access lists the way a router does.

Entries are checked top to bottom; the first match decides. If nothing
matches, the packet is denied (the implicit "deny any" at the end).
Supports the forms used in this lab: standard ACLs and extended ACLs for
ip/tcp/udp/icmp with any / host / address+wildcard, "eq <port>", and ICMP
type keywords.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

ICMP_TYPES = {"echo-reply": 0, "unreachable": 3, "echo": 8, "time-exceeded": 11}
PORT_NAMES = {"www": 80, "domain": 53, "bootps": 67, "bootpc": 68, "ftp": 21, "telnet": 23}


@dataclass(frozen=True)
class Packet:
    proto: str  # "tcp", "udp", or "icmp"
    src: str
    dst: str
    sport: int | None = None
    dport: int | None = None
    icmp: str | None = None  # e.g. "echo", "echo-reply"


@dataclass(frozen=True)
class AddressMatch:
    address: int
    wildcard: int

    def matches(self, ip: str) -> bool:
        value = int(ipaddress.IPv4Address(ip))
        return (value & ~self.wildcard & 0xFFFFFFFF) == (self.address & ~self.wildcard & 0xFFFFFFFF)

    def as_network(self) -> ipaddress.IPv4Network | None:
        """The network this entry describes, if the wildcard is contiguous."""
        mask = (~self.wildcard) & 0xFFFFFFFF
        try:
            return ipaddress.IPv4Network((self.address & mask, str(ipaddress.IPv4Address(mask))))
        except ValueError:
            return None


ANY = AddressMatch(0, 0xFFFFFFFF)


@dataclass(frozen=True)
class Entry:
    action: str
    proto: str
    src: AddressMatch
    dst: AddressMatch
    sport: int | None = None
    dport: int | None = None
    icmp: str | None = None
    text: str = ""

    def matches(self, packet: Packet) -> bool:
        if self.proto != "ip" and self.proto != packet.proto:
            return False
        if not self.src.matches(packet.src) or not self.dst.matches(packet.dst):
            return False
        if self.sport is not None and packet.sport != self.sport:
            return False
        if self.dport is not None and packet.dport != self.dport:
            return False
        if self.icmp is not None and packet.icmp != self.icmp:
            return False
        return True


def _take_address(tokens: list[str]) -> AddressMatch:
    word = tokens.pop(0)
    if word == "any":
        return ANY
    if word == "host":
        return AddressMatch(int(ipaddress.IPv4Address(tokens.pop(0))), 0)
    address = int(ipaddress.IPv4Address(word))
    if tokens and _looks_like_ip(tokens[0]):
        return AddressMatch(address, int(ipaddress.IPv4Address(tokens.pop(0))))
    return AddressMatch(address, 0)


def _looks_like_ip(word: str) -> bool:
    try:
        ipaddress.IPv4Address(word)
        return True
    except ValueError:
        return False


def _take_port(tokens: list[str]) -> int | None:
    if tokens and tokens[0] == "eq":
        tokens.pop(0)
        word = tokens.pop(0)
        return int(word) if word.isdigit() else PORT_NAMES[word]
    if tokens and tokens[0] in {"gt", "lt", "neq", "range"}:
        raise ValueError(f"Port operator {tokens[0]!r} is not supported by this checker")
    return None


def parse_entry(text: str, kind: str) -> Entry | None:
    """Parse one ACL line ('permit tcp any host 1.2.3.4 eq 80'). Remarks -> None."""
    tokens = text.split()
    if not tokens or tokens[0] == "remark":
        return None
    action = tokens.pop(0)
    if action not in {"permit", "deny"}:
        raise ValueError(f"Unexpected ACL action in {text!r}")

    if kind == "standard":
        return Entry(action, "ip", _take_address(tokens), ANY, text=text)

    proto = tokens.pop(0)
    if proto not in {"ip", "tcp", "udp", "icmp"}:
        raise ValueError(f"Unsupported protocol {proto!r} in {text!r}")
    src = _take_address(tokens)
    sport = _take_port(tokens) if proto in {"tcp", "udp"} else None
    dst = _take_address(tokens)
    dport = _take_port(tokens) if proto in {"tcp", "udp"} else None
    icmp = None
    if proto == "icmp" and tokens and tokens[0] in ICMP_TYPES:
        icmp = tokens.pop(0)
    if tokens:
        raise ValueError(f"Unparsed words {tokens} in ACL entry {text!r}")
    return Entry(action, proto, src, dst, sport, dport, icmp, text)


def parse_acl(lines: list[str], kind: str) -> list[Entry]:
    return [entry for line in lines if (entry := parse_entry(line, kind)) is not None]


def evaluate(entries: list[Entry], packet: Packet) -> tuple[str, Entry | None]:
    """Return ('permit' | 'deny', the entry that matched or None for the implicit deny)."""
    for entry in entries:
        if entry.matches(packet):
            return entry.action, entry
    return "deny", None
