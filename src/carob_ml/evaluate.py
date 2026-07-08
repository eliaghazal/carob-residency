"""Evaluate a registered router on the test split, overall and by language variety.

python -m carob_ml evaluate [--version router-...]   # writes reports/eval-<version>.json
"""

import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

from carob.support.router import ModelRouter
from carob_ml.data import PROCESSED
from carob_ml.labels import INTENT_TO_QUEUE
from carob_ml.train import REGISTRY

REPORTS = Path("reports")


def latest_version(registry: Path = REGISTRY) -> str:
    versions = sorted(p.name for p in registry.iterdir() if (p / "manifest.json").exists())
    if not versions:
        raise SystemExit("no model in the registry; run: python -m carob_ml train")
    return versions[-1]


def _scores(gold: pd.Series, predicted: pd.Series) -> dict[str, float]:
    return {
        "rows": int(len(gold)),
        "accuracy": round(float(accuracy_score(gold, predicted)), 4),
        "macro_f1": round(float(f1_score(gold, predicted, average="macro")), 4),
        "queue_accuracy": round(
            float((gold.map(INTENT_TO_QUEUE) == predicted.map(INTENT_TO_QUEUE)).mean()), 4
        ),
    }


def evaluate(
    version: str | None = None, data_dir: Path = PROCESSED, registry: Path = REGISTRY
) -> dict[str, object]:
    version = version or latest_version(registry)
    router = ModelRouter(str(registry / version))
    test = pd.read_parquet(data_dir / "test.parquet")
    test["predicted"] = router._pipeline.predict(test.text)  # noqa: SLF001 (batch prediction)
    report: dict[str, object] = {
        "version": version,
        "overall": _scores(test.intent, test.predicted),
        "by_variety": {v: _scores(g.intent, g.predicted) for v, g in test.groupby("variety")},
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"eval-{version}.json").write_text(json.dumps(report, indent=2))
    return report
