# QNX 8.0 + QEMU setup and log extraction

This guide covers how to get a real `RTARCH` log out of a QNX 8.0 QEMU target
and into the host analysis tool.

> **Status of this document:** the QNX API usage in `target/qnx8_demo/` was
> verified against the official QNX 8.0 library reference. The QEMU boot and
> extraction steps below are the standard QNX Everywhere workflow but were **not
> executed in this environment** (no QNX SDP, no QEMU, no sudo here). Expect to
> adjust image names and paths to the BSP you download.

---

## 1. Install QNX 8.0 SDP

**Option A — QNX Everywhere (free, recommended)**

1. Register at <https://www.qnx.com/everywhere/> (free developer licence).
2. Download the **QNX SDP 8.0** for Linux (x86_64 host).
3. Run the installer:

   ```sh
   chmod +x qnx800-linux-x86_64-installer.run
   ./qnx800-linux-x86_64-installer.run
   # default install: /opt/qnx800
   ```

4. Source the environment:

   ```sh
   source /opt/qnx800/qnxsdp-env.sh
   which qcc    # /opt/qnx800/host/linux/x86_64/usr/bin/qcc
   ```

**Option B — QNX SDP evaluation**

QNX occasionally offers a time-limited evaluation SDP. Same install steps.

## 2. Install QEMU

**Without root (recommended on Deepin/UOS, where sudo needs a password):**

```sh
bash scripts/setup_qemu_local.sh
~/rt-architect-tools/qemu/bin/qemu-system-x86_64 --version
```

This downloads the `.deb` packages and extracts them into
`~/rt-architect-tools/qemu`, so no system-wide install is needed.

**With root:**

```sh
sudo apt-get update
sudo apt-get install qemu-system-x86 qemu-system-arm qemu-utils
qemu-system-x86_64 --version
```

KVM acceleration is recommended (check `/dev/kvm` exists). Without KVM the demo
still runs, just slower.

## 3. Get a QNX QEMU image

QNX Everywhere / the QNX SDP download page provides a **QEMU BSP** (for x86_64
or ARM). It typically contains:

- a bootable disk image (e.g. `.hdd` / `.qcow2`),
- a QNX IFS (initial filesystem image),
- a launch script or `qemu` command line.

If your BSP ships a launch script, use it. Otherwise a minimal x86_64 launch
looks like:

```sh
qemu-system-x86_64 \
  -m 512 \
  -drive file=qnx80-hdd.img,format=raw,if=ide \
  -nographic \
  -serial file:/tmp/qnx_serial.txt \
  -netdev user,id=n0,hostfwd=tcp::2222-:22 \
  -device e1000,netdev=n0
```

Boot the guest and log in as `root` (no password on most QNX demo images).

## 4. Build and copy the demo

On the host:

```sh
cd target/qnx8_demo
source /opt/qnx800/qnxsdp-env.sh
make
```

Copy the five binaries into the guest. With `hostfwd` above and sshd running in
the guest:

```sh
sshpass -p '' scp -P 2222 sensor_service perception_service brake_controller \
    telemetry_client diagnostics_client root@127.0.0.1:/tmp/
```

Or attach the binaries to the guest filesystem image, or use a 9p shared folder.

## 5. Run the demo

In the guest:

```sh
cd /tmp
sh scripts/run_flawed_demo.sh     # starts services, runs 6 s, stops them
sh scripts/extract_slog2.sh       # slog2info > /tmp/raw_slog2.txt
```

## 6. Get the log onto the host

**Method A — serial console (simplest).** If you booted with
`-serial file:/tmp/qnx_serial.txt`, then in the guest:

```sh
slog2info > /dev/ser1        # dump the buffer straight to the serial port
```

The host file `/tmp/qnx_serial.txt` now contains the slog2 output.

**Method B — network copy.**

```sh
scp -P 2222 root@127.0.0.1:/tmp/raw_slog2.txt ./real_qnx_flawed.log
```

**Method C — copy-paste.** For a short run, open the serial console and copy the
`slog2info` output directly into a host file. This is fine for a demo.

## 7. Analyse on the host

```sh
.venv/bin/rtarch real_qnx_flawed.log \
  -s scenarios/brake_demo.json \
  -o real_report.html
```

Expected: `BOTTLENECK-001`, `CRITICAL-PATH-001`, `HEAD-OF-LINE-001`,
`QUEUE-WAIT-001`, `SPOF-001`.

---

## 8. Tuning for real hardware

The artificial delays in `brake_controller` (`BRAKE_DELAY_MS`,
`LOWPRIO_DELAY_MS`) and the message periods in the clients are the knobs. The
C code is a **log generator**; the architecture under test is the *message
topology and scheduling*, not the delays.

If real QNX timing shifts the metrics:

1. Look at the node/edge tables in the report.
2. Adjust `scenarios/brake_demo.json` (`deadline_ms`, `max_in_degree`,
   `low_priority_work_ratio`, `queue_wait_ratio`, `blocked_queue_wait_ratio`).
3. Re-run the CLI. **Never tune thresholds in the code.**

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `slog2_register` fails | slog2 not started; run `slogger2 &` in the guest |
| `ConnectAttach` fails | server not up yet; `rtarch_connect` retries for 10 s |
| no RTARCH lines in `slog2info` | buffer set name mismatch; check `rtarch_init` |
| `pthread_setschedparam` fails | needs privileges; the demo still logs the intended priority |
| `MsgReceive` returns -1 | `EINTR` is handled; anything else is logged to stderr |
| parser finds 0 events | confirm the log actually contains lines starting with `RTARCH` |
