"""A model of the lab network built from design/lab-plan.json and configs/.

It answers one question for the policy tests: would R1 (and, for SSH, the
target device's VTY access list) let a given packet through? It reads the
router's real subinterface addresses and ACLs from configs/R1.txt, so a
mistake in the config file shows up as a failed check.

It models layer 3 policy only. It cannot tell whether the configs work in
Packet Tracer; that is what docs/VERIFICATION.md is for.
"""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass, field
from pathlib import Path

from .acl import Entry, Packet, evaluate, parse_acl
from .iosconfig import DeviceConfig, load_config

ROOT = Path(__file__).resolve().parent.parent
BROADCAST = "255.255.255.255"


def load_plan() -> dict:
    return json.loads((ROOT / "design" / "lab-plan.json").read_text(encoding="utf-8"))


def load_devices(plan: dict) -> dict[str, DeviceConfig]:
    return {device["name"]: load_config(ROOT / device["config"]) for device in plan["devices"]}


def acl_entries(config: DeviceConfig, name: str) -> list[Entry]:
    if name in config.named_acls:
        kind, lines = config.named_acls[name]
        return parse_acl(lines, kind)
    if name in config.numbered_acls:
        kind = "standard" if int(name) < 100 or 1300 <= int(name) <= 1999 else "extended"
        return parse_acl(config.numbered_acls[name], kind)
    raise KeyError(f"ACL {name!r} is not defined")


@dataclass
class SubInterface:
    name: str
    vlan: int
    native: bool
    interface: ipaddress.IPv4Interface | None
    acl_in: str | None = None
    acl_out: str | None = None


@dataclass
class Decision:
    action: str
    reasons: list[str] = field(default_factory=list)
    # (ACL name, matching line) for every router ACL the packet passed through.
    matched: list[tuple[str, str]] = field(default_factory=list)


def router_subinterfaces(router: DeviceConfig) -> list[SubInterface]:
    result = []
    for name, lines in router.interfaces.items():
        if "." not in name:
            continue
        vlan, native, address, acl_in, acl_out = None, False, None, None, None
        for line in lines:
            words = line.split()
            if words[:2] == ["encapsulation", "dot1Q"]:
                vlan = int(words[2])
                native = "native" in words[3:]
            elif words[:2] == ["ip", "address"]:
                address = ipaddress.IPv4Interface(f"{words[2]}/{words[3]}")
            elif words[:2] == ["ip", "access-group"]:
                if words[3] == "in":
                    acl_in = words[2]
                else:
                    acl_out = words[2]
        if vlan is None:
            raise ValueError(f"{name} has no 'encapsulation dot1Q' line")
        result.append(SubInterface(name, vlan, native, address, acl_in, acl_out))
    return result


class CampusNetwork:
    def __init__(self, plan: dict | None = None, devices: dict[str, DeviceConfig] | None = None):
        self.plan = plan or load_plan()
        self.devices = devices or load_devices(self.plan)
        self.router = self.devices["R1"]
        self.subinterfaces = [s for s in router_subinterfaces(self.router) if s.interface]
        self.router_ips = {str(s.interface.ip) for s in self.subinterfaces}

    def _subinterface_for(self, ip: str) -> SubInterface | None:
        address = ipaddress.IPv4Address(ip)
        for sub in self.subinterfaces:
            if address in sub.interface.network:
                return sub
        return None

    def _subinterface_for_vlan(self, vlan: int) -> SubInterface | None:
        return next((s for s in self.subinterfaces if s.vlan == vlan), None)

    def _check(self, acl_name: str | None, packet: Packet, where: str, decision: Decision) -> bool:
        if acl_name is None:
            decision.reasons.append(f"{where}: no ACL")
            return True
        action, entry = evaluate(acl_entries(self.router, acl_name), packet)
        matched = entry.text if entry else "implicit deny any"
        decision.reasons.append(f"{where}: {acl_name} -> {action} ({matched})")
        decision.matched.append((acl_name, matched))
        return action == "permit"

    def forward(self, packet: Packet, from_vlan: int | None = None) -> Decision:
        """Would the packet reach its destination at layer 3?"""
        decision = Decision("deny")
        ingress = self._subinterface_for_vlan(from_vlan) if from_vlan else self._subinterface_for(packet.src)
        if ingress is None:
            decision.reasons.append("source is in no routed VLAN")
            return decision

        destination_sub = self._subinterface_for(packet.dst) if packet.dst != BROADCAST else ingress
        if destination_sub is ingress and packet.dst not in self.router_ips and packet.dst != BROADCAST:
            decision.action = "permit"
            decision.reasons.append(f"same VLAN {ingress.vlan}: switched, never reaches R1")
            return decision

        if not self._check(ingress.acl_in, packet, f"in on {ingress.name}", decision):
            return decision

        if packet.dst in self.router_ips or packet.dst == BROADCAST:
            decision.action = "permit"
            decision.reasons.append("delivered to R1 itself")
            return decision

        if destination_sub is None:
            decision.reasons.append("no route to destination")
            return decision
        if self._check(destination_sub.acl_out, packet, f"out on {destination_sub.name}", decision):
            decision.action = "permit"
        return decision

    def device_for_address(self, ip: str) -> str | None:
        if ip in self.router_ips:
            return "R1"
        for device in self.plan["devices"]:
            if device["management_ip"] == ip:
                return device["name"]
        return None

    def ssh_allowed(self, device_name: str, source_ip: str) -> Decision:
        """Would the device's VTY lines accept an SSH session from source_ip?"""
        decision = Decision("deny")
        config = self.devices[device_name]
        vty = next((lines for key, lines in config.lines.items() if key.startswith("vty")), None)
        if vty is None:
            decision.reasons.append(f"{device_name}: no VTY lines configured")
            return decision
        if "transport input ssh" not in vty:
            decision.reasons.append(f"{device_name}: VTY does not accept SSH")
            return decision
        access_class = next((line.split()[1] for line in vty if line.startswith("access-class ")), None)
        if access_class is None:
            decision.action = "permit"
            decision.reasons.append(f"{device_name}: VTY has no access-class")
            return decision
        packet = Packet("tcp", source_ip, "0.0.0.0", dport=22)
        action, entry = evaluate(acl_entries(config, access_class), packet)
        matched = entry.text if entry else "implicit deny any"
        decision.reasons.append(f"{device_name}: VTY access-class {access_class} -> {action} ({matched})")
        decision.action = action
        return decision

    def evaluate_policy(self, test: dict) -> Decision:
        packet = Packet(
            proto=test["proto"],
            src=test["src"],
            dst=test["dst"],
            sport=test.get("sport"),
            dport=test.get("dport"),
            icmp=test.get("icmp"),
        )
        decision = self.forward(packet, test.get("from_vlan"))
        if decision.action != "permit" or test.get("layer") != "management":
            return decision
        target = self.device_for_address(packet.dst)
        if target is None:
            decision.action = "deny"
            decision.reasons.append("destination is not a network device")
            return decision
        management = self.ssh_allowed(target, packet.src)
        decision.action = management.action
        decision.reasons.extend(management.reasons)
        return decision
