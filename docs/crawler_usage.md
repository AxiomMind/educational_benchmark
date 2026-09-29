# Crawler usage and adapter contract

## Source gate

Before network access, `crawl` loads `config/source_registry.yaml` and requires:

- `status: approved`;
- `login_required: false`;
- `robots_checked: true`;
- `terms_checked: true`;
- a licence status other than `restricted`;
- an implemented adapter name.

An empty registry is intentional. It prevents accidental access before URLs and
rules are reviewed.

## Shared downloader

`BaseCrawler` provides serial requests, a 2–5 second configurable interval,
explicit User-Agent, timeout, retry/backoff, raw byte preservation, URL/content
hashing, same-domain enforcement, error classification, SQLite checkpointing
and cache reuse. V0.1 is serial even if a concurrency value of 2 is configured.

Retryable responses are 408, 425, 429 and selected 5xx responses. Other 4xx
responses are recorded without repeated requests. `Retry-After` is honoured up
to 60 seconds.

## Site adapters

Each source gets a separate class under `src/chis_eval/crawlers/adapters/`.
Adapters implement only:

1. list and pagination discovery;
2. detail/PDF link discovery;
3. source-specific selectors and metadata rules;
4. conversion of saved raw files to canonical question records.

No production selector belongs in the shared parser. A source adapter is added
only after inspecting sample URLs. JavaScript browser automation is considered
only after confirming that static HTTP cannot retrieve the required content.

## Adding a source

Supply a listing URL, two or three detail examples, terms URL, robots result,
licence evidence, answer location, expected exam range, and redistribution
permission. Register it as `draft`, implement and test the adapter with saved
fixtures, then change to `approved` after review.

Start with:

```bash
python -m chis_eval crawl --source SOURCE_ID --limit 20 --dry-run
python -m chis_eval crawl --source SOURCE_ID --limit 20
python -m chis_eval parse --source SOURCE_ID --limit 20
```

After parsing, `export-csv` creates an internal flattened CSV. It is not a
public-release command and does not override source redistribution restrictions.
