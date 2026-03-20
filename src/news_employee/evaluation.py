from __future__ import annotations

import csv
from pathlib import Path

from .models import ForecastOutcome, MarketImpactAssessment, PriceObservation


def load_price_observations(path: str | Path) -> list[PriceObservation]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            PriceObservation(
                asset=row["asset"],
                evaluation_window=row["evaluation_window"],
                observed_direction=row["observed_direction"],
                observed_move=float(row.get("observed_move", 0.0)),
                notes=row.get("notes", ""),
            )
            for row in reader
        ]


class ForecastEvaluator:
    def evaluate(self, run_id: int, assessments: list[MarketImpactAssessment], observations: list[PriceObservation]) -> list[ForecastOutcome]:
        outcomes: list[ForecastOutcome] = []
        obs_lookup = {(item.asset, item.evaluation_window): item for item in observations}
        for assessment in assessments:
            if assessment.status != "ready":
                continue
            for asset in assessment.impacted_assets:
                for window in ("D0", "D1", "D5"):
                    observation = obs_lookup.get((asset, window))
                    if observation is None:
                        continue
                    outcomes.append(
                        ForecastOutcome(
                            run_id=run_id,
                            assessment_id=assessment.id,
                            asset=asset,
                            evaluation_window=window,
                            observed_direction=observation.observed_direction,
                            observed_move=observation.observed_move,
                            hit=observation.observed_direction == assessment.direction,
                            notes=observation.notes,
                        )
                    )
        return outcomes
