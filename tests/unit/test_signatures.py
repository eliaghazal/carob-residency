from carob.paystub_client import sign, verify_signature


def test_a_signed_body_verifies() -> None:
    body = b'{"id":"evt_1"}'
    assert verify_signature(body, sign(body, "whsec_x", 1_000), "whsec_x", now=1_010)


def test_tampering_or_the_wrong_secret_fails() -> None:
    header = sign(b'{"id":"evt_1"}', "whsec_x", 1_000)
    assert not verify_signature(b'{"id":"evt_2"}', header, "whsec_x", now=1_000)
    assert not verify_signature(b'{"id":"evt_1"}', header, "whsec_y", now=1_000)


def test_old_signatures_are_refused() -> None:
    body = b"{}"
    assert not verify_signature(body, sign(body, "s", 1_000), "s", now=1_000 + 301)


def test_malformed_headers_are_refused() -> None:
    assert not verify_signature(b"{}", None, "s")
    assert not verify_signature(b"{}", "nonsense", "s")
    assert not verify_signature(b"{}", "t=abc,v1=00", "s")
