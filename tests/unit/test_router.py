import pytest

from carob.support.router import RulesRouter, language_of


@pytest.mark.parametrize(
    ("text", "queue"),
    [
        ("My card was stolen this morning", "security"),
        ("How do I change my card PIN?", "cards"),
        ("My top up from yesterday is still pending", "topups"),
        ("I sent money to my brother but the transfer did not arrive", "transfers"),
        ("What exchange rate do you use for dollars?", "exchange"),
        ("بطاقتي انسرقت مبارح، في احتيال على حسابي", "security"),
        ("ما وصل التحويل لأخي", "transfers"),
    ],
)
def test_rules_route_common_messages(text: str, queue: str) -> None:
    assert RulesRouter().route(text).queue == queue


def test_unmatched_messages_have_low_confidence() -> None:
    route = RulesRouter().route("hello")
    assert route.queue == "general" and route.confidence < 0.5


def test_language_detection() -> None:
    assert language_of("مرحبا") == "ar"
    assert language_of("hello") == "en"
