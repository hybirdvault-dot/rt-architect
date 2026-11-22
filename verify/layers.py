#!/usr/bin/env python3
"""The six verification layers.  Each function returns CheckResults.

Nothing here reads documentation and assumes it is true: every check executes a
command or a parser call and inspects the real result.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verify.models import CheckResult, Scorecard

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.environ.get("RTARCH_PY", os.path.join(REPO, ".venv", "bin", "python"))


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _run(cmd, cwd=REPO, timeout=300):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)


def _tool(name):
    """Locate a dev tool, installing it into .verify-venv if it is missing."""
    found = shutil.which(name)
    if found:
        return found
    venv = os.path.join(REPO, ".verify-venv")
    candidate = os.path.join(venv, "bin", name)
    if os.path.exists(candidate):
        return candidate
    subprocess.run([sys.executable, "-m", "venv", venv], check=True, capture_output=True)
    subprocess.run([os.path.join(venv, "bin", "pip"), "install", "-q", name],
                   check=True, capture_output=True)
    return candidate


def _add(scorecard, layer, name, ok, severity, evidence, warn=False):
    scorecard.add(CheckResult(layer, name, "WARN" if warn and ok else ("PASS" if ok else "FAIL"),
                              severity, evidence[-600:]))


# --------------------------------------------------------------------- layer 1
def layer1(scorecard: Scorecard) -> None:
    os.chdir(REPO)

    # commit count claim
    overview = _read(os.path.join(REPO, "docs", "project_overview.md"))
    m = re.search(r"(\d+)\s+commits", overview)
    if m:
        claimed = int(m.group(1))
        actual = int(_run(["git", "rev-list", "--count", "HEAD"]).stdout.strip())
        _add(scorecard, 1, "commit-count claim", abs(claimed - actual) <= 1, "P2",
             f"claimed {claimed}, actual {actual} (the doc-updating commit shifts this by one)")
    else:
        _add(scorecard, 1, "commit-count claim", True, "info", "no brittle numeric claim present")

    # test count claim
    readme = _read(os.path.join(REPO, "README.md"))
    m = re.search(r"(\d+)\s+tests", readme)
    collected = _run([PY, "-m", "pytest", "--collect-only", "-q"]).stdout
    per_file = [int(x) for x in re.findall(r":\s*(\d+)\s*$", collected, re.MULTILINE)]
    summary = re.search(r"(\d+)\s+tests? collected", collected)
    n_collected = sum(per_file) if per_file else (int(summary.group(1)) if summary else 0)
    if m:
        _add(scorecard, 1, "test-count claim", int(m.group(1)) == n_collected, "P2",
             f"claimed {m.group(1)}, collected {n_collected}")

    # documented quick-start command
    bad = [ln.strip() for ln in readme.splitlines()
           if "rtarch " in ln and "analyze" not in ln and "compare" not in ln
           and "--help" not in ln and not ln.strip().startswith("Usage:")
           and "rtarch [OPTIONS]" not in ln]
    _add(scorecard, 1, "documented command includes subcommand", not bad, "P0",
         "bare commands: " + "; ".join(bad) if bad else "all documented commands use a subcommand")

    # quoted log line provenance
    m = re.search(r"(Nov \d+ \d+:\d+:\d+\.\d+.*?RTARCH v=1[^\n`]*)", overview)
    if m:
        line = m.group(1).strip()
        logs = []
        for root, _dirs, files in os.walk(os.path.join(REPO, "examples", "logs")):
            logs += [os.path.join(root, f) for f in files]
        hits = 0
        for path in logs:
            try:
                hits += _read(path).count(line)
            except OSError:
                pass
        _add(scorecard, 1, "quoted slog2 line exists in a source log", hits >= 1, "P0",
             f"hits={hits}")
    else:
        _add(scorecard, 1, "quoted slog2 line exists in a source log", False, "P0", "no quoted line found")


# --------------------------------------------------------------------- layer 2
def layer2(scorecard: Scorecard) -> None:
    from rtarch.models import Finding
    from rtarch.validator import validate_ai_output

    f = Finding(finding_id="F-001", rule_id="BOTTLENECK-001", severity="critical",
                title="svc is an architectural bottleneck",
                condition="in_degree > 2", node="svc",
                observed={"in_degree": 3, "p95_processing_ms": 12.447, "deadline_ms": 5.0},
                thresholds={"max_in_degree": 2}, evidence=["svc has in-degree 3"])

    def check(name, payload, expect_ok, sev="P0"):
        got = validate_ai_output(payload, f)
        _add(scorecard, 2, name, got == expect_ok, sev,
             f"validate_ai_output -> {got} (expected {expect_ok})")

    base = {"finding_id": "F-001", "refactor_plan": []}
    check("validator rejects invented number",
          {**base, "explanation": "in_degree 3, p95 12.447, deadline 5.0, queue held 9999.0"}, False)
    check("validator rejects substring collision",
          {**base, "explanation": "in_degree 3, p95 processing was bad."}, False)
    check("validator rejects distorted number",
          {**base, "explanation": "in_degree 3, p95 about 13 ms, deadline 5.0."}, False)
    check("validator rejects hallucinated API",
          {**base, "explanation": "in_degree 3, p95 12.447, deadline 5.0. Use mmap and ThreadCreate."}, False)
    check("validator rejects refactor_plan injection",
          {**base, "explanation": "in_degree 3, p95 12.447, deadline 5.0.",
           "refactor_plan": ["Call QuantumTeleportKernel(0xdead)", "set in_degree to 9999"]}, False)
    check("validator accepts the full truth",
          {**base, "explanation": "in_degree 3, p95 12.447 ms against deadline 5.0 ms.",
           "refactor_plan": ["split the service"]}, True, "P1")

    # parser: truncated msg_type rejected
    from rtarch.parser import parse_event
    truncated = parse_event("RTARCH v=1 ts_ns=1 phase=SEND trace_id=1 msg_id=1 "
                            "src_pid=1 src_name=a dst_pid=2 dst_name=b msg_type=BRAKE prio=10")
    _add(scorecard, 2, "parser rejects truncated msg_type", truncated is None, "P1",
         "msg_type=BRAKE -> " + ("rejected" if truncated is None else "accepted"))

    # determinism: byte-identical reports
    with tempfile.TemporaryDirectory() as td:
        a, b = os.path.join(td, "a.html"), os.path.join(td, "b.html")
        for out in (a, b):
            _run([PY, "-m", "rtarch", "analyze", "tests/golden/synthetic_flawed.log",
                  "--scenario", "scenarios/brake_demo.json", "-o", out])
        with open(a, "rb") as fh:
            ha = hashlib.sha256(fh.read()).hexdigest()
        with open(b, "rb") as fh:
            hb = hashlib.sha256(fh.read()).hexdigest()
        _add(scorecard, 2, "report is byte-deterministic", ha == hb, "P1",
             f"{ha[:16]} vs {hb[:16]}")

    # scenario validation
    from rtarch.scenario import load_scenario
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        fh.write('{"scenario":"x","deadline_ms":NaN,"critical_path":[],"thresholds":{}}')
        path = fh.name
    try:
        load_scenario(path)
        _add(scorecard, 2, "scenario NaN rejected", False, "P1", "NaN was accepted")
    except (ValueError, TypeError) as exc:
        _add(scorecard, 2, "scenario NaN rejected", True, "P1", f"rejected: {exc}")
    finally:
        os.unlink(path)


# --------------------------------------------------------------------- layer 3
def layer3(scorecard: Scorecard) -> None:
    build = os.path.join(REPO, "target", "linux_sim")
    r = _run(["make", "clean"], cwd=build)
    r = _run(
        [
            "make",
            ("CFLAGS=-Wall -Wextra -Werror -D_GNU_SOURCE -DRTARCH_SIM -O2 "
             "-Iinclude -I../qnx8_demo/include"),
        ],
        cwd=build,
        timeout=300,
    )
    _add(scorecard, 3, "sim compiles with -Wall -Wextra -Werror", r.returncode == 0, "P1",
         r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "clean build")

    sim = os.path.join(build, "rtarch_sim")
    if not os.path.exists(sim):
        _add(scorecard, 3, "sim shutdown (4 cases)", False, "P0", "sim binary missing")
        return

    cases = [("", "INT"), ("", "TERM"), ("fixed", "INT"), ("fixed", "TERM")]
    for mode, sig in cases:
        proc = subprocess.Popen([sim] + ([mode] if mode else []),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=build)
        import time
        time.sleep(1.2)
        proc.send_signal(2 if sig == "INT" else 15)
        try:
            proc.wait(timeout=2.0)
            ok = proc.returncode is not None
            ev = f"exited (rc={proc.returncode})"
        except subprocess.TimeoutExpired:
            ok = False
            ev = "still alive after 2 s"
            proc.kill()
            proc.wait()
        _add(scorecard, 3, f"sim shutdown {mode or 'flawed'}/{sig}", ok, "P0", ev)


# --------------------------------------------------------------------- layer 4
def layer4(scorecard: Scorecard) -> None:
    ruff = _tool("ruff")
    mypy = _tool("mypy")
    r = _run([ruff, "check", ".", "--exclude", ".venv"])
    _add(scorecard, 4, "ruff clean", r.returncode == 0, "P1",
         r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "clean")
    r = _run([mypy, "rtarch/", "--ignore-missing-imports"])
    _add(scorecard, 4, "mypy clean", r.returncode == 0, "P1",
         r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "clean")

    lock = any(os.path.exists(os.path.join(REPO, f)) for f in
               ("uv.lock", "requirements.lock", "poetry.lock", "Pipfile.lock"))
    _add(scorecard, 4, "lockfile present", lock, "P1",
         "found" if lock else "no lockfile")

    r = _run(["git", "ls-files"])
    tracked = r.stdout.split()
    elfs = []
    for path in tracked:
        full = os.path.join(REPO, path)
        if os.path.isfile(full):
            try:
                with open(full, "rb") as fh:
                    if fh.read(4) == b"\x7fELF":
                        elfs.append(path)
            except OSError:
                pass
    _add(scorecard, 4, "no ELF binaries tracked", not elfs, "P1", "none" if not elfs else ", ".join(elfs))

    gi = _read(os.path.join(REPO, ".gitignore"))
    _add(scorecard, 4, ".gitignore covers target bin", "target/qnx8_demo/bin/" in gi, "P1",
         "covered" if "target/qnx8_demo/bin/" in gi else "missing")


# --------------------------------------------------------------------- layer 5
def layer5(scorecard: Scorecard) -> None:
    with tempfile.TemporaryDirectory() as td:
        clone = os.path.join(td, "fresh")
        r = _run(["git", "clone", "-q", REPO, clone])
        if r.returncode != 0:
            _add(scorecard, 5, "fresh clone", False, "P0", r.stderr[-200:])
            return
        venv = os.path.join(clone, ".venv")
        _run([sys.executable, "-m", "venv", venv], timeout=180)
        py = os.path.join(venv, "bin", "python")
        r = _run([py, "-m", "pip", "install", "-q", "-e", "."], cwd=clone, timeout=600)
        _add(scorecard, 5, "documented install succeeds", r.returncode == 0, "P1", f"rc={r.returncode}")

        r = _run([os.path.join(venv, "bin", "rtarch"), "analyze",
                  "tests/golden/synthetic_flawed.log", "--scenario", "scenarios/brake_demo.json",
                  "-o", "report.html"], cwd=clone)
        _add(scorecard, 5, "documented quick-start command exits 0", r.returncode == 0, "P0",
             f"rc={r.returncode}")

        r = _run([py, "-m", "pip", "install", "-q", "-e", ".[dev]"], cwd=clone, timeout=300)
        r = _run([py, "-m", "pytest", "-q"], cwd=clone, timeout=300)
        _add(scorecard, 5, "pytest passes after .[dev]", r.returncode == 0, "P1",
             r.stdout.strip().splitlines()[-1] if r.stdout.strip() else f"rc={r.returncode}")


# --------------------------------------------------------------------- layer 6
def layer6(scorecard: Scorecard) -> None:
    reports = sorted(os.path.join(REPO, "examples", "reports", f)
                     for f in os.listdir(os.path.join(REPO, "examples", "reports"))
                     if f.endswith(".html"))
    for path in reports:
        html = _read(path)
        name = os.path.basename(path)
        has_prov = "SHA-256" in html
        _add(scorecard, 6, f"provenance footer: {name}", has_prov, "P1",
             "present" if has_prov else "missing")

    # the real-QNX flawed report must reproduce from its source log
    import difflib
    src = os.path.join(REPO, "examples", "logs", "real_qnx_flawed_slog2.txt")
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "r.html")
        _run([PY, "-m", "rtarch", "analyze", src, "--scenario", "scenarios/brake_demo.json",
              "-o", out])
        committed = _read(os.path.join(REPO, "examples", "reports", "real_qnx_flawed.html"))
        regen = _read(out)
        same = committed == regen
        _add(scorecard, 6, "real_qnx_flawed.html reproduces", same, "P1",
             "identical" if same else f"diff of {sum(1 for _ in difflib.unified_diff(committed.splitlines(), regen.splitlines()))} lines")




# --------------------------------------------------------------------- extras
_UNKNOWN_KIND_C = r'''
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
#include <time.h>
#include "rtarch_ipc.h"
extern int brake_controller_entry(int argc, char **argv);
extern int brake_controller_fixed_entry(int argc, char **argv);
static int g_coid = -1;
static void *server(void *arg)
{
    int (*entry)(int, char **) = arg;
    return (void *)(long)entry(0, NULL);
}
int main(int argc, char **argv)
{
    const char *name = argc > 1 ? argv[1] : "brake_controller";
    int (*entry)(int, char **) = strcmp(name, "brake_controller_fixed") == 0
                                     ? brake_controller_fixed_entry : brake_controller_entry;
    pthread_t th;
    rtarch_payload_t req;
    rtarch_reply_t rep;
    struct timespec t0, t1;
    long us;
    long rc;
    int pid = 0;
    pthread_create(&th, NULL, server, entry);
    usleep(800000);
    { int coid = rtarch_open((char *)name, &pid);
      if (coid < 0) { printf("OPENFAIL\n"); return 2; }
      g_coid = coid; }
    memset(&req, 0, sizeof(req)); memset(&rep, 0, sizeof(rep));
    req.kind = 99;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    rc = MsgSend(g_coid, &req, sizeof(req), &rep, sizeof(rep));
    clock_gettime(CLOCK_MONOTONIC, &t1);
    us = (t1.tv_sec - t0.tv_sec) * 1000000L + (t1.tv_nsec - t0.tv_nsec) / 1000L;
    printf("unknown rc=%ld us=%ld\n", rc, us);
    if (rc != ENOTSUP || us > 50000) { return 1; }
    memset(&req, 0, sizeof(req)); memset(&rep, 0, sizeof(rep));
    req.kind = RTARCH_KIND_BRAKE_CMD;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    rc = MsgSend(g_coid, &req, sizeof(req), &rep, sizeof(rep));
    clock_gettime(CLOCK_MONOTONIC, &t1);
    us = (t1.tv_sec - t0.tv_sec) * 1000000L + (t1.tv_nsec - t0.tv_nsec) / 1000L;
    printf("valid rc=%ld us=%ld\n", rc, us);
    return (rc == 0 && us < 50000) ? 0 : 1;
}
'''


def layer7_extras(scorecard: Scorecard) -> None:
    """Checks added after the independent re-verification (B2)."""

    # L3.7 — unknown message kind must be rejected fast by the real controllers
    build = os.path.join(REPO, "target", "linux_sim")
    sim = os.path.join(build, "rtarch_sim")
    if not os.path.exists(sim):
        _add(scorecard, 7, "L3.7 unknown-kind rejected fast (both controllers)", False, "P1",
             "sim not built")
    else:
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "uk.c")
            with open(src, "w") as fh:
                fh.write(_UNKNOWN_KIND_C)
            binary = os.path.join(td, "uk")
            objs = [os.path.join(build, o) for o in
                    ("brake_controller.o", "brake_controller_fixed.o", "shim.o")]
            comp = _run(["gcc", "-D_GNU_SOURCE", "-DRTARCH_SIM", "-O2",
                         "-I" + os.path.join(build, "include"),
                         "-I" + os.path.join(REPO, "target", "qnx8_demo", "include"),
                         src, *objs, "-o", binary, "-lpthread", "-lrt"], timeout=120)
            if comp.returncode != 0:
                _add(scorecard, 7, "L3.7 unknown-kind rejected fast (both controllers)",
                     False, "P1", comp.stderr[-200:])
            else:
                outs = []
                for name in ("brake_controller", "brake_controller_fixed"):
                    r = _run([binary, name], timeout=60)
                    outs.append(f"{name}: rc={r.returncode} {r.stdout.strip().splitlines()[:1]}")
                ok = all("rc=0" in o for o in outs)
                _add(scorecard, 7, "L3.7 unknown-kind rejected fast (both controllers)",
                     ok, "P1", " | ".join(outs))

    # M3.9 — the report's node p95 equals the pooled p95 recomputed from samples
    import html as _html
    import re as _re
    src_log = os.path.join(REPO, "examples", "logs", "real_qnx_flawed_slog2.txt")
    report = os.path.join(REPO, "examples", "reports", "real_qnx_flawed.html")
    if os.path.exists(report) and os.path.exists(src_log):
        from rtarch.metrics import percentile
        from rtarch.parser import parse_log
        events = parse_log(src_log)
        # processing samples: pair RECV/REPLY per triple via the metrics module
        from rtarch.metrics import _completed_triples, group_triples
        proc = [r.ts_ns - v.ts_ns for _s, v, r in _completed_triples(group_triples(events))
                if v.dst_name == "brake_controller"]
        pooled = percentile(proc, 95) / 1e6 if proc else 0.0
        text = _re.sub(r"<[^>]+>", " ", _read(report))
        text = _html.unescape(_re.sub(r"\s+", " ", text))
        m = _re.search(r"brake_controller 3 0 ([\d.]+)", text)
        reported = float(m.group(1)) if m else -1.0
        _add(scorecard, 7, "M3.9 report node p95 == pooled p95",
             abs(pooled - reported) < 0.01, "P1",
             f"pooled {pooled:.3f} ms vs reported {reported:.3f} ms")

    # M3.2 — trace ids are unique per request (no cross-edge reuse)
    if os.path.exists(src_log):
        seen = {}
        collisions = 0
        for e in parse_log(src_log):
            key = (e.trace_id, e.msg_id)
            edge = tuple(sorted((e.src_name, e.dst_name)))
            if key in seen and seen[key] != edge:
                collisions += 1
            seen[key] = edge
        _add(scorecard, 7, "M3.2 no cross-edge (trace_id,msg_id) reuse",
             collisions == 0, "P1", f"{collisions} collisions over {len(seen)} triples")

    # L3.6 — every service checks pthread_setschedparam and logs failure
    services = ["brake_controller", "brake_controller_fixed", "perception_service",
                "sensor_service", "telemetry_client", "diagnostics_client"]
    unchecked = []
    for svc in services:
        body = _read(os.path.join(REPO, "target", "qnx8_demo", svc, "main.c"))
        if "pthread_setschedparam" not in body or "if (pthread_setschedparam" not in body:
            unchecked.append(svc)
    _add(scorecard, 7, "L3.6 pthread_setschedparam return checked in all 6 services",
         not unchecked, "P1", "all checked" if not unchecked else "unchecked: " + ", ".join(unchecked))

    # L3.5 — registered name == called name in the demo scripts
    reg = set()
    for svc in ("brake_controller_fixed",):
        body = _read(os.path.join(REPO, "target", "qnx8_demo", svc, "main.c"))
        reg.update(re.findall(r'name_attach\(NULL,\s*"([^"]+)"', body))
    script = _read(os.path.join(REPO, "target", "qnx8_demo", "scripts", "run_fixed_demo.sh"))
    called = set(re.findall(r"(rtarch/brake_(?:fast|slow))", script))
    _add(scorecard, 7, "L3.5 registered name == called name", reg == called, "P1",
         f"registered {sorted(reg)} called {sorted(called)}")

    # L3.8 — A/B parity: both variants use 1 ms / 8 ms
    flawed = _read(os.path.join(REPO, "target", "qnx8_demo", "brake_controller", "main.c"))
    fixed = _read(os.path.join(REPO, "target", "qnx8_demo", "brake_controller_fixed", "main.c"))
    f_ok = ("BRAKE_DELAY_MS      1" in flawed or "BRAKE_DELAY_MS 1" in flawed) and "LOWPRIO_DELAY_MS    8" in flawed
    x_ok = "FAST_DELAY_MS   1" in fixed and "SLOW_DELAY_MS   8" in fixed
    _add(scorecard, 7, "L3.8 A/B parity (both variants 1 ms / 8 ms)", f_ok and x_ok, "P1",
             f"flawed 1/8={f_ok} fixed 1/8={x_ok}")

    # M3.13 — comparison view styles zero deltas neutral, not red
    tmpl = _read(os.path.join(REPO, "rtarch", "templates", "comparison_report.html.j2"))
    has_neutral = "delta-neutral" in tmpl and "delta_class" in tmpl
    _add(scorecard, 7, "M3.13 zero deltas styled neutral", has_neutral, "P1",
         "delta_class + delta-neutral present" if has_neutral else "missing")


_UNBLOCK_C = r'''
#include <stdio.h>
#include <signal.h>
#include <pthread.h>
#include <time.h>
#include <unistd.h>
#include "rtarch_ipc.h"

static int g_chid;
static volatile int g_woke = 0;

static void *receiver(void *arg)
{
    (void)arg;
    char buf[64];
    struct _msg_info info;
    int rcvid = MsgReceive(g_chid, buf, sizeof(buf), &info);
    if (rcvid < 0) {
        g_woke = 1;              /* woken by the signal */
    }
    return NULL;
}

int main(void)
{
    pthread_t th;
    struct timespec t0, t1;
    long us;
    int i;

    signal(SIGINT, rtarch_on_signal);
    g_chid = rtarch_channel_create();
    pthread_create(&th, NULL, receiver, NULL);
    usleep(200000);

    clock_gettime(CLOCK_MONOTONIC, &t0);
    raise(SIGINT);
    for (i = 0; i < 200 && !g_woke; i++) {
        usleep(10000);
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    us = (t1.tv_sec - t0.tv_sec) * 1000000L + (t1.tv_nsec - t0.tv_nsec) / 1000L;
    printf("woke=%d us=%ld\n", g_woke, us);
    return (!g_woke || us > 50000) ? 1 : 0;
}
'''


def _run_unblock_test(header_path):
    """Compile and run the unblock test against the current header."""
    build = os.path.join(REPO, "target", "linux_sim")
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "ub.c")
        binary = os.path.join(td, "ub")
        with open(src, "w") as fh:
            fh.write(_UNBLOCK_C)
        comp = _run(["gcc", "-D_GNU_SOURCE", "-DRTARCH_SIM", "-O2",
                     "-I" + os.path.join(build, "include"),
                     "-I" + os.path.join(REPO, "target", "qnx8_demo", "include"),
                     src, os.path.join(build, "shim.o"), "-o", binary,
                     "-lpthread", "-lrt"], timeout=120)
        if comp.returncode != 0:
            return 1, comp.stderr[-200:]
        r = _run([binary], timeout=30)
        return r.returncode, r.stdout.strip()


def layer8_mutation(scorecard: Scorecard) -> None:
    """L0.3 — the harness must discriminate on P0-3's unblock mechanism."""

    header = os.path.join(REPO, "target", "qnx8_demo", "include", "rtarch_ipc.h")
    original = _read(header)
    try:
        base_rc, base_out = _run_unblock_test(header)
        mutated = original.replace("_NTO_CHF_UNBLOCK", "0")
        with open(header, "w") as fh:
            fh.write(mutated)
        mut_rc, mut_out = _run_unblock_test(header)
    finally:
        with open(header, "w") as fh:
            fh.write(original)

    ok = base_rc == 0 and mut_rc != 0
    _add(scorecard, 8, "L0.3 P0-3 unblock mechanism discriminates (mutation flips)",
         ok, "P0",
         f"baseline rc={base_rc} ({base_out}); mutated rc={mut_rc} ({mut_out})")


