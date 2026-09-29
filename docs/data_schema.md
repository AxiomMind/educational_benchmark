# Data schema

The canonical intermediate format is UTF-8 JSONL with one question per line.
`schemas/question_schema.json` is the machine-readable contract.

## Raw and normalised values

- `raw_question` and `raw_options` retain parser output.
- `normalized_question`, `question`, and `options` contain conservative
  normalisation only. `question` must equal `normalized_question`.
- `provenance.normalization_changes` records before/after values.
- The immutable downloaded body is referenced by `provenance.raw_file` and its
  SHA-256 is stored as `provenance.content_hash`.

Normalisation may change Unicode width, HTML entities, whitespace, option
markers and answer letter case. It must not paraphrase the historical content.

## Groups

Every record has a non-empty `group_id`. Standalone questions receive their own
group. Questions sharing one material receive the same group. Dataset splitting
must operate on groups, never individual records.

## Answers

`answer_status` supports `unchecked`, `verified`, `single_source`, `conflict`,
`missing`, and `invalid`. The validator promotes an answer to `verified` only
when evidence is explicitly official or at least two distinct reliable sources
agree. Parser output from one source remains `single_source`.

## Multiple sources

`source` is the primary display source. `source_records` retains all known
occurrences and `answer_evidence` retains source-specific answer claims. A
deduplication operation must not discard these records automatically.

## Hashes

- `ordered_hash`: material + question + A/B/C/D option order.
- `permutation_hash`: material + question + sorted option text.

The second hash identifies option-order changes. Any future canonical merge
must map the answer by option text; it must not copy the old answer letter.

## Images

`has_image` records the presence of an image. `image_dependency` distinguishes
`not_image_dependent`, `image_dependent`, and `needs_review`. Image-dependent
records are excluded from a pure-text release unless separately approved.

## Report meaning

The validation-stage `structurally_valid` count means that no structural error
was found. Validation-stage `qualified` additionally requires a verified answer
and no confirmed image dependency. The final quality report is stricter:
`qualified` also requires human approval and `duplicate_status: unique`.
