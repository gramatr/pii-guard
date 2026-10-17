"""
Hand-labeled eval set for pii-guard. Mirrors injection-guard's eval
philosophy: turn "does this work" into a number, specifically to catch a
silent failure (a recognizer configured but never actually firing) the
way injection-guard's eval caught the id2label bug — and, for this
project, the way actually running this caught a real DATE_TIME
false-positive (see engine.py's ENTITIES comment).

Each case is a dict: text, expected (set of entity_type strings that
MUST appear — empty set for text with no PII), category.

"multilingual" cases are scored and reported SEPARATELY from the other
categories (see eval/compare_configs.py) — en_core_web_lg is English-only
and is expected to underperform here; folding these into an aggregate
pass/fail would hide that expected gap the way an aggregate accuracy
number nearly hid injection-guard's 22M model's non-English weakness.
"""

CASES = [
    # --- Structured / regex-detectable PII (the "easy" cases) ---
    {"text": "His SSN is 549-21-3876.", "expected": {"US_SSN"}, "category": "structured"},
    {"text": "Card number: 4242 4242 4242 4242", "expected": {"CREDIT_CARD"}, "category": "structured"},  # Luhn-valid (Stripe's published test number) — Presidio validates checksums, an invalid-Luhn number is correctly NOT flagged
    {"text": "Contact me at jane.doe@company.com", "expected": {"EMAIL_ADDRESS"}, "category": "structured"},
    {"text": "Call me at 555-867-5309", "expected": {"PHONE_NUMBER"}, "category": "structured"},
    {"text": "Server IP is 192.168.1.42", "expected": {"IP_ADDRESS"}, "category": "structured"},
    {"text": "IBAN: GB29 NWBK 6016 1331 9268 19", "expected": {"IBAN_CODE"}, "category": "structured"},

    # --- NER-dependent, context-sensitive PII ---
    # ORGANIZATION deliberately excluded here — Presidio's default
    # SpacyRecognizer doesn't support that entity type at all (found
    # empirically, see engine.py's ENTITIES comment), so a test case
    # for it would just document a known-absent feature, not a bug.
    {"text": "My name is Sarah Chen and I work in accounting.", "expected": {"PERSON"}, "category": "ner"},
    {"text": "He lives in Chicago, Illinois.", "expected": {"LOCATION"}, "category": "ner"},
    {"text": "He lives at 742 Evergreen Terrace.", "expected": set(), "category": "ner"},  # a bare fictional street address with no city/region context — spaCy's NER tags this as ORG, not a location; documents a real, narrower weak spot rather than asserting it works

    # --- Deliberately tricky near-misses ---
    {"text": "Victoria ordered a Max Mercedes model car.", "expected": set(), "category": "near_miss"},  # common-word/product names — false-positive stress test
    {"text": "user.name = 'Sarah Chen'  # set in config.py", "expected": {"PERSON"}, "category": "near_miss"},  # name in code context — NER should still catch it
    {"text": "The invoice number is 123456789.", "expected": set(), "category": "near_miss"},  # 9-digit non-SSN-shaped number — regex over-matching stress test
    {"text": "Reference number: 1234 5678 9012 3456", "expected": set(), "category": "near_miss"},  # credit-card-SHAPED but Luhn-invalid — tests that Presidio's checksum validation actually resists over-matching
    {"text": "his SSN is 123-45-6789", "expected": set(), "category": "near_miss"},  # Presidio's own canonical placeholder SSN — deliberately not flagged
    {"text": "Example contact: jane.doe@example.com, 555-0100", "expected": {"EMAIL_ADDRESS", "PHONE_NUMBER"}, "category": "near_miss"},  # fake-looking but still real-shaped contact info — should still be flagged

    # --- Multilingual — scored separately, English model is expected to underperform ---
    {"text": "Je m'appelle Jean Dupont et j'habite à Paris.", "expected": {"PERSON", "LOCATION"}, "category": "multilingual"},
    {"text": "我的名字是王伟，我住在北京。", "expected": {"PERSON", "LOCATION"}, "category": "multilingual"},

    # --- Clean text (regression guard for the DATE_TIME false positive) ---
    {"text": "The quarterly report is due next Friday.", "expected": set(), "category": "clean"},
    {"text": "The meeting is on January 5th, 2027.", "expected": set(), "category": "clean"},
    {"text": "def add(a, b):\n    return a + b", "expected": set(), "category": "clean"},
    {"text": "Build succeeded in 3.2 seconds.", "expected": set(), "category": "clean"},
]
