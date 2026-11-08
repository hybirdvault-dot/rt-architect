"""Load and validate scenario configuration files.

Scenarios are the only source of thresholds, deadlines and critical-path
definitions.  Nothing about a specific service is hardcoded in the analysis
logic, which is what keeps the tool generic.
"""

import json
from typing import Dict


def load_scenario(path: str) -> Dict:
    """Load a scenario JSON file and apply structural defaults."""
    with open(path, "r", encoding="utf-8") as handle:
        scenario = json.load(handle)

    if not isinstance(scenario, dict):
        raise ValueError("scenario config must be a JSON object")
    if "scenario" not in scenario:
        raise ValueError("scenario config must define a 'scenario' name")
    if "deadline_ms" not in scenario:
        raise ValueError("scenario config must define 'deadline_ms'")

    scenario.setdefault("target", "QNX 8.0 QEMU")
    scenario.setdefault("critical_path", [])
    scenario.setdefault("thresholds", {})

    return scenario
