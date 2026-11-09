# Thai NL → SQL (rule-based, business domain)

> **Presentation UI is ready:** run `./start-demo.ps1` and open `http://127.0.0.1:8000/`.
> Read [PRESENTATION_RUNBOOK.md](PRESENTATION_RUNBOOK.md) for the 5–7 minute demo and standalone offline backup.

> **Sprint 2 is ready: [SPRINT2.md](SPRINT2.md)** — compare Rule-based against
> IntelSphere `gpt-5.6-luna` using POST `/compare` in API v0.3.0.

> **Start with [SCHEMA_GUIDE.md](SCHEMA_GUIDE.md) for the five-table sales and inventory demo (v0.2).**
> Run `./start-demo.ps1` (entry point: `app.demo_api:app`).
> The remainder of this README describes the original broader prototype
> (`app.main`), which is preserved for reference and uses a different schema.

Turns a Thai (or English) business question into a safe, parameterized SQL
query against a shop database, using rules and a maintainable lexicon —
no LLM in the query path.

```
raw text
  -> normalize          (app/nlp/normalize.py)   clean text, tokens
  -> match_intent        (app/nlp/intents.py)     metric, dimension, filters, top-N
  -> parse_time_range     (app/nlp/time_parser.py) Thai/BE dates -> [start, end)
  -> resolve_entity       (app/nlp/entity_resolver.py) name -> row id, or ambiguous
  -> build_query          (app/sql/builder.py)     Intent -> parameterized SELECT
  -> execute (read-only, LIMIT + timeout)
```

Every step is deterministic and independently testable — see `tests/`.

## Quick start

```bash
cp .env.example .env      # fill in real values
docker compose up -d --build
curl -X POST localhost:8000/query -H 'content-type: application/json' \
  -d '{"text": "ยอดขายเดือนนี้เท่าไหร่"}'
```

