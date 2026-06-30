"""Build the routing dataset: English BANKING77 plus Arabic ArBanking77, one table, three splits.

    python -m carob_ml data    # writes data/processed/{train,val,test}.parquet and manifest.json

Columns: text, intent (BANKING77 spelling), language (en, ar), variety
(en, msa_pal, msa, pal, saudi, moroccan, tunisian), source, split.
"""

import hashlib
import json
from pathlib import Path

import pandas as pd
from datasets import load_dataset

from carob_ml.labels import canonical_intent
from carob_ml.sources import ARBANKING77, BANKING77

PROCESSED = Path("data/processed")
SEED = 20260303


def _arbanking(file: str) -> pd.DataFrame:
    url = ARBANKING77["base_url"].format(commit=ARBANKING77["commit"], file=file)  # type: ignore[union-attr]
    return pd.read_csv(url)


def load_english() -> pd.DataFrame:
    ds = load_dataset(BANKING77["repo"], revision=BANKING77["revision"])
    frames = []
    for split in ("train", "test"):
        df = ds[split].to_pandas()[["text", "label_text"]].rename(columns={"label_text": "intent"})
        df["split"] = split
        frames.append(df)
    english = pd.concat(frames, ignore_index=True)
    english["language"], english["variety"], english["source"] = "en", "en", "banking77"
    # Hold out a tenth of the training rows, stratified by intent, for validation.
    train = english[english.split == "train"]
    val_index = train.groupby("intent", group_keys=False).sample(frac=0.1, random_state=SEED).index
    english.loc[val_index, "split"] = "val"
    return english


def load_arabic() -> pd.DataFrame:
    intents = _arbanking(ARBANKING77["intents"])  # type: ignore[arg-type]
    to_english = dict(zip(intents.label_ar, intents.label_en, strict=True))
    frames = []
    for split, file, variety in (
        ("train", ARBANKING77["train"], "msa_pal"),
        ("val", ARBANKING77["val"], "msa_pal"),
        *(("test", f, v) for v, f in ARBANKING77["test"].items()),  # type: ignore[union-attr]
    ):
        df = _arbanking(file)  # type: ignore[arg-type]
        df["split"], df["variety"] = split, variety
        frames.append(df)
    arabic = pd.concat(frames, ignore_index=True)
    arabic["intent"] = [canonical_intent(to_english[label]) for label in arabic.label]
    arabic["language"], arabic["source"] = "ar", "arbanking77"
    return arabic[["text", "intent", "split", "language", "variety", "source"]]


def build(out: Path = PROCESSED) -> dict[str, object]:
    data = pd.concat([load_english(), load_arabic()], ignore_index=True)
    data["text"] = data["text"].astype(str).str.strip()
    data = data[data.text != ""]
    out.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "sources": {"banking77": BANKING77, "arbanking77": ARBANKING77},
        "splits": {},
    }
    for split in ("train", "val", "test"):
        part = data[data.split == split].reset_index(drop=True)
        path = out / f"{split}.parquet"
        part.to_parquet(path, index=False)
        manifest["splits"][split] = {  # type: ignore[index]
            "rows": len(part),
            "by_variety": part.variety.value_counts().sort_index().to_dict(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest
