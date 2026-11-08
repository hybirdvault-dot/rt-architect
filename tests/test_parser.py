"""Parser tests, including the Threat-4 RTARCH pre-filter."""

import os

from rtarch.parser import parse_event, parse_log, parse_log_with_stats

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")
FLAWED_LOG = os.path.join(GOLDEN_DIR, "synthetic_flawed.log")


def test_parses_all_golden_events():
    events = parse_log(FLAWED_LOG)
    assert len(events) == 12


def test_first_event_fields():
    first = parse_log(FLAWED_LOG)[0]
    assert first.v == 1
    assert first.ts_ns == 1_000_000_000
    assert first.phase.value == "SEND"
    assert first.trace_id == 1001
    assert first.msg_id == 1
    assert first.src_pid == 101
    assert first.src_name == "sensor_service"
    assert first.dst_pid == 201
    assert first.dst_name == "perception_service"
    assert first.msg_type == "SENSOR_FRAME"
    assert first.prio == 25


def test_reply_event_reverses_direction():
    reply = parse_log(FLAWED_LOG)[2]
    assert reply.phase.value == "REPLY"
    assert reply.src_name == "perception_service"
    assert reply.dst_name == "sensor_service"
    assert reply.msg_type == "SENSOR_ACK"


def test_non_rtarch_lines_are_filtered(tmp_path):
    log = tmp_path / "noisy.log"
    log.write_text(
        "slog2: 09:37:10.000000 cpu=0 tid=1 process_start name=brake_controller\n"
        "RTARCH v=1 ts_ns=100 phase=SEND trace_id=1 msg_id=1 "
        "src_pid=1 src_name=a dst_pid=2 dst_name=b msg_type=X prio=10\n"
        "unrelated warning: something happened\n"
    )
    events = parse_log(str(log))
    assert len(events) == 1
    assert events[0].src_name == "a"


def test_malformed_rtarch_line_is_skipped(tmp_path):
    log = tmp_path / "bad.log"
    log.write_text(
        "RTARCH v=1 ts_ns=100 phase=SEND trace_id=1 msg_id=1 src_name=a\n"
        "RTARCH v=1 ts_ns=100 phase=SEND trace_id=1 msg_id=1 "
        "src_pid=1 src_name=a dst_pid=2 dst_name=b msg_type=X prio=10\n"
    )
    events, skipped = parse_log_with_stats(str(log))
    assert len(events) == 1
    assert skipped == 1


def test_empty_file_yields_no_events(tmp_path):
    log = tmp_path / "empty.log"
    log.write_text("")
    assert parse_log(str(log)) == []


def test_non_rtarch_line_is_rejected():
    assert parse_event("hello world") is None


def test_real_slog2_prefix_is_tolerated(tmp_path):
    log = tmp_path / "prefixed.log"
    log.write_text(
        "09:37:10.123456 1234 1 RTARCH v=1 ts_ns=100 phase=SEND trace_id=1 msg_id=1 "
        "src_pid=1 src_name=a dst_pid=2 dst_name=b msg_type=X prio=10\n"
    )
    events = parse_log(str(log))
    assert len(events) == 1
    assert events[0].ts_ns == 100