Local dev without Docker:

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql://readonly:...@localhost:5432/shop
uvicorn app.main:app --reload
```

## Running the tests

```bash
pip install -r requirements.txt
pytest tests/ -v            # unit + pipeline tests, spin up an embedded Postgres
python3 eval/run_eval.py    # coverage/accuracy report against eval/test_set.yaml
```

Tests use [`pgserver`](https://pypi.org/project/pgserver/) to run a real,
throwaway PostgreSQL in-process — no Docker needed for `pytest`. `pg_trgm`
(fuzzy name matching) isn't in that minimal build, so
`app/nlp/entity_resolver.py`'s fuzzy step is untested there; it *is* live
once you run against Docker's `postgres:15` image, which ships it.

## What's rule-based, and where the rules live

| Concern | File | What to edit to extend it |
|---|---|---|
| Vocabulary (metrics, entities, status, synonyms) | `config/lexicon.yaml` | Add a synonym under the right key. No code change needed. |
| Thai calendar words (months, relative periods, BE) | `config/time_words.yaml` | Add a phrase under the right key. |
| Which table joins to which | `app/sql/schema.py` `EDGES` | Add an edge when you add a table/FK to `db/schema.sql`. |
| What a metric computes | `app/sql/builder.py` `METRICS` | Add a new `metric_key -> SQL expression`. |
| What can be grouped/filtered by | `app/sql/builder.py` `DIMENSIONS` | Add a new `dimension_key -> (table, id_col, label_col)`. |
| Sentence-level pattern rules (top-N, superlatives, comparators) | `app/nlp/intents.py` | Add a regex or phrase list. |

This is deliberately a **data-driven** system: 90% of "teach it a new
question" work should be editing YAML, not Python.

## Safety guarantees (enforced in code, not just policy)

- **SELECT-only.** `build_query` has no code path to any other verb; every
  table/column comes from `app/sql/schema.py`'s `ALLOWED_TABLES` /
  `ALLOWED_COLUMNS`, checked before use.
- **Parameterized values, always.** Names, numbers, and dates are bind
  parameters (`%s`), never string-interpolated into SQL text.
- **Never guesses on entity identity.** If a name matches more than one row,
  `entity_resolver` returns `AMBIGUOUS` with the candidates, and the
  pipeline reports that to the caller instead of picking one.
- **`LIMIT` and a statement timeout are always applied** (see `MAX_LIMIT`,
  `DEFAULT_LIMIT` in `builder.py`, `STATEMENT_TIMEOUT_MS` in `pipeline.py`).
- **Cancelled orders are excluded from revenue-style metrics by default**
  unless the question explicitly filters on status — so "ยอดขายเดือนนี้"
  doesn't silently include money that was never actually collected.
- Connect the app as the `readonly` Postgres role (see the comment block at
  the bottom of `db/schema.sql`) as a second line of defense.

## Known limitations (honest list, not swept under the rug)

- **No true "compare A vs B" intent.** "เทียบกับเดือนที่แล้ว" currently just
  causes the time parser to pick whichever relative-period phrase is
  *longer* as text and silently drops the other side. A real comparison
  (two ranges, a delta, a % change) needs a new `Intent` shape with two
  time ranges — not yet built. See `eval/test_set.yaml`'s "Known gaps".
- **No anti-join questions** ("ลูกค้าคนไหนไม่เคยสั่งซื้อเลย" — customers who
  never ordered). Needs a `LEFT JOIN ... WHERE right.id IS NULL` intent
  shape the builder doesn't have yet.
- **Proper-name extraction is substring-based, not a real NER model.** It
  works by stripping every phrase the intent matcher already consumed, plus
  connector words, and treating what's left as a candidate name. This is
  robust to Thai's lack of word spacing (see the regression test
  `test_customer_name_adjacent_to_verb_still_resolves`), but it will still
  occasionally grab the wrong leftover fragment on sentences with unusual
  phrasing outside the lexicon's coverage. Every miss found in testing (see
  "Bugs found and fixed" below) got turned into a permanent regression test
  rather than a one-off patch, and that pattern should continue as new gaps
  are found.
- **Single-turn only.** No conversation memory — "แล้วเดือนก่อนล่ะ" ("what
  about last month?") as a follow-up isn't resolved against prior context.
- **Fuzzy name matching needs `pg_trgm`.** Falls back to exact/substring
  matching only if the extension isn't installed (logged as `NOT_FOUND`
  rather than crashing).

## Bugs found and fixed during development (kept as regression tests)

Real issues caught by testing against a live database rather than trusting
the code by inspection — each is now a named test in `tests/test_pipeline.py`
so it can't silently come back:

1. Seed data generator used `(g * 7) % 7`, which is always `0` — every
   generated order landed on customer 1. Fixed in `db/seed.sql`.
2. `SET LOCAL statement_timeout = %s` isn't valid Postgres (no bind params
   there) — fixed to use a literal (the value is an internal constant, never
   user input, so this is safe).
3. `"ของ"` (a generic "of/belonging to" word) was listed as a product
   synonym, causing false dimension matches on totally unrelated questions.
4. A superlative phrase ("ที่สุด") wasn't always stripped from the text when
   an explicit top-N number was already present, leaving a fragment ("สุด")
   that accidentally fuzzy-matched an unrelated customer named "สุดา".
5. The repeat-character emphasis collapser ("มากกกก" → "มาก") used a
   3-repeat threshold, which mangled the legitimate word "ต่อออเดอร์" (three
   real, different-word vowels in a row at a word boundary) into
   "ต่อเดอร์". Raised the threshold to 4.

## Suggested next steps

1. Add the "compare two periods" and "never ordered" intent shapes (see
   Known limitations above) — they're the two most common real business
   questions this doesn't handle yet.
2. Grow `eval/test_set.yaml` every time a real user question fails; that
   log is the actual backlog for `config/lexicon.yaml`.
3. Once rule coverage plateaus, consider a small LLM/ML fallback *only* for
   questions the rules miss — keep the rules as the trusted, auditable core
   and log every fallback invocation for review.
