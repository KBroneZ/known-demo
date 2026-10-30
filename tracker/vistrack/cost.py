"""Pre-flight cost estimate and budget guard."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .engines.base import Engine


@dataclass(frozen=True)
class Estimate:
    calls_by_engine: dict[str, int]
    upper_usd_by_engine: dict[str, float]

    @property
    def calls(self) -> int:
        return sum(self.calls_by_engine.values())

    @property
    def upper_usd(self) -> float:
        return sum(self.upper_usd_by_engine.values())


def estimate(cfg: Config, engines: list[Engine], reps: int) -> Estimate:
    """Upper-bound cost: calls x the top of the per-call range in research/04 (section 1.1).

    Real cost is measured per call and stored in run.cost_usd; replace these numbers with the
    measured mean after the first batch.
    """
    calls = {e.key: len(cfg.prompts) * (e.reps or reps) for e in engines}
    usd = {e.key: calls[e.key] * e.est_cost_upper for e in engines}
    return Estimate(calls, usd)


class BudgetExceeded(RuntimeError):
    pass


def check_plan(est: Estimate, budget_usd: float) -> None:
    if est.upper_usd > budget_usd:
        raise BudgetExceeded(
            f"estimated upper-bound cost ${est.upper_usd:.2f} exceeds budget ${budget_usd:.2f}; "
            "reduce prompts/repetitions/engines or raise the budget explicitly"
        )
