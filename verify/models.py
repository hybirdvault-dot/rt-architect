"""Verification result model for the RTArchitect harness."""

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    layer: int
    name: str
    verdict: str          # "PASS" | "FAIL" | "WARN" | "SKIP"
    severity: str         # "P0" | "P1" | "P2" | "info"
    evidence: str = ""

    def is_fail(self) -> bool:
        return self.verdict == "FAIL"


@dataclass
class Scorecard:
    results: list[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    def counts(self) -> dict:
        out = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
        for r in self.results:
            out[r.verdict] = out.get(r.verdict, 0) + 1
        return out

    def exit_code(self) -> int:
        """0 = GREEN, 1 = YELLOW, 2 = RED."""
        if any(r.is_fail() and r.severity == "P0" for r in self.results):
            return 2
        if any(r.is_fail() for r in self.results):
            return 1
        return 0
