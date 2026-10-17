"""
Loads the real Presidio engines (requires en_core_web_lg installed) and
checks real detection + redaction behavior — deliberately not mocked,
since a mocked engine proves nothing about whether detection works.
"""

from pii_guard import engine


def setup_module():
    engine.load_engines()


def test_detects_and_redacts_multiple_entity_types():
    result = engine.analyze_and_redact(
        "John Smith lives at 123 Main St, his SSN is 549-21-3876, email john@example.com"
    )
    assert result["found"] is True
    entity_types = {e["entity_type"] for e in result["entities"]}
    assert "PERSON" in entity_types
    assert "US_SSN" in entity_types
    assert "EMAIL_ADDRESS" in entity_types
    # the raw values must never appear in the redacted text
    assert "549-21-3876" not in result["redacted_text"]
    assert "john@example.com" not in result["redacted_text"]


def test_clean_text_finds_nothing():
    """Regression test for a real false-positive caught while building
    this: Presidio's full default entity set includes DATE_TIME, which
    flagged "quarterly" and "next Friday" in this exact sentence as PII.
    A plain date isn't sensitive on its own — DATE_TIME/URL/NRP are
    deliberately excluded from engine.ENTITIES (see engine.py)."""
    result = engine.analyze_and_redact("The quarterly report is due next Friday.")
    assert result["found"] is False
    assert result["entities"] == []


def test_date_time_is_deliberately_excluded():
    result = engine.analyze_and_redact("The meeting is on January 5th, 2027.")
    assert result["found"] is False


def test_placeholder_ssn_is_deliberately_not_flagged():
    """Presidio's UsSsnRecognizer hardcodes a deny-list of canonical
    sample/placeholder SSNs (confirmed by reading invalidate_result()
    source directly) — 123-45-6789 is on it. This is correct behavior,
    not a bug; this test exists so a future "fix" doesn't break it."""
    result = engine.analyze_and_redact("his SSN is 123-45-6789")
    ssn_entities = [e for e in result["entities"] if e["entity_type"] == "US_SSN"]
    assert ssn_entities == []


def test_entities_never_carry_raw_matched_value():
    """The response schema has no field for the matched substring —
    this test guards against ever adding one by accident."""
    result = engine.analyze_and_redact("email test@example.com")
    for entity in result["entities"]:
        assert set(entity.keys()) == {"entity_type", "start", "end", "score"}
