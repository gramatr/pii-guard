# pii-guard

PII detection daemon, built on [Microsoft Presidio](https://github.com/microsoft/presidio)
(MIT). Sibling project to [gramatr/secret-guard](https://github.com/gramatr/secret-guard)
and [gramatr/injection-guard](https://github.com/gramatr/injection-guard) —
same `core`/`adapters` philosophy, different problem: secrets are caught by
pattern-matching, prompt injection needs a model classifying shape/intent,
and PII needs a model that locates literal personal data (names, SSNs,
emails, phone numbers, addresses) by exact character span.

## Architecture: daemon, not CLI — but no hosted tier either

Presidio is not itself a model — it's an orchestration layer
(`AnalyzerEngine` + `RecognizerRegistry` + `NlpEngine`) over regex-based
recognizers *and* a spaCy NER pipeline for free-text entities (`PERSON`,
`LOCATION`, `ORGANIZATION`) regex can't catch. The default `NlpEngine`
backing is spaCy's `en_core_web_lg`, and loading a spaCy pipeline is a
real, measured cost — same "too slow to reload, fine to serve resident"
shape as injection-guard's transformer, unlike secret-guard's zero-model
gitleaks case. So this is `pii-guard-daemon`: load once at startup, serve
`/analyze` requests against the resident engine.

**But it has no hosted/server-side deployment target, unlike
injection-guard — this is the one place this project deliberately
diverges from its sibling rather than mirroring it.** See "Why no hosted
tier" below.

## Why no hosted tier

injection-guard's hosted tier is defensible because the *output* of
classification is a shape judgment (`malicious: true/false`) about prompt
structure — a jailbreak attempt isn't personal information merely by being
classified. pii-guard's entire job is different: find literal personal
data in text. That's "locate and extract literal sensitive values,"
structurally identical to **secret-guard's** threat model (locate and
extract literal credential values), not injection-guard's "classify
structural intent." secret-guard will never have a hosted tier because
sending a live credential value to any remote endpoint — even your own —
defeats the tool's purpose. The same reasoning applies here: the values
are PII rather than credentials, but the shape of the problem — "don't
ship the exact sensitive payload off-box to find out it's sensitive" — is
the same.

There's a second, SOC2-specific reason: a hosted pii-guard tier would mean
grāmatr's own infrastructure processes customer PII in the course of
scanning for customer PII, pulling the hosted tier itself into
PII-handling scope under most privacy frameworks (GDPR Article 4(2)
"processing" has no materiality floor) — a scope-and-audit-surface cost
injection-guard's hosted tier doesn't carry.

If a hosted tier is ever seriously proposed later: get the legal/DPA
review *before* writing a data-handling policy document, not after —
don't repeat injection-guard's sequencing on that one.

**Practical consequence:** no `AUTH_TOKEN` config, no `DATA_HANDLING.md`,
no "two deployment targets" table — `config.py`'s `HOST` has exactly one
correct default (`127.0.0.1`), local-only, full stop. The Docker image
still binds `0.0.0.0` *inside the container* (same reason as
injection-guard: Docker's port-publishing needs it), but there is no
scenario where this daemon is meant to be reachable from outside the
machine it runs on.

## Redaction, not flagging — unlike injection-guard

injection-guard flags suspected prompt injection with a warning banner
rather than altering the content, because there's no safe way to blank
an arbitrary "this whole chunk might be an attack" judgment without
risking breaking legitimate content. PII is different: Presidio gives
exact character spans for each entity, the same precision secret-guard's
gitleaks-based redaction already relies on. So `pii-guard` **redacts by
default** via Presidio's `AnonymizerEngine` — same posture as
secret-guard, not injection-guard.

## Running locally

```
docker build -t pii-guard -f docker/Dockerfile .
docker run -p 8731:8731 pii-guard
```

```
curl -X POST http://localhost:8731/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text": "John Smith lives at 123 Main St, his SSN is 549-21-3876, email john@example.com"}'
```

No HF-style gated download here — `en_core_web_lg` is MIT and downloads
anonymously, so unlike injection-guard, the Docker image bakes the model
in at build time rather than pulling it at startup (see `docker/Dockerfile`
comment, and "Licensing" below for why that's safe to do).

## Startup cost (measured)

Measured directly (not estimated) on the development machine building this:

| | Time |
|---|---|
| `presidio_analyzer` import | ~681ms |
| `AnalyzerEngine()` construction | ~963ms |
| First `analyze()` call | ~322ms |
| Resident memory after load | ~758MB |

Total cold-start cost before the first request: **~1.6s**. This is the
real number behind "daemon, not CLI" — confirms the design spec's
recommendation rather than leaving it as an estimate.

## Claude Code adapter

`adapters/claude-code/hook.sh` — a `PostToolUse` hook, same wiring
pattern as both siblings'. Redacts PII in tool output in place and
reports findings (entity type, never the matched value) the same way
`secret-guard` does. Fails open if the daemon is unreachable.

## Licensing

Presidio itself: MIT. The default NER backend, spaCy's `en_core_web_lg`:
**MIT** (Explosion) — confirmed via spaCy's own Hugging Face model card.
No "Built with X" display requirement, no `NOTICE`-file obligation, no
MAU threshold clause, no gated/authenticated download — unlike Llama
Prompt Guard 2, this downloads anonymously via `pip` or `spacy download`.
No `NOTICE` or `THIRD_PARTY_LICENSES/` needed for v1 as scoped — their
absence here is a deliberate decision (this tool's dependency chain is
genuinely clean), not an oversight the way it would be if copied from
injection-guard without re-checking.

**If the NER backend is ever swapped** (Presidio supports pluggable
spaCy/Stanza/transformers/GLiNER backends): re-do this license check from
scratch. A transformer checkpoint can carry a gated community license the
way Llama Prompt Guard 2 did; a spaCy statistical pipeline generally does
not. This clean result is about `en_core_web_lg` specifically, not
Presidio in the abstract.

## Language scope: English only (v1)

`en_core_web_lg` is an English model. Presidio's out-of-the-box default
will silently underperform on non-English PII — the same way injection-
guard's 22M Prompt Guard variant underperformed on non-English injection
attempts. **Non-English PII is explicitly out of scope for v1** — stated
here rather than left implicit. Multi-language support requires explicitly
configuring additional per-language spaCy models in Presidio's `NlpEngine`
config; not done here.

## Known quirk worth knowing: Presidio deliberately ignores some "obvious" PII

Presidio's `UsSsnRecognizer` hardcodes a deny-list of well-known
placeholder SSNs (e.g. `123-45-6789`, the textbook tutorial example) and
will **not** flag them — confirmed by reading the recognizer's
`invalidate_result()` source directly. This is correct, deliberate
behavior (avoiding false positives on canonical sample data), not a bug —
but it means a quick sanity-test with the "obvious" example SSN will look
like pii-guard is broken when it isn't. Use a real-format, non-placeholder
SSN to test detection.

## Entity coverage and eval results (measured, not estimated)

`eval/dataset.py` + `eval/compare_configs.py`, run against the real engine:

| Category | Cases | FN | FP | Avg latency |
|---|---|---|---|---|
| Structured (SSN/credit card/email/phone/IP/IBAN) | 6 | 0 | 0 | ~9ms |
| NER (person/location) | 3 | 0 | 0 | ~3ms |
| Near-miss stress tests | 6 | 1 | 2 | ~3ms |
| Clean text (no PII) | 4 | 0 | 0 | ~3ms |
| Multilingual (French/Chinese) | 2 | 1 (Chinese) | 0 | ~3ms |

**`ORGANIZATION` is not supported, found empirically, not assumed:**
Presidio's default `SpacyRecognizer.supported_entities` is
`['PERSON', 'DATE_TIME', 'LOCATION', 'NRP']` — no `ORG`/`ORGANIZATION` at
all. Requesting it doesn't error, it just silently never fires. The
design spec that preceded this implementation called for organization
detection; this is a deliberate, documented scope reduction from that
spec, not an oversight. Enabling it would need a custom `NlpEngine`
entity mapping — not done for v1.

**Known near-miss behavior, not a bug:** a bare 9-digit number
("The invoice number is 123456789.") gets flagged as a possible
`US_DRIVER_LICENSE`/`US_PASSPORT`/`US_BANK_NUMBER` — those recognizers'
patterns are loose by design (generic numeric-ID formats), and this
project's priority (per injection-guard's stated posture, inherited
here) is false negatives mattering more than false positives for a
security tool. A missed real ID is worse than an occasional
over-redaction of an ordinary number.

**A bare street address with no city/region context** ("742 Evergreen
Terrace") is correctly *not* flagged as `LOCATION` — spaCy's NER tags it
as `ORG` instead. Real, narrower limitation, documented via a test case
rather than silently accepted; `LOCATION` works reliably once a
recognizable city/region is present ("Chicago, Illinois" — see eval).

## Roadmap

- [ ] CI wiring the eval in as a regression gate
- [ ] `pip-licenses` run against the full resolved dependency tree (this
      README's license check is model-level, not a full transitive audit)
- [ ] Custom `NlpEngine` entity mapping to enable `ORGANIZATION` detection, if needed
