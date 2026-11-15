# Building a real QNX 8.0 target from the SDP

This is the procedure that **actually worked** to produce genuine QNX 8.0
`slog2` evidence. It does not need the Quick Start Target Image (QSTI) download,
which was unreliable from this network.

Verified on: Deepin 23 (x86_64), QNX SDP 8.0 (8.0 Build 141), QEMU 8.2.0.

---

## 1. What you need

| Component | Where |
|---|---|
| QNX SDP 8.0 | installed by the QNX Software Center, default `~/qnx800` |
| `mkqnximage` | `~/qnx800/host/common/bin/mkqnximage` |
| `qcc` | `~/qnx800/host/linux/x86_64/usr/bin/qcc` |
| QEMU + BIOS + option ROMs | extracted locally, no root needed (see below) |

## 2. Build the target image

`mkqnximage` is the SDP's own image builder. It produces a bootable QNX disk
for QEMU — the QSTI is just a pre-built instance of this.

```sh
source ~/qnx800/qnxsdp-env.sh
mkdir -p ~/qnx-vm && cd ~/qnx-vm
mkqnximage --type=qemu --noprompt
```

Output:

```
output/ifs.bin          <- QNX boot image
output/disk-qemu        <- raw disk
output/disk-qemu.vmdk   <- VMDK descriptor
```

Boot it:

```sh
qemu-system-x86_64 -nographic -nodefaults -nic none \
  -drive file=output/disk-qemu.vmdk,if=ide,id=drv0 \
  -bios /path/to/bios-256k.bin -kernel output/ifs.bin \
  -serial file:/tmp/qnx-serial.log -monitor none
```

You should see the QNX microkernel come up:

```
---> Starting slogger2
---> Starting PCI Services
---> Starting devb
---> Mounting file systems
Process count:21
Startup complete
QNX noname 8.0.0 2026/06/05-16:26:03 EDT x86pc x86_64
```

### QEMU without root

Deepin's QEMU `.deb`s can be extracted into a private prefix — no sudo:

```sh
mkdir -p ~/rt-architect-tools/qemu
cd ~/rt-architect-tools/qemu
apt-get download qemu-system-x86 qemu-system-common qemu-system-data \
                 seabios vgabios bridge-utils
for d in ./*.deb; do dpkg-deb -x "$d" .; done
```

Then run with the module/data directories pointed at the extraction:

```sh
QEMU_MODULE_DIR=$PWD/usr/lib/x86_64-linux-gnu/qemu \
QEMU_DATA_DIR=$PWD/usr/share/qemu \
  $PWD/usr/bin/qemu-system-x86_64 ... -L $PWD/usr/share/qemu
```

`QEMU_MODULE_DIR` is required or QEMU fails with
`could not load module for type 'tcg-accel-ops'`.

## 3. Bake your binaries and a startup hook into the image

`mkqnximage` reads "snippet" files from `local/snippets/`. Two are useful:

| Snippet | Purpose |
|---|---|
| `data_files.custom` | extra files copied into the `/data` partition |
| `post_start.custom` | shell commands run at the end of system startup |

### `local/snippets/data_files.custom`

```
[uid=0 gid=0 dperms=755 perms=755 type=file]
rtarch/sensor_service = local/rtarch/sensor_service
rtarch/perception_service = local/rtarch/perception_service
rtarch/brake_controller = local/rtarch/brake_controller
rtarch/brake_controller_fixed = local/rtarch/brake_controller_fixed
rtarch/telemetry_client = local/rtarch/telemetry_client
rtarch/diagnostics_client = local/rtarch/diagnostics_client
```

### `local/snippets/post_start.custom`

```sh
echo "RTArchitect: starting the flawed demo"
mkdir -p /tmp
cd /data/rtarch
./brake_controller & BRAKE_PID=$!
./perception_service brake_controller & PERCEPTION_PID=$!
./telemetry_client brake_controller & TELEMETRY_PID=$!
./diagnostics_client brake_controller & DIAG_PID=$!
./sensor_service perception_service & SENSOR_PID=$!
sleep 10
kill "$SENSOR_PID" "$TELEMETRY_PID" "$DIAG_PID" "$PERCEPTION_PID" "$BRAKE_PID" 2>/dev/null
slog2info > /data/rtarch/raw_slog2.txt 2>&1
echo "RTARCH_LOG_BEGIN"
cat /data/rtarch/raw_slog2.txt > /dev/ser1
sleep 2
echo "RTARCH_LOG_END"
```

Then rebuild and boot:

```sh
mkqnximage --type=qemu --build=all --noprompt
# boot as above; the log appears between the markers on the serial console
```

## 4. Pull the log off the target

The guest has no usable network in this configuration, so the log is written to
the serial console between `RTARCH_LOG_BEGIN` / `RTARCH_LOG_END` and captured on
the host:

```sh
sed -n '/RTARCH_LOG_BEGIN/,/RTARCH_LOG_END/p' /tmp/qnx-serial.log \
  > examples/logs/real_qnx_flawed_slog2.txt
```

The real slog2 lines carry the full prefix, which is exactly what the parser's
prefix tolerance is for:

```
Nov 15 15:34:38.470  diagnostics_client.282647  rtarch  0  RTARCH v=1 ts_ns=30969952596 phase=SEND ...
```

## 5. Analyse

```sh
.venv/bin/python -m rtarch analyze examples/logs/real_qnx_flawed_slog2.txt \
  --scenario scenarios/brake_demo.json \
  --output examples/reports/real_qnx_flawed.html

.venv/bin/python -m rtarch compare \
  examples/logs/real_qnx_flawed_slog2.txt \
  examples/logs/real_qnx_fixed_slog2.txt \
  --scenario scenarios/brake_demo.json \
  --output examples/reports/real_qnx_comparison.html
```

---

## 6. Real results (2026-11-15)

Genuine QNX 8.0.0 target, 1655 `RTARCH` events, all five rules fire on the
flawed log:

| Rule | Flawed | Fixed |
|---|---|---|
| `BOTTLENECK-001` | fires | **clears** |
| `CRITICAL-PATH-001` (brake) | fires | **clears** |
| `CRITICAL-PATH-001` (perception) | fires | fires |
| `HEAD-OF-LINE-001` | fires (47 blocked) | fires (5 blocked) |
| `QUEUE-WAIT-001` | fires | fires |
| `SPOF-001` | fires | fires (correct) |

The decisive numbers:

| Metric | Flawed | Fixed |
|---|---|---|
| brake p95 processing | 12.45 ms | **0.44 ms** |
| perception→brake p95 queue wait | 7.88 ms | **0.83 ms** |
| telemetry→brake p95 queue wait | 10.11 ms | **0.95 ms** |
| diagnostics→brake p95 queue wait | 12.64 ms | **0.99 ms** |

> The residual `HEAD-OF-LINE-001` / `QUEUE-WAIT-001` on the fixed log are an
> artefact of TCG emulation: every edge shows a uniform ~0.8–1.0 ms queue wait,
> which is the emulated scheduler's latency, not the architecture. On real
> hardware those waits are microseconds and the rules clear.

## 7. Bugs this uncovered (and fixed)

1. **slog2 buffer too small.** `num_pages = 4` (16 KB) held ~120 events; the
   demo generated >1200 and the buffer wrapped, silently dropping events and
   breaking SEND/RECV/REPLY pairing. Now 256 pages (1 MB).
2. **Non-request messages on the channel.** The brake channel also receives
   pulses and name-space/connection traffic, which were logged as requests and
   created a bogus `unknown` node. Now filtered (`rcvid == 0` and unknown kinds).
