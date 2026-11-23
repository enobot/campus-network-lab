# Interview prep: questions this lab should let you answer

Answer each question out loud *before* reading the answer. If you can explain
it using this lab as your example ("in my campus lab, I…"), you own it.

---

## Explain the project in 60 seconds

> "I designed and built a campus network for a fictional university in Cisco
> Packet Tracer. It has five VLANs: faculty, students, servers, voice and
> management. They're trunked over 802.1Q to a router that does inter-VLAN
> routing with subinterfaces. The router hands out addresses with DHCP and
> enforces access control lists: students get the campus website and DNS but
> can't reach faculty, phones or the management network. Network devices only
> accept SSH, and only from the management VLAN. I tested it against a
> written test plan of allowed and blocked traffic, and I practised eight
> break-and-fix scenarios, like a native VLAN mismatch and an ACL that
> accidentally blocked DHCP."

Adapt it to what you actually built and tested. Never claim a step you
didn't do.

---

## VLANs and trunking

**1. What is a VLAN, and why use one?**
A VLAN splits one physical switch into separate broadcast domains. In the
lab, students and faculty share the same access switch but sit in different
VLANs. Their traffic can't mix unless it goes through the router, which is
where the ACLs enforce policy. VLANs also keep broadcasts smaller and let a
port's role (faculty office, student lab) be set in configuration instead of
by rewiring.

**2. What's the difference between an access port and a trunk port?**
An access port belongs to one VLAN and sends untagged frames, which suits a
PC. A trunk carries many VLANs between switches (or to a router) and marks
each frame with an 802.1Q tag that says which VLAN it belongs to.

**3. What does the 802.1Q tag contain?**
A 4-byte field inserted into the Ethernet frame. It carries a 12-bit VLAN ID
(so VLANs 1–4094) and a 3-bit priority field (CoS) that voice traffic uses.

**4. What is the native VLAN, and why did you change it to 999?**
The native VLAN's frames cross a trunk *untagged*. By default that's VLAN 1,
which every port starts in. Moving it to an unused VLAN with no users
prevents VLAN-hopping attacks that rely on double tagging. The native VLAN
must match on both ends of a trunk, or untagged traffic lands in the wrong
VLAN (Troubleshooting Scenario 2).

**5. Why `switchport trunk allowed vlan`?**
It limits each trunk to the VLANs that actually need to cross it. That's less
broadcast traffic and less exposure. The catch: the command replaces the
whole list unless you use `add` (Scenario 1).

**6. Why `switchport nonegotiate`?**
It turns off DTP, so a switch port can't be talked into becoming a trunk by
whatever device plugs in.

**7. What does VTP transparent mode do, and why use it here?**
VTP can copy VLAN lists between switches. In transparent mode each switch
keeps its own list. That's safer: a switch with a higher VTP revision number
can't wipe out every VLAN in the network by accident.

## Routing between VLANs

**8. What is router-on-a-stick?**
One physical router interface trunked to a switch, split into subinterfaces,
one per VLAN. Each subinterface has `encapsulation dot1Q <vlan>` and that
VLAN's gateway address. Traffic between VLANs goes up the trunk to the router
and back down, re-tagged for the destination VLAN.

**9. Router-on-a-stick or a Layer 3 switch: which is better?**
A Layer 3 switch routes between VLANs in hardware using SVIs (`interface vlan
10`). It's faster and doesn't depend on one link. Router-on-a-stick is
cheaper and fine for a small site, but the single trunk is both a bottleneck
and a single point of failure (Scenario 8). For a real campus, I'd use Layer
3 switches with a redundant gateway such as HSRP.

## DHCP

**10. Walk me through how a PC gets an address.**
DORA: the PC broadcasts a **Discover**, the server answers with an
**Offer**, the PC broadcasts a **Request** for that offer, and the server
confirms with an **Ack**. In the lab, R1 is the DHCP server for the faculty,
student and voice VLANs.

