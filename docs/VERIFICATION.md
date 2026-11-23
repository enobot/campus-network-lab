# Verification checklist

Run these after building the lab (see [`BUILD-GUIDE.md`](BUILD-GUIDE.md)).
Record each result in the **Result** column, and paste the command output
into [`../evidence/`](../evidence/README.md). A test counts as passed only
when you've seen it pass in Packet Tracer.

The test IDs (P01, P02, …) match the cases in `design/lab-plan.json`, which
the automated checks (`pytest`) run against the configs' logic. Those checks
read the config files; these tests prove the network behaves that way.

---

## Part A: Device checks

### All switches

| Command | What a pass looks like | Result |
| --- | --- | --- |
| `show vlan brief` | VLANs 10 FACULTY, 20 STUDENTS, 30 SERVERS, 50 VOICE, 99 MGMT, 998 PARKING, 999 NATIVE. Access ports listed under the right VLAN; unused ports under 998. | |
| `show interfaces trunk` | Each uplink: Mode **on**, Encapsulation **802.1q**, Status **trunking**, Native vlan **999**. "Vlans allowed on trunk" is **10,20,30,50,99**. | |
| `show interfaces status` | Unused ports show **disabled**; ports with devices show **connected**. | |
| `show spanning-tree vlan 10` | On CORE-SW1: "This bridge is the root". On the access switches: the root port is Gig0/1 (the uplink). | |
| `show ip interface brief` | `Vlan99` is up/up with the management address; `Vlan1` is administratively down. | |
| `show ip ssh` | SSH enabled, version 2.0. | |

### ACC-SW1 and ACC-SW2 only

| Command | What a pass looks like | Result |
| --- | --- | --- |
| `show interfaces fa0/1 switchport` | Access Mode VLAN **10 (FACULTY)**, Voice VLAN **50 (VOICE)**. | |
| `show port-security interface fa0/11` (ACC-SW2: `fa0/5`) | Port Security **Enabled**, Port Status **Secure-up**, Violation Mode **Shutdown**, Maximum MAC Addresses **1**, Sticky MAC Addresses **1** once the PC has sent traffic. | |
| `show port-security address` | One sticky MAC address per student port in use. | |

### R1

| Command | What a pass looks like | Result |
| --- | --- | --- |
| `show ip interface brief` | Gig0/0/0 and subinterfaces .10 .20 .30 .50 .99 .999 are **up/up**; .10–.99 show the gateway addresses. | |
| `show interfaces gig0/0/0.20` | "Encapsulation 802.1Q Virtual LAN, Vlan ID 20". | |
| `show ip dhcp binding` | Leases in 10.10.10.x, 10.10.20.x and 10.10.50.x, all **.21 or higher** (the exclusions work). | |
| `show ip dhcp pool` | Three pools (FACULTY, STUDENTS, VOICE) with leased addresses counted. | |
| `show access-lists` | STUDENT-IN, SERVERS-OUT and standard list 10. After Part B, the lines you tested show **(N match(es))**. | |
| `show ip route` | Five **C** (connected) routes, one per routed VLAN, plus the **L** (local) gateway addresses. | |

---

## Part B: End-to-end tests

Run these from each device's **Desktop** tab: **Command Prompt**, **Web
Browser** or **IP Configuration**.

**Telling "blocked" apart from "broken":** when R1's ACL drops a packet, R1
usually answers with an ICMP unreachable message, so a blocked ping often
shows `Reply from 10.10.20.1: Destination host unreachable.` A
`Request timed out.` also counts as blocked. Write down what you actually
see. Then confirm on R1 with `show access-lists`: the match counter on the
deny line should go up.

> Tip: run every **permit** test first. If those pass, routing works, so a
> failed **deny** test can only mean the ACL did its job.

### Student PC (STU-PC1 or STU-PC3)

