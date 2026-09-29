# Human review workflow

Export a review sheet:

```bash
python -m chis_eval export-review --input data/cleaned/deduplicated.jsonl --output data/reviewed/review.csv
```

Reviewers may edit only `review_status`, `reviewer`, and `notes`.
`review_status` must be `approved`, `needs_revision`, `rejected`, or `pending`.
The sheet contains a `review_snapshot_hash` over protected question fields.

Merge into a new file:

```bash
python -m chis_eval merge-review \
  --input data/cleaned/deduplicated.jsonl \
  --review data/reviewed/review.csv \
  --output data/reviewed/reviewed_v1.jsonl
```

The merge refuses to overwrite the input. Unknown IDs, duplicate rows, invalid
statuses, and stale snapshot hashes are skipped and reported. Protected fields
such as question, options, answer and source are never imported from CSV.

CSV cells beginning with spreadsheet formula characters are escaped on export
and restored only for comparison. This reduces accidental formula execution
when the file is opened in spreadsheet software.
