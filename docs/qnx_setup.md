# QNX 8.0 + QEMU setup and log extraction

This guide gets a real `RTARCH` log out of a QNX 8.0 QEMU target.

It follows the exact flow QNX documents for a Named User licence, and the
Quick Start Target Image (QSTI) that QNX ships for QEMU. Verified against the
public QNX SDP 8.0 QEMU walkthrough that ships with the platform.

---

## 1. Accept and deploy the licence

Your licence email (serial `911285-10383452`) gives three steps:

1. Log in to your **myQNX** account and open **myQNX License Manager**:
   <https://www.qnx.com/account/dashboard>
2. Click **Accept** on the licence. Until you accept it, it stays
   *Available* and cannot be deployed.
3. Click the **Users** column and **deploy** the licence to your own account
   (`ammarbloch@protonmail.com`).

Once deployed, the QNX Software Center will see the licence when you log in
with that account.

> The licence manager in your screenshot shows every seat as **Available** —
> that means none has been accepted/deployed yet. Do step 2 and 3 first.

## 2. Install the QNX Software Center

Download the Linux host installer from the QNX download page:

<https://www.qnx.com/download/group.html?programid=29178>

The direct file is `qnx-setup-2.0.4-…-linux.run` (~100 MB). You must be logged
in to fetch it — the unauthenticated URL redirects to the login page.

```sh
chmod +x qnx-setup-2.0.4-*-linux.run
./qnx-setup-2.0.4-*-linux.run        # installs into ~/qnx/qnxsoftwarecenter
```

Then run it and log in with `ammarbloch@protonmail.com`:

```sh
~/qnx/qnxsoftwarecenter/qnxsoftwarecenter
```

## 3. Install QNX SDP 8.0 and the QEMU target image

Inside the QNX Software Center, install **both** of these (search by name):

| Package | What it gives you |
|---|---|
| **QNX SDP 8.0** (host: Linux x86_64) | `qcc`, the QNX headers, `libslog2`, `mkqnximage` |
| **QNX SDP 8.0 Quick Start Target Image for QEMU** (QSTI) | a bootable QNX 8.0 system image for QEMU |

They install under `~/qnx800/`:

```
~/qnx800/qnxsdp-env.sh              <- source this
~/qnx800/host/linux/x86_64/usr/bin/qcc
~/qnx800/images/qemu/               <- the QSTI
```

The QSTI arrives as three ~1 GB split archives plus an unpack script:

```sh
cd ~/qnx800/images/qemu
./unpack_qemu_image.sh             # produces qemu/output/{ifs.bin,disk-qemu,disk-qemu.vmdk}
```

> Do not delete the `.tar.gz.0/.1/.2` parts until you are sure the image works.

## 4. Build the demo

```sh
source ~/qnx800/qnxsdp-env.sh
cd target/qnx8_demo
make
```

or, using the helper:

```sh
bash scripts/setup_qnx_sdp.sh --env-only     # skips the installer, builds directly
```

This builds `sensor_service`, `perception_service`, `brake_controller`,
`brake_controller_fixed`, `telemetry_client`, `diagnostics_client`.

## 5. Boot the target

The QSTI ships its own launcher — use it rather than hand-rolling QEMU flags:

```sh
source ~/qnx800/qnxsdp-env.sh
cd ~/qnx800/images/qemu/qemu
mkqnximage --run
```

The guest boots to a **Developer Desktop**. Log in with:

```
username: root
password: root
```

The guest gets an address on QEMU's user network, typically
`192.168.122.x`. QEMU mode does **not** provide a graphical console from the
host, so work inside the guest desktop or over SSH.

## 6. Copy the binaries into the guest

Check whether the QSTI runs an SSH server:

```sh
# in the guest terminal:
pidin args | grep -i sshd
```

If it does, from the host:

```sh
scp -P 22 target/qnx8_demo/{sensor_service,perception_service,brake_controller,brake_controller_fixed,telemetry_client,diagnostics_client} root@192.168.122.x:/tmp/
```

If it does not, use the serial console, or attach the binaries to the image
before boot. `scripts/run_qnx_demo.sh` prints the options at that step.

## 7. Run the demo and extract the log

Inside the guest:

```sh
cd /tmp
sh scripts/run_flawed_demo.sh      # starts services, runs 6 s, stops them
sh scripts/extract_slog2.sh        # slog2info > /tmp/raw_slog2.txt
```

Copy `/tmp/raw_slog2.txt` back to the host.

## 8. Analyse on the host

```sh
cd ~/Desktop/rt-architect
.venv/bin/rtarch analyze examples/logs/real_qnx_flawed.log \
  --scenario scenarios/brake_demo.json \
  --output examples/reports/real_qnx_flawed.html
```

Expected: `BOTTLENECK-001`, `CRITICAL-PATH-001`, `HEAD-OF-LINE-001`,
`QUEUE-WAIT-001`, `SPOF-001`.

Then repeat with `run_fixed_demo.sh` and compare:

```sh
.venv/bin/rtarch compare examples/logs/real_qnx_flawed.log \
                       examples/logs/real_qnx_fixed.log \
                       --scenario scenarios/brake_demo.json \
                       --output examples/reports/real_qnx_comparison.html
```

---

## 9. Tuning for real hardware

The artificial delays in `brake_controller` (`BRAKE_DELAY_MS`,
`LOWPRIO_DELAY_MS`) and the message periods in the clients are the knobs. The
C code is a **log generator**; the architecture under test is the *message
topology and scheduling*, not the delays.

If real QNX timing shifts the metrics:

1. Look at the node/edge tables in the report.
2. Adjust `scenarios/brake_demo.json` (`deadline_ms`, `max_in_degree`,
   `low_priority_work_ratio`, `queue_wait_ratio`, `blocked_queue_wait_ratio`).
3. Re-run the CLI. **Never tune thresholds in the code.**

## 10. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| licence still "Available" | step 2/3 of section 1 not done |
| QNX Software Center shows no products | licence not deployed to your user |
| `slog2_register` fails | `slogger2` not started; run `slogger2 &` in the guest |
| `ConnectAttach` fails | server not up yet; `rtarch_open` retries for 5 s |
| no RTARCH lines in `slog2info` | buffer set name mismatch; check `rtarch_init` |
| `pthread_setschedparam` fails | needs privileges; the demo still logs the intended priority |
| `MsgReceive` returns -1 | `EINTR` is handled; anything else is logged to stderr |
| parser finds 0 events | confirm the log actually contains lines starting with `RTARCH` |
| `mkqnximage --run` needs a display | QEMU mode is headless; use the guest desktop or SSH |
