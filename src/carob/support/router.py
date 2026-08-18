"""Routing a customer's first message to a support queue.

Two routers share one interface. `RulesRouter` matches keywords in
English and Arabic and is the fallback when no model is deployed.
`ModelRouter` loads the classifier trained by `ml/` (BANKING77 intents,
English and Arabic) from the model registry. Low-confidence results go to
the triage queue, where a person routes them by hand.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

log = logging.getLogger(__name__)

QUEUES = (
    "security",
    "cards",
    "topups",
    "transfers",
    "exchange",
    "fees",
    "verification",
    "account",
    "general",
)
TRIAGE = "triage"
ARABIC = re.compile(r"[؀-ۿ]")


@dataclass(frozen=True, slots=True)
class Route:
    queue: str
    intent: str | None
    confidence: float
    version: str


class Router(Protocol):
    version: str

    def route(self, text: str) -> Route: ...


def language_of(text: str) -> str:
    return "ar" if ARABIC.search(text) else "en"


# Order matters on ties: earlier queues win (security before cards).
KEYWORDS: dict[str, tuple[str, ...]] = {
    "security": (
        "stolen",
        "lost my card",
        "lost card",
        "fraud",
        "hacked",
        "compromised",
        "not recognise",
        "not recognize",
        "didn't make",
        "سرقة",
        "مسروق",
        "ضاعت",
        "ضايعة",
        "احتيال",
        "اختراق",
        "ما عملت",
    ),
    "cards": (
        "card",
        "pin",
        "atm",
        "contactless",
        "apple pay",
        "google pay",
        "بطاقة",
        "البطاقة",
        "كرت",
        "الرقم السري",
        "صراف",
    ),
    "topups": ("top up", "top-up", "topup", "add money", "deposit", "شحن", "تعبئة", "إيداع", "ايداع"),
    "transfers": (
        "transfer",
        "send money",
        "sent money",
        "recipient",
        "beneficiary",
        "تحويل",
        "حولت",
        "حوالة",
        "المستفيد",
    ),
    "exchange": ("exchange", "rate", "convert", "currency", "صرف", "سعر", "عملة", "دولار", "ليرة"),
    "fees": ("fee", "charge", "charged", "commission", "رسوم", "عمولة"),
    "verification": ("verify", "identity", "kyc", "document", "passport", "تحقق", "هوية", "توثيق", "جواز"),
    "account": (
        "close my account",
        "password",
        "passcode",
        "personal details",
        "terminate",
        "حسابي",
        "كلمة السر",
        "إغلاق",
        "اغلاق",
    ),
}


class RulesRouter:
    version = "rules-2026.03"

    def route(self, text: str) -> Route:
        lowered = text.lower()
        scores = {q: sum(1 for k in words if k in lowered) for q, words in KEYWORDS.items()}
        best = max(KEYWORDS, key=lambda q: scores[q])
        total = sum(scores.values())
        if scores[best] == 0:
            return Route("general", None, 0.2, self.version)
        return Route(best, None, round(scores[best] / (total + 1), 3), self.version)


class ModelRouter:
    """A scikit-learn pipeline from the registry: `model.joblib` plus `manifest.json`."""

    def __init__(self, directory: str) -> None:
        import joblib  # only needed when a model is deployed

        path = Path(directory)
        manifest: dict[str, Any] = json.loads((path / "manifest.json").read_text())
        blob = (path / manifest["file"]).read_bytes()
        digest = hashlib.sha256(blob).hexdigest()
        if digest != manifest["sha256"]:
            raise RuntimeError(f"model file hash {digest} does not match its manifest")
        self._pipeline = joblib.load(path / manifest["file"])
        self._queues: dict[str, str] = manifest["intent_to_queue"]
        self.version = manifest["version"]

    def route(self, text: str) -> Route:
        probabilities = self._pipeline.predict_proba([text])[0]
        best = int(probabilities.argmax())
        intent = str(self._pipeline.classes_[best])
        return Route(self._queues.get(intent, "general"), intent, float(probabilities[best]), self.version)


_router: Router | None = None


def get_router() -> Router:
    global _router
    if _router is None:
        from carob.config import get_settings

        directory = get_settings().router_model_path
        if directory:
            try:
                _router = ModelRouter(directory)
                log.info("support router loaded", extra={"fields": {"router_version": _router.version}})
            except Exception:
                log.exception("could not load the router model; using rules")
                _router = RulesRouter()
        else:
            _router = RulesRouter()
    return _router
