"""Load and validate scenario configuration files.

Scenarios are the only source of thresholds, deadlines and critical-path
definitions.  Nothing about a specific service is hardcoded in the analysis
logic, which is what keeps the tool generic.

Scenario files are validated on load: a NaN, null or string where a number is
belongs is rejected immediately with a clear message rather than crashing (or
silently degrading) deep inside the rule engine.
"""

import json
import math

_THRESHOLD_KEYS = frozenset({
    "max_in_degree",
    "processing_deadline_fraction",
    "low_priority_work_ratio",
    "queue_wait_ratio",
    "spof_min_in_degree",
    "priority_threshold",
    "blocked_queue_wait_ratio",
})


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number, got {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number, got {value!r}")
    return float(value)


def _validate(scenario: dict) -> None:
    if not isinstance(scenario.get("scenario"), str) or not scenario["scenario"]:
        raise ValueError("scenario config must define a non-empty 'scenario' name")

    if "deadline_ms" not in scenario:
        raise ValueError("scenario config must define 'deadline_ms'")
    deadline = _finite_number(scenario["deadline_ms"], "deadline_ms")
    if deadline <= 0:
        raise ValueError(f"deadline_ms must be positive, got {deadline}")

    critical_path = scenario.get("critical_path", [])
    if not isinstance(critical_path, list) or not all(
        isinstance(name, str) for name in critical_path
    ):
        raise ValueError("critical_path must be a list of service names")

    thresholds = scenario.get("thresholds", {})
    if not isinstance(thresholds, dict):
        raise TypeError("thresholds must be a JSON object")
    for key, value in thresholds.items():
        if key not in _THRESHOLD_KEYS:
            raise ValueError(f"unknown threshold {key!r}")
        _finite_number(value, f"thresholds.{key}")


def load_scenario(path: str) -> dict:
    """Load a scenario JSON file and validate it."""
    with open(path, "r", encoding="utf-8") as handle:
        scenario = json.load(handle)

    if not isinstance(scenario, dict):
        raise TypeError("scenario config must be a JSON object")

    _validate(scenario)

    scenario.setdefault("target", "QNX 8.0 QEMU")
    scenario.setdefault("critical_path", [])
    scenario.setdefault("thresholds", {})

    return scenario
