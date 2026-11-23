# Troubleshooting scenarios (break it, then fix it)

Each scenario breaks the working lab on purpose. Before reading the
diagnosis, try to find the fault yourself with `show` commands. That's the
skill interviewers are actually testing.

**Before you start:** save a copy of your working `.pkt` file. After each
scenario, apply the fix (or reopen the saved file) so faults never stack.

**A method that works every time:** go bottom-up through the layers.

1. **Physical:** is the link up? (`show interfaces status`)
2. **Data link:** is the port in the right VLAN, and is the trunk carrying it?
   (`show vlan brief`, `show interfaces trunk`)
3. **Network:** does the PC have the right address and gateway, and can it
   reach the gateway? (`ipconfig`, `ping <gateway>`)
4. **Policy:** is an ACL dropping it? (`show access-lists`: which counter
   went up?)

---

## Scenario 1: Students get 169.254.x.x addresses

**Break it** (ACC-SW1):
```
configure terminal
interface GigabitEthernet0/1
 switchport trunk allowed vlan 10,30,50,99
end
```

**Symptoms:** STU-PC1 and STU-PC2 show "DHCP request failed" and get an
APIPA address (169.254.x.x). Faculty PCs on the same switch still work.

**Diagnose:**
- `ipconfig` on STU-PC1: a 169.254.x.x address means no DHCP server answered.
- Only VLAN 20 is affected, so look at what carries VLAN 20 off the switch.
- `show interfaces trunk` on ACC-SW1: VLAN 20 is missing from "Vlans allowed
  on trunk".

**Fix:**
```
interface GigabitEthernet0/1
 switchport trunk allowed vlan 10,20,30,50,99
```
Then IP Configuration → DHCP on the student PCs again.

**Why it happened:** `switchport trunk allowed vlan` *replaces* the whole
list. To add one VLAN without retyping the list, use
`switchport trunk allowed vlan add 20`.

---

## Scenario 2: Native VLAN mismatch

**Break it** (ACC-SW2):
```
configure terminal
interface GigabitEthernet0/1
 switchport trunk native vlan 1
end
```

**Symptoms:** The switch console logs CDP messages about a native VLAN
mismatch. Tagged VLANs usually keep working, which is what makes this fault
easy to miss, but spanning tree can block the trunk for the mismatched VLANs.

**Diagnose:**
- Read the CDP log message: it names both ports and both native VLANs.
- `show interfaces trunk` on both ends: Native vlan **1** on ACC-SW2 but
  **999** on CORE-SW1.

**Fix:**
```
interface GigabitEthernet0/1
 switchport trunk native vlan 999
```

**Why it matters:** untagged frames land in different VLANs on each side.
Attackers abuse this with VLAN double-tagging, which is why this design
moves the native VLAN off VLAN 1 to a VLAN with no users.

---

## Scenario 3: Wrong VLAN tag on a router subinterface

**Break it** (R1):
```
configure terminal
interface GigabitEthernet0/0/0.20
 encapsulation dot1Q 21
end
```

**Symptoms:** Student PCs lose DHCP and can't ping 10.10.20.1. Every other
VLAN works.

**Diagnose:**
- `show ip interface brief` on R1: .20 is still **up/up**. The subinterface
  looks healthy, which is the trap.
- `show interfaces gig0/0/0.20`: "Vlan ID **21**".
- `show vlan brief` on the switches: there is no VLAN 21. R1 is listening on
  a VLAN that doesn't exist.

**Fix:**
```
interface GigabitEthernet0/0/0.20
 encapsulation dot1Q 20
```

---

## Scenario 4: The ACL that broke DHCP

**Break it** (R1):
```
configure terminal
ip access-list extended STUDENT-IN
 no permit udp any eq 68 any eq 67
end
```

**Symptoms:** Students who already have a lease keep working, because their
renewals come from their own address and match the last line. A new student
PC, or one that releases its address and asks again, gets no lease.

