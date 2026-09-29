# CHisEval data pipeline — V0.1

CHisEval is a prototype pipeline for collecting and auditing Chinese high-school
history multiple-choice questions. V0.1 focuses on provenance, parsing,
normalisation, deduplication, quality checks and human review. It does **not**
assign final ability labels and it does not treat unverified answers as gold.

The repository currently contains a source-agnostic framework and offline test
fixtures. No real website adapter or approved data source is included yet.

## Safety and data policy

- Only entries with `status: approved` in `config/source_registry.yaml` may be
  crawled.
- Login-protected, paywalled, CAPTCHA-protected, restricted, or unchecked
  sources are rejected by the crawler.
- Public accessibility is not interpreted as redistribution permission.
- Raw downloads and generated datasets are ignored by Git by default.
- Public release requires `redistribution_allowed: true` and separate review.
- Near duplicates are reported for human review and are never auto-deleted.
- A single-source answer remains `single_source`; it is not promoted to
  `verified` automatically.

## Installation

Python 3.10 or newer is required. Python 3.11 is recommended.

```bash
python -m venv .venv
.venv/Scripts/activate
python -m pip install -e ".[dev,pdf]"
```

PaddleOCR is optional and intentionally excluded from the default install:

```bash
python -m pip install -e ".[ocr]"
```

## Commands

```bash
python -m chis_eval --help
python -m chis_eval crawl --source SOURCE_ID --limit 20 --dry-run
python -m chis_eval parse --source SOURCE_ID --dry-run
python -m chis_eval normalize --input INPUT.jsonl --output CLEANED.jsonl
python -m chis_eval validate --input CLEANED.jsonl --output VALIDATED.jsonl
python -m chis_eval deduplicate --input VALIDATED.jsonl --output DEDUPED.jsonl
python -m chis_eval export-csv --input DEDUPED.jsonl --output QUESTIONS.csv
python -m chis_eval export-review --input DEDUPED.jsonl --output REVIEW.csv
python -m chis_eval merge-review --input DEDUPED.jsonl --review REVIEW.csv --output REVIEWED.jsonl
python -m chis_eval report --input REVIEWED.jsonl --output REPORT.json
```

Every command accepts explicit paths. Mutating pipeline commands support
`--dry-run`. Crawl state is stored in SQLite so successful URLs are not fetched
again and interrupted runs can continue.

`crawl` and `parse` deliberately fail with a clear message until a named source
is approved and a matching adapter has been implemented. Site selectors are
never guessed by the generic framework.

## Development

Tests use only synthetic or reduced local fixtures and never contact a live
website:

```bash
python -m pytest
```

See `docs/crawler_usage.md`, `docs/data_schema.md`, and
`docs/review_workflow.md` for workflow details.