def _queue_wait_count():
    """How many QUEUE-WAIT findings the real QNX flawed log produces."""
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "r.html")
        _run([PY, "-m", "rtarch", "analyze",
              os.path.join(REPO, "examples", "logs", "real_qnx_flawed_slog2.txt"),
              "--scenario", "scenarios/brake_demo.json", "-o", out])
        return _read(out).count("QUEUE-WAIT-001")


def layer9_mutations(scorecard: Scorecard) -> None:
    """L0.1 / L0.2 — the harness must notice when P0-2 or P1-1 is reverted."""

    # L0.1: break the validator's number check -> the validator tests must fail.
    validator = os.path.join(REPO, "rtarch", "validator.py")
    original = _read(validator)
    try:
        with open(validator, "w") as fh:
            fh.write(original.replace("    return (not violations), violations",
                                      "    return True, []"))
        r = _run([PY, "-m", "pytest", "tests/test_ai_validator.py", "-q", "--no-header"],
                 timeout=300)
        failed = r.returncode != 0
    finally:
        with open(validator, "w") as fh:
            fh.write(original)
    _add(scorecard, 9, "L0.1 P0-2 revert -> tests fail", failed, "P0",
         "number check disabled -> pytest failed" if failed
         else "number check disabled but pytest still passed")

    # L0.2: revert the dedup key -> the per-edge QUEUE-WAIT findings collapse.
    rules = os.path.join(REPO, "rtarch", "rules.py")
    original = _read(rules)
    try:
        with open(rules, "w") as fh:
            fh.write(original.replace(
                "        key = (finding.rule_id, finding.node, finding.title)",
                "        key = (finding.rule_id, finding.node)"))
        mutated_count = _queue_wait_count()
    finally:
        with open(rules, "w") as fh:
            fh.write(original)
    baseline_count = _queue_wait_count()
    _add(scorecard, 9, "L0.2 P1-1 revert -> per-edge findings collapse",
         baseline_count == 3 and mutated_count == 1, "P0",
         f"baseline QUEUE-WAIT={baseline_count}, reverted={mutated_count} (want 3 vs 1)")



LAYERS = {1: layer1, 2: layer2, 3: layer3, 4: layer4, 5: layer5, 6: layer6,
          7: layer7_extras, 8: layer8_mutation, 9: layer9_mutations}