| ID | Action | Expected | Result |
| --- | --- | --- | --- |
| P01 | IP Configuration → DHCP | Lease from 10.10.20.21–.254, gateway 10.10.20.1, DNS 10.10.30.10 | |
| P02 | `ping 10.10.20.1` | Replies | |
| P03 | Web Browser → `http://www.hru.test` | Campus page loads | |
| P04 | Web Browser → `https://www.hru.test` | Campus page loads | |
| P05 | `ping www.hru.test` | Name resolves to 10.10.30.10 and replies | |
| P06 | `ping 10.10.30.10` | Replies | |
| P07 | `ftp 10.10.30.10` | Fails, no login prompt (STUDENT-IN) | |
| P09 | `ping <FAC-PC2's address>` | Blocked | |
| P10 | `ping 10.10.10.10` (printer) | Blocked | |
| P11 | `ping <a phone's address from show ip dhcp binding>` | Blocked | |
| P12 | `ping 10.10.99.50` | Blocked | |
| P13 | `ssh -l netadmin 10.10.99.2` | Fails, never reaches the switch (STUDENT-IN) | |
| P14 | `ssh -l netadmin 10.10.20.1` | Refused by R1, e.g. "Connection refused" (VTY access-class) | |

### Faculty PC (FAC-PC2)

| ID | Action | Expected | Result |
| --- | --- | --- | --- |
| P30 | IP Configuration → DHCP | Lease from 10.10.10.21–.254 | |
| P15 / P16 | `ping <STU-PC1's address>` | Replies (STUDENT-IN lets echo-replies out) | |
| P17 | Web Browser → `http://www.hru.test` | Page loads | |
| P18 | `ping www.hru.test` | Resolves and replies | |
| P19 | `ftp 10.10.30.10` | Fails (SERVERS-OUT) | |
| P21 | `ping 10.10.10.10` (printer, same VLAN) | Replies | |
| P22 | `ssh -l netadmin 10.10.99.2` | Refused by CORE-SW1 (VTY access-class) | |

### IT admin PC (IT-ADMIN-PC)

| ID | Action | Expected | Result |
| --- | --- | --- | --- |
| P23 | `ssh -l netadmin 10.10.99.2` | Password prompt; log in with the lab password; prompt shows `CORE-SW1>` | |
| P24 | `ssh -l netadmin 10.10.99.4` | Logs in to `ACC-SW2` | |
| P25 | `ssh -l netadmin 10.10.99.1` | Logs in to `R1` | |
| P26 | `ftp 10.10.30.10` | FTP login prompt (user `cisco` / `cisco`); IT has admin access | |
| P27 | `ping <STU-PC1's address>` | Replies | |
| extra | `telnet 10.10.99.2` | Refused: VTY lines accept SSH only | |

### Server (SRV-WEB-DNS)

| ID | Action | Expected | Result |
| --- | --- | --- | --- |
| P31 | `ping <FAC-PC2's address>` | Replies (SERVERS-OUT lets echo-replies in) | |
| P32 | `ping <STU-PC1's address>` | Replies | |

### Phones

| ID | Action | Expected | Result |
| --- | --- | --- | --- |
| P29 | On R1: `show ip dhcp binding` | Each phone has a lease in 10.10.50.0/24 | |
| extra | On ACC-SW1: `show mac address-table interface fa0/1` | Two MAC addresses on one port: the phone in VLAN 50, FAC-PC1 in VLAN 10 | |

### Cases checked only by the automated tests

These can't be reproduced directly in Packet Tracer. The pytest suite checks
them against the config logic, and other tests above confirm them indirectly:

| ID | Why not testable by hand | Indirect evidence |
| --- | --- | --- |
| P08, P20 | Packet Tracer's server has no SSH service to connect to | P07 and P19 prove the same ACL lines block non-web traffic |
| P28 | Server replies can't be sent on their own | P03 succeeding proves the replies get back |

---

## Part C: Watch it happen (optional, great for screenshots)

Switch to **Simulation** mode (bottom right), filter on ICMP, and ping from
STU-PC1 to FAC-PC2. Step through the events:

- On the trunk the frame carries an **802.1Q header with VLAN 20**.
- At R1 the packet is dropped. Click the event at R1 and read the
  **OSI Model** tab, where Packet Tracer explains what the router decided.

Repeat with STU-PC1 → `10.10.30.10` to see the packet re-tagged with
VLAN 30 on its way back down the trunk. That's router-on-a-stick in action.
