"""Pydantic data models for the RTArchitect pipeline.

The wire format mirrors the locked RTARCH event schema (v1).  Nothing in this
module is allowed to change without a schema-version bump.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Phase(str, Enum):
    """The three IPC phases captured for every message."""

    SEND = "SEND"
    RECV = "RECV"
    REPLY = "REPLY"


class RTArchEvent(BaseModel):
    """One structured ``RTARCH`` log line."""

    v: int
    ts_ns: int
    phase: Phase
    trace_id: int
    msg_id: int
    src_pid: int
    src_name: str
    dst_pid: int
    dst_name: str
    msg_type: str
    prio: int


class EdgeMetrics(BaseModel):
    """Aggregated latency metrics for one directed service-to-service edge."""

    src_name: str
    dst_name: str
    msg_type: str
    count: int
    p50_queue_wait_ns: int
    p95_queue_wait_ns: int
    p99_queue_wait_ns: int
    p50_processing_ns: int
    p95_processing_ns: int
    p99_processing_ns: int
    p50_total_ns: int
    p95_total_ns: int
    p99_total_ns: int


class NodeMetrics(BaseModel):
    """Aggregated metrics for one service (graph node)."""

    name: str
    in_degree: int
    out_degree: int
    p95_processing_ns: int
    total_messages_received: int
    on_critical_path: bool = False
    high_priority_blocked_count: int = 0
    low_priority_work_ratio: float = 0.0


class Finding(BaseModel):
    """A deterministic, evidence-backed architectural finding."""

    finding_id: str
    rule_id: str
    deterministic: bool = True
    severity: str  # critical | warning | info
    title: str
    condition: str
    node: Optional[str] = None
    observed: Dict[str, object] = Field(default_factory=dict)
    thresholds: Dict[str, object] = Field(default_factory=dict)
    evidence: List[str] = Field(default_factory=list)
    recommendation: str = ""
    ai_explanation: Optional[str] = None
    ai_refactor_plan: Optional[List[str]] = None
