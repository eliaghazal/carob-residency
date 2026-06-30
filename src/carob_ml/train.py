"""Train the support router and add it to the model registry.

    python -m carob_ml train    # reads data/processed, writes models/router/<version>/

The model is a scikit-learn pipeline: normalized text, character and word
TF-IDF features, multinomial logistic regression over the 77 intents. The
API maps the intent to a queue (manifest["intent_to_queue"]).
"""

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import FeatureUnion, Pipeline

from carob_ml.data import PROCESSED
from carob_ml.labels import INTENT_TO_QUEUE
from carob_ml.normalize import normalize

REGISTRY = Path("models/router")


def make_pipeline() -> Pipeline:
    features = FeatureUnion(
        [
            (
                "chars",
                TfidfVectorizer(
                    preprocessor=normalize,
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    min_df=2,
                    sublinear_tf=True,
                ),
            ),
            (
                "words",
                TfidfVectorizer(preprocessor=normalize, ngram_range=(1, 2), min_df=2, sublinear_tf=True),
            ),
        ]
    )
    return Pipeline([("features", features), ("classifier", LogisticRegression(C=10.0, max_iter=2000))])


def train(data_dir: Path = PROCESSED, registry: Path = REGISTRY) -> dict[str, object]:
    train_df = pd.read_parquet(data_dir / "train.parquet")
    val_df = pd.read_parquet(data_dir / "val.parquet")
    started = time.perf_counter()
    pipeline = make_pipeline().fit(train_df.text, train_df.intent)
    seconds = time.perf_counter() - started
    predicted = pipeline.predict(val_df.text)
    metrics = {
        "val_accuracy": round(float(accuracy_score(val_df.intent, predicted)), 4),
        "val_macro_f1": round(float(f1_score(val_df.intent, predicted, average="macro")), 4),
        "train_seconds": round(seconds, 1),
    }
    version = datetime.now(UTC).strftime("router-%Y%m%d-%H%M%S")
    directory = registry / version
    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, directory / "model.joblib")
    data_manifest = (data_dir / "manifest.json").read_bytes()
    manifest = {
        "version": version,
        "file": "model.joblib",
        "sha256": hashlib.sha256((directory / "model.joblib").read_bytes()).hexdigest(),
        "intent_to_queue": INTENT_TO_QUEUE,
        "metrics": metrics,
        "data_manifest_sha256": hashlib.sha256(data_manifest).hexdigest(),
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
