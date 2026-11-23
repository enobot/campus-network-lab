"""A small parser for the Cisco IOS configuration files in configs/.

It understands only the commands this lab uses: interfaces (including
"interface range"), VLANs, DHCP pools and exclusions, access lists, and
console/VTY lines. It is a checking aid, not a full IOS parser.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Lines that are typed at the exec prompt, not configuration.
EXEC_COMMANDS = {"enable", "configure terminal", "conf t", "end", "write memory", "exit"}

INTERFACE_PREFIXES = {
    "gi": "GigabitEthernet",
    "gigabitethernet": "GigabitEthernet",
    "fa": "FastEthernet",
    "fastethernet": "FastEthernet",
    "vlan": "Vlan",
}


def normalize_interface(name: str) -> str:
    """'gi0/1' or 'GigabitEthernet0/1' -> 'GigabitEthernet0/1'."""
    match = re.match(r"^([A-Za-z]+)\s*([\d/.]+)$", name.strip())
    if not match:
        raise ValueError(f"Unrecognised interface name: {name!r}")
    prefix, number = match.groups()
    full = INTERFACE_PREFIXES.get(prefix.lower())
    if full is None:
        raise ValueError(f"Unrecognised interface type: {prefix!r}")
    return f"{full}{number}"


def expand_interface_range(spec: str) -> list[str]:
    """'FastEthernet0/3 - 9, GigabitEthernet0/2' -> each interface name."""
    names: list[str] = []
    for part in spec.split(","):
        part = part.strip()
        match = re.match(r"^([A-Za-z]+\s*[\d/]*?/)(\d+)\s*(?:-\s*(\d+))?$", part)
        if not match:
            raise ValueError(f"Unrecognised interface range: {part!r}")
        prefix, start, end = match.groups()
        first, last = int(start), int(end) if end else int(start)
        if last < first:
            raise ValueError(f"Backwards interface range: {part!r}")
        names.extend(normalize_interface(f"{prefix}{n}") for n in range(first, last + 1))
    return names


def expand_port_list(spec: str) -> list[str]:
    """Plan notation 'FastEthernet0/3-9,GigabitEthernet0/2' -> interface names."""
    return expand_interface_range(spec.replace("-", " - "))


@dataclass
class DeviceConfig:
    hostname: str | None = None
    global_lines: list[str] = field(default_factory=list)
    vlans: dict[int, str | None] = field(default_factory=dict)
    interfaces: dict[str, list[str]] = field(default_factory=dict)
    dhcp_pools: dict[str, list[str]] = field(default_factory=dict)
    dhcp_excluded: list[tuple[str, str]] = field(default_factory=list)
    named_acls: dict[str, tuple[str, list[str]]] = field(default_factory=dict)
    numbered_acls: dict[str, list[str]] = field(default_factory=dict)
    lines: dict[str, list[str]] = field(default_factory=dict)

    def interface(self, name: str) -> list[str]:
        return self.interfaces.get(normalize_interface(name), [])

    def has_global(self, line: str) -> bool:
        return line in self.global_lines


def parse_config(text: str) -> DeviceConfig:
    config = DeviceConfig()
    # Sub-command lists that indented lines are added to (several for
    # "interface range", which applies each line to every port in it).
    current_targets: list[list[str]] = []
    vlan_blocks: dict[int, list[str]] = {}

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("!"):
            continue
        indented = raw[0] in (" ", "\t")
        line = " ".join(raw.split())

        if indented:
            if not current_targets:
                raise ValueError(f"Indented command outside any block: {raw!r}")
            for target in current_targets:
                target.append(line)
            continue

        current_targets = []
        if line in EXEC_COMMANDS:
            continue

        if line.startswith("interface range "):
            for name in expand_interface_range(line[len("interface range "):]):
                current_targets.append(config.interfaces.setdefault(name, []))
        elif line.startswith("interface "):
            name = normalize_interface(line[len("interface "):])
            current_targets = [config.interfaces.setdefault(name, [])]
        elif re.match(r"^vlan \d+$", line):
            vlan_id = int(line.split()[1])
            config.vlans.setdefault(vlan_id, None)
            current_targets = [vlan_blocks.setdefault(vlan_id, [])]
        elif line.startswith("ip dhcp pool "):
            current_targets = [config.dhcp_pools.setdefault(line[len("ip dhcp pool "):], [])]
        elif line.startswith("ip dhcp excluded-address "):
            parts = line.split()[3:]
            config.dhcp_excluded.append((parts[0], parts[1] if len(parts) > 1 else parts[0]))
        elif line.startswith("ip access-list "):
            _, _, kind, name = line.split(maxsplit=3)
            entries: list[str] = []
            config.named_acls[name] = (kind, entries)
            current_targets = [entries]
        elif line.startswith("access-list "):
            _, number, rest = line.split(maxsplit=2)
            config.numbered_acls.setdefault(number, []).append(rest)
        elif line.startswith("line "):
            current_targets = [config.lines.setdefault(line[len("line "):], [])]
        else:
            if line.startswith("hostname "):
                config.hostname = line.split(maxsplit=1)[1]
            config.global_lines.append(line)

    for vlan_id, block in vlan_blocks.items():
        for sub in block:
            if sub.startswith("name "):
                config.vlans[vlan_id] = sub[len("name "):]
    return config


def load_config(path: str | Path) -> DeviceConfig:
    return parse_config(Path(path).read_text(encoding="utf-8"))