**11. Why exclude .1 to .20 from each pool?**
So DHCP never hands out an address that's already used by something
configured by hand: the gateway (.1), the printer (10.10.10.10), and room
for future static devices.

**12. What if the DHCP server were on another subnet?**
Broadcasts don't cross routers. You'd add `ip helper-address <server-ip>` on
each VLAN's gateway interface, which relays the requests to the server as
unicast.

**13. A user has a 169.254.x.x address. What does that tell you?**
The PC asked for DHCP and nobody answered, so it gave itself an APIPA
address. Check the port's VLAN, whether the trunk carries that VLAN, whether
an ACL blocks DHCP, and whether the server has addresses left (Scenarios 1
and 4).

## Voice

**14. How do a phone and a PC share one wall jack?**
The phone has a small built-in switch: the jack goes into the phone, and the
PC plugs into the phone. The switch port gets `switchport access vlan 10` for
the PC's untagged data and `switchport voice vlan 50`. Cisco switches tell
the phone (through CDP) to tag its own traffic with VLAN 50. Separate voice
traffic can then get QoS priority and its own policies.

## ACLs

**15. Standard vs. extended ACL?**
A standard ACL matches only the source address. An extended ACL matches
protocol, source, destination and ports. The lab uses extended ACLs for
traffic policy (STUDENT-IN, SERVERS-OUT) and a standard ACL to limit SSH
access to the management VLAN.

**16. Where should an ACL go?**
The usual rule: extended ACLs close to the source, so unwanted traffic dies
early. STUDENT-IN follows that rule, inbound where student traffic enters
R1. SERVERS-OUT is the exception on purpose: one list outbound toward the
server VLAN protects the servers from *every* VLAN at once.

**17. What's a wildcard mask?**
The inverse of a subnet mask: 0 bits must match, 1 bits are ignored.
`10.10.20.0 0.0.0.255` matches 10.10.20.0 to 10.10.20.255. Writing a subnet
mask (255.255.255.0) where a wildcard belongs is a classic mistake.

**18. Why is there a `permit icmp ... echo-reply` line?**
ACLs are stateless: they don't remember that a faculty PC started the ping.
Without that line, the student PC's *reply* would hit the deny statements,
and faculty and IT couldn't ping student machines to troubleshoot them.

**19. What's at the end of every ACL?**
An invisible `deny any`. SERVERS-OUT ends with an explicit `deny ip any any`
so `show access-lists` shows how many packets it dropped.

**20. Order matters: why?**
The router checks lines top to bottom and stops at the first match. A broad
`permit` placed above a specific `deny` makes the deny unreachable.

## Switch security and management

**21. What do PortFast and BPDU Guard do?**
PortFast moves a port straight to forwarding, so a PC isn't kept waiting for
spanning tree. BPDU Guard shuts the port down if a switch is plugged into it,
which prevents loops and rogue switches.

**22. What does port security do in this lab?**
On student ports it learns the first computer's MAC address (sticky) and
shuts the port down if a different device shows up (Scenario 5).

**23. Why SSH, and why only from VLAN 99?**
Telnet sends passwords in clear text; SSH encrypts the session. The VTY
lines accept SSH only, and `access-class 10 in` limits management to the IT
team's network, so a student who guesses a password still can't log in.

## Troubleshooting

**24. A user says "the internet is down." Where do you start?**
Scope first: one user, one VLAN, or everyone? Then bottom-up: link up? Right
VLAN? Valid IP and gateway (`ipconfig`)? Can they ping the gateway? Can they
reach the server by IP but not by name (DNS)? Is an ACL counter climbing?

**25. How does this connect to your current job?**
Answer from your real experience only. For example: at CSUF IT
Telecommunications, assigning VLANs and verifying switch ports on
Alcatel-Lucent OmniSwitch over SSH is the same concept as
`switchport access vlan` here, on different hardware. Building this lab let
you see the whole path: the access port, the trunk, the router, and the
policy.