**Diagnose:**
- DHCP fails only in VLAN 20, the only VLAN with an inbound ACL.
- `show access-lists STUDENT-IN`: the DHCP line is gone. DHCP Discover
  packets come from 0.0.0.0, so no other line matches them, and the final
  `permit ip 10.10.20.0 0.0.0.255 any` can't help either.

**Fix** (sequence number 5 puts the line back at the top):
```
ip access-list extended STUDENT-IN
 5 permit udp any eq 68 any eq 67
```

**Why it matters:** an inbound ACL also filters traffic *to the router
itself*, including DHCP requests. This is one of the most common real-world
ACL mistakes.

---

## Scenario 5: Port security shut a student port down

**Break it:** on ACC-SW1, unplug STU-PC1 from Fa0/11. Plug a *different* PC
into Fa0/11, then have that PC ping anything.

**Symptoms:** the new PC gets no network, and the link light on Fa0/11
turns red.

**Diagnose:**
- `show interfaces status`: Fa0/11 is **err-disabled**.
- `show port-security interface fa0/11`: Port Status **Secure-shutdown**,
  Security Violation Count **1**, and the sticky MAC is the *old* PC's address.

**Fix** (after confirming the new computer is allowed):
```
configure terminal
interface FastEthernet0/11
 no switchport port-security mac-address sticky <old-mac-address>
 shutdown
 no shutdown
end
```
Use the old MAC from `show port-security address`. Removing it lets the new
PC's MAC be learned instead. Save with `write memory`.

---

## Scenario 6: A faculty PC plugged into a student port

**Break it:** move FAC-PC2's cable from ACC-SW1 Fa0/2 to Fa0/13 (an unused
student port), then request DHCP on FAC-PC2.

**Symptoms:** FAC-PC2 gets a 10.10.20.x address and can no longer reach the
printer or other faculty PCs.

**Diagnose:**
- `ipconfig` on FAC-PC2: the address is in the *student* subnet.
- `show mac address-table` on ACC-SW1: FAC-PC2's MAC is on Fa0/13 in VLAN 20.
- The VLAN comes from the *switch port*, not the PC.

**Fix:** move the cable back to a faculty port (Fa0/1–9) and renew DHCP.
Port security on Fa0/13 has now learned FAC-PC2's MAC as sticky; remove it
the same way as in Scenario 5. At work this is a patching problem: the fix
is the right jack, or reassigning the port's VLAN.

---

## Scenario 7: Pings work by address but not by name

**Break it** (R1):
```
configure terminal
ip dhcp pool STUDENTS
 dns-server 10.10.30.99
end
```
Renew DHCP on STU-PC1.

**Symptoms:** `ping 10.10.30.10` works, but `ping www.hru.test` and
`http://www.hru.test` fail.

**Diagnose:**
- Reaching the server by address but not by name points straight at DNS.
- `ipconfig /all` on STU-PC1: the DNS server is 10.10.30.99, which doesn't exist.

**Fix:**
```
ip dhcp pool STUDENTS
 dns-server 10.10.30.10
```
Then renew DHCP on the PC.

---

## Scenario 8: Every VLAN is down at once

**Break it** (R1):
```
configure terminal
interface GigabitEthernet0/0/0
 shutdown
end
```

**Symptoms:** no PC can reach anything outside its own VLAN, and DHCP fails
everywhere. Pings inside a VLAN (FAC-PC2 to the printer) still work.

**Diagnose:**
- Every VLAN fails at once, but same-VLAN traffic still works, so look at
  the one thing all VLANs share: R1's trunk.
- `show ip interface brief` on R1: Gig0/0/0 and *every* subinterface show
  **administratively down**.

**Fix:**
```
interface GigabitEthernet0/0/0
 no shutdown
```

**Why it matters:** router-on-a-stick has a single point of failure. In an
interview, this is a good opening to talk about Layer 3 switches with SVIs
and redundant gateways (HSRP).

---

## Record what you did

For each scenario, write a short entry in `evidence/troubleshooting-log.md`:
symptom, the commands you used, root cause, and fix. Five well-written
entries are worth more to an interviewer than any certificate line.
