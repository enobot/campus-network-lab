# Build guide: Halcyon Ridge University campus network in Packet Tracer

This guide builds the whole lab from an empty Packet Tracer workspace. Plan on
two to three hours the first time. Work top to bottom; each part ends with a
quick check so a mistake never travels far.

**You need:** Cisco Packet Tracer 8.x (free with a Cisco Networking Academy
account). Every config in `configs/` uses standard CCNA-level IOS commands.
Two commands can behave differently between Packet Tracer versions; the
guide flags both.

---

## Part 1: Place the devices

| Device | Packet Tracer model | Where to find it |
| --- | --- | --- |
| R1 | ISR4331 | Network Devices → Routers |
| CORE-SW1, ACC-SW1, ACC-SW2 | 2960-24TT | Network Devices → Switches |
| SRV-WEB-DNS | Server-PT | End Devices |
| FAC-PC1, FAC-PC2, STU-PC1–4, LIB-PC1, IT-ADMIN-PC | PC-PT | End Devices |
| FAC-PRINTER | Printer-PT | End Devices |
| FAC-PHONE1, LIB-PHONE1 | IP Phone 7960 | End Devices |

Rename each device: click it, open the **Config** tab, and change **Display
Name**. Matching names make your screenshots and notes easy to follow.

> No ISR4331 in your version? A 2911 router works too. Its trunk port is
> `GigabitEthernet0/0` instead of `GigabitEthernet0/0/0`: change that name
> everywhere in `configs/R1.txt` before pasting.

## Part 2: Cable it

Use these exact ports so the configs match. "Straight" means Copper
Straight-Through; "Cross" means Copper Cross-Over.

| From | Port | To | Port | Cable |
| --- | --- | --- | --- | --- |
| R1 | Gig0/0/0 | CORE-SW1 | Gig0/1 | Straight |
| CORE-SW1 | Fa0/1 | ACC-SW1 | Gig0/1 | Cross |
| CORE-SW1 | Fa0/2 | ACC-SW2 | Gig0/1 | Cross |
| CORE-SW1 | Fa0/10 | SRV-WEB-DNS | Fa0 | Straight |
| ACC-SW1 | Fa0/1 | FAC-PHONE1 | Switch | Straight |
| FAC-PHONE1 | PC | FAC-PC1 | Fa0 | Straight |
| ACC-SW1 | Fa0/2 | FAC-PC2 | Fa0 | Straight |
| ACC-SW1 | Fa0/10 | FAC-PRINTER | Fa0 | Straight |
| ACC-SW1 | Fa0/11 | STU-PC1 | Fa0 | Straight |
| ACC-SW1 | Fa0/12 | STU-PC2 | Fa0 | Straight |
| ACC-SW1 | Fa0/21 | IT-ADMIN-PC | Fa0 | Straight |
| ACC-SW2 | Fa0/1 | LIB-PHONE1 | Switch | Straight |
| LIB-PHONE1 | PC | LIB-PC1 | Fa0 | Straight |
| ACC-SW2 | Fa0/5 | STU-PC3 | Fa0 | Straight |
| ACC-SW2 | Fa0/6 | STU-PC4 | Fa0 | Straight |

**Power the phones.** The 2960 doesn't supply power over Ethernet, so each IP
phone needs its power adapter: click the phone → **Physical** tab → drag the
power adapter from the list on the left onto the phone's power socket.

**Check:** links between switches start amber while spanning tree settles,
then turn green within about 30 seconds.

## Part 3: Configure the switches

For each switch: click it → **CLI** tab → press Enter → paste the whole
matching file from `configs/`:

1. `configs/CORE-SW1.txt`
2. `configs/ACC-SW1.txt`
3. `configs/ACC-SW2.txt`

Read the output as it scrolls. Warnings about `portfast` are normal (IOS
reminds you to use it only on ports to end devices, which is how it's used
here). Anything starting with `% Invalid input` is not normal: note which
line caused it.

> **Version note: the SSH key.** The configs use
> `crypto key generate rsa general-keys modulus 2048`. If your Packet Tracer
> rejects it, type `crypto key generate rsa` and answer `2048` when asked
> for the modulus size. Then re-run `ip ssh version 2`.

**Check on each switch:**

```
show vlan brief
show interfaces trunk
```

VLANs 10, 20, 30, 50, 99, 998 and 999 exist; the access ports sit in the
right VLANs. Trunks show **Mode on**, **Encapsulation 802.1q**, **Native vlan
999**, and **10,20,30,50,99** as allowed.

## Part 4: Configure the router

Click R1 → **CLI**. If asked "Would you like to enter the initial
configuration dialog?", type `no`. Press Enter, then paste
`configs/R1.txt`. The same SSH-key note applies.

**Check:**

```
show ip interface brief
```

`Gig0/0/0` and every subinterface (`.10 .20 .30 .50 .99 .999`) should read
**up / up**, with the gateway addresses from the IP plan.

## Part 5: Set up the server

Click SRV-WEB-DNS.

1. **Desktop → IP Configuration → Static**
   - IPv4 Address `10.10.30.10`, Subnet Mask `255.255.255.0`
   - Default Gateway `10.10.30.1`, DNS Server `10.10.30.10`
2. **Services → DNS**: turn DNS **On**, then add an **A Record** with Name
   `www.hru.test` and Address `10.10.30.10`. Click **Add**.
3. **Services → HTTP**: make sure HTTP and HTTPS are **On**. Optional: edit
   `index.html` so the page says "Halcyon Ridge University".
4. **Services → FTP**: leave it **On** (default user `cisco`, password
   `cisco`). FTP isn't meant for students or faculty; the ACLs block it, and
   testing that is part of the lab.

## Part 6: Set up the end devices

**PCs on DHCP** (FAC-PC1, FAC-PC2, LIB-PC1, STU-PC1 to STU-PC4):
**Desktop → IP Configuration → DHCP**. Each PC should show "DHCP request
successful" and an address from its VLAN's pool: `.21` or higher, because
`.1–.20` are excluded.

**IT-ADMIN-PC (static):** **Desktop → IP Configuration → Static**: address
`10.10.99.50`, mask `255.255.255.0`, gateway `10.10.99.1`, DNS `10.10.30.10`.

**FAC-PRINTER (static):** **Config → FastEthernet0**: address `10.10.10.10`,
mask `255.255.255.0`. Then **Config → Settings**: gateway `10.10.10.1`.

**IP phones:** once powered, they request an address in the voice VLAN on
their own. Confirm on R1 with `show ip dhcp binding`: you should see leases
in `10.10.50.0/24`.

> **Phones registering for calls is out of scope.** In this build the phones
> get an address in VLAN 50, but they won't register or make calls. That
> needs a call-control server (Cisco CME), which isn't part of this design
> and hasn't been tested. It's a good stretch goal for later.

## Part 7: Verify everything

Work through [`VERIFICATION.md`](VERIFICATION.md). It lists every
`show` command and connectivity test, with the expected result for each.

## Part 8: Save your work and your evidence

1. **File → Save As** → `packet-tracer/hru-campus-lab.pkt`.
2. Capture the screenshots listed in
   [`../screenshots/README.md`](../screenshots/README.md).
3. Paste the `show` command output into the files in
   [`../evidence/`](../evidence/README.md).
4. On every device, run `write memory` (the configs end with it, but run it
   again after any change you make).
