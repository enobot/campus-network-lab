# Test evidence

Paste real command output here after building the lab: copy from the
Packet Tracer CLI with `Ctrl+C`, and paste into a text file. Raw output is
the strongest proof that the configuration works.

Create these files as you work through [`../docs/VERIFICATION.md`](../docs/VERIFICATION.md):

| File | Contents |
| --- | --- |
| `R1-show-outputs.txt` | `show ip interface brief`, `show ip dhcp binding`, `show ip dhcp pool`, `show access-lists`, `show ip route` |
| `CORE-SW1-show-outputs.txt` | `show vlan brief`, `show interfaces trunk`, `show spanning-tree vlan 10`, `show ip ssh` |
| `ACC-SW1-show-outputs.txt` | `show vlan brief`, `show interfaces trunk`, `show interfaces fa0/1 switchport`, `show port-security interface fa0/11`, `show port-security address` |
| `ACC-SW2-show-outputs.txt` | Same commands as ACC-SW1 (port-security on `fa0/5`) |
| `end-to-end-results.md` | The Part B tables from VERIFICATION.md with each Result filled in (pass/fail, date) |
| `troubleshooting-log.md` | One entry per scenario from TROUBLESHOOTING.md: symptom, commands, root cause, fix |

At the top of each file, note the Packet Tracer version and the date, for
example: `Packet Tracer 8.2.2, 2026-12-05`.
