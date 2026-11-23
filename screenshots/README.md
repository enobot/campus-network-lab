# Screenshots

This folder holds **real** Packet Tracer screenshots, taken after the lab is
built and verified. It's intentionally empty until then: a portfolio
screenshot must show something that actually happened.

Use the file names below so the main README can link to them. Crop each
capture to the relevant window and avoid showing anything personal.

| File | What to capture |
| --- | --- |
| `01-topology.png` | The full logical workspace with every device labelled (use **Options → Preferences → Always Show Port Labels**). |
| `02-show-vlan-brief.png` | `show vlan brief` on ACC-SW1. |
| `03-show-interfaces-trunk.png` | `show interfaces trunk` on CORE-SW1 (all three trunks, native VLAN 999). |
| `04-r1-ip-interface-brief.png` | `show ip interface brief` on R1, with every subinterface up/up. |
| `05-dhcp-bindings.png` | `show ip dhcp binding` on R1, including the phones' leases. |
| `06-student-web-ok.png` | STU-PC1's Web Browser showing `http://www.hru.test` loaded. |
| `07-student-blocked.png` | STU-PC1's Command Prompt: a successful ping to 10.10.30.10, then a blocked ping to a faculty PC. |
| `08-acl-counters.png` | `show access-lists` on R1 after testing, with match counters. |
| `09-ssh-mgmt.png` | IT-ADMIN-PC logging in over SSH to a switch, and FAC-PC2 being refused. |
| `10-simulation-8021q.png` | Simulation mode: the PDU details for a frame on a trunk, showing the 802.1Q tag. |
| `11-port-security.png` | `show port-security interface fa0/11` after Troubleshooting Scenario 5. |

**How:** Windows **Snipping Tool** (`Win + Shift + S`), then save as PNG
here. Once they exist, add them to the main README's "Screenshots" section.
