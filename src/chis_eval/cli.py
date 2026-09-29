from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Sequence

from .config import SourceRegistry
from .crawlers import BaseCrawler, get_adapter
from .errors import ChisEvalError
from .pipeline.deduplicate import DeduplicationResult, deduplicate_records
from .pipeline.export import export_canonical_csv
from .pipeline.normalize import normalise_records
from .pipeline.report import build_quality_report, write_quality_report
from .pipeline.review import export_review_csv, merge_review_csv, write_merged_review
from .pipeline.validate import validate_records
from .storage.crawl_state import CrawlState
from .storage.jsonl import read_jsonl, write_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m chis_eval",
        description="Auditable CHisEval V0.1 data pipeline",
    )
    parser.add_argument("--log-file", default="logs/chis_eval.log", help="Log file path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl = subparsers.add_parser("crawl", help="Download an approved source with its adapter")
    _registry_argument(crawl)
    crawl.add_argument("--source", required=True, help="source_id from the registry")
    crawl.add_argument("--limit", type=_positive_int, default=20)
    crawl.add_argument("--raw-dir", default="data/raw")
    crawl.add_argument("--state", default="data/state/crawl_state.sqlite3")
    crawl.add_argument("--dry-run", action="store_true")
    crawl.set_defaults(handler=_crawl)

    parse = subparsers.add_parser("parse", help="Parse saved files with a source adapter")
    _registry_argument(parse)
    parse.add_argument("--source", required=True)
    parse.add_argument("--input", help="Optional single raw file")
    parse.add_argument("--output", default="data/parsed/questions.jsonl")
    parse.add_argument("--state", default="data/state/crawl_state.sqlite3")
    parse.add_argument("--limit", type=_positive_int)
    parse.add_argument("--dry-run", action="store_true")
    parse.set_defaults(handler=_parse)

    normalize = subparsers.add_parser("normalize", help="Normalise parsed JSONL")
    _input_output_arguments(normalize)
    normalize.set_defaults(handler=_normalize)

    validate = subparsers.add_parser("validate", help="Run automatic quality checks")
    _input_output_arguments(validate)
    validate.add_argument("--report", default="data/reports/validation.json")
    validate.set_defaults(handler=_validate)

    dedup = subparsers.add_parser("deduplicate", help="Find exact, reordered and near duplicates")
    _input_output_arguments(dedup)
    dedup.add_argument("--report-dir", default="data/reports/deduplication")
    dedup.add_argument("--threshold", type=float, default=0.88)
    dedup.set_defaults(handler=_deduplicate)

    export_review = subparsers.add_parser("export-review", help="Export a human review CSV")
    _input_output_arguments(export_review, default_output="data/reviewed/review.csv")
    export_review.set_defaults(handler=_export_review)

    export_csv = subparsers.add_parser("export-csv", help="Export canonical JSONL as a flat internal CSV")
    _input_output_arguments(export_csv, default_output="data/cleaned/questions.csv")
    export_csv.set_defaults(handler=_export_csv)

    merge_review = subparsers.add_parser("merge-review", help="Safely merge review decisions")
    merge_review.add_argument("--input", required=True, help="Original JSONL")
    merge_review.add_argument("--review", required=True, help="Completed review CSV")
    merge_review.add_argument("--output", required=True, help="New JSONL; cannot equal input")
    merge_review.add_argument("--report", default="data/reports/review_merge.json")
    merge_review.add_argument("--dry-run", action="store_true")
    merge_review.set_defaults(handler=_merge_review)

    report = subparsers.add_parser("report", help="Generate aggregate quality statistics")
    report.add_argument("--input", required=True)
    report.add_argument("--output", default="data/reports/quality_report.json")
    report.add_argument("--dry-run", action="store_true")
    report.set_defaults(handler=_report)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_file)
    try:
        return int(args.handler(args) or 0)
    except (ChisEvalError, ValueError, OSError) as exc:
        logging.getLogger("chis_eval").error("%s", exc)
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _crawl(args: argparse.Namespace) -> int:
    registry = SourceRegistry.load(args.registry)
    source = registry.assert_crawl_allowed(args.source)
    adapter = get_adapter(source.adapter, source)
    with BaseCrawler(
        source,
        registry.defaults,
        raw_root=args.raw_dir,
        state_path=args.state,
        dry_run=args.dry_run,
    ) as crawler:
        results = adapter.collect(crawler, args.limit)
    _print_json(
        {
            "source_id": source.source_id,
            "dry_run": args.dry_run,
            "requested_limit": args.limit,
            "successful_or_cached": len(results),
        }
    )
    return 0


def _parse(args: argparse.Namespace) -> int:
    registry = SourceRegistry.load(args.registry)
    source = registry.require_source(args.source)
    adapter = get_adapter(source.adapter, source)
    items: list[dict[str, Any]]
    if args.input:
        items = [{"raw_file": args.input, "url": source.base_url, "content_hash": ""}]
    else:
        with CrawlState(args.state) as state:
            items = state.successful_files(source.source_id, args.limit)
    records: list[dict[str, Any]] = []
    for item in items:
        path = Path(item["raw_file"])
        records.extend(adapter.parse_file(path, item))
    if not args.dry_run:
        write_jsonl(args.output, records)
    _print_json({"source_id": source.source_id, "files": len(items), "questions": len(records), "dry_run": args.dry_run})
    return 0


def _normalize(args: argparse.Namespace) -> int:
    records = normalise_records(read_jsonl(args.input))
    if not args.dry_run:
        write_jsonl(args.output, records)
    _print_json({"records": len(records), "output": args.output, "dry_run": args.dry_run})
    return 0


def _validate(args: argparse.Namespace) -> int:
    records, summary = validate_records(read_jsonl(args.input))
    if not args.dry_run:
        write_jsonl(args.output, records)
        write_quality_report(args.report, summary.as_dict())
    _print_json({**summary.as_dict(), "dry_run": args.dry_run})
    return 0


def _deduplicate(args: argparse.Namespace) -> int:
    result = deduplicate_records(read_jsonl(args.input), near_threshold=args.threshold)
    if not args.dry_run:
        write_jsonl(args.output, result.records)
        _write_dedup_reports(Path(args.report_dir), result)
    _print_json({**result.summary(), "dry_run": args.dry_run})
    return 0


def _export_review(args: argparse.Namespace) -> int:
    records = list(read_jsonl(args.input))
    if not args.dry_run:
        export_review_csv(args.output, records)
    _print_json({"records": len(records), "output": args.output, "dry_run": args.dry_run})
    return 0


def _export_csv(args: argparse.Namespace) -> int:
    records = list(read_jsonl(args.input))
    if not args.dry_run:
        export_canonical_csv(args.output, records)
    _print_json({"records": len(records), "output": args.output, "dry_run": args.dry_run})
    return 0


def _merge_review(args: argparse.Namespace) -> int:
    records = list(read_jsonl(args.input))
    if args.dry_run:
        _, summary = merge_review_csv(records, args.review)
    else:
        summary = write_merged_review(args.input, args.review, args.output, records)
        write_quality_report(args.report, summary.as_dict())
    _print_json({**summary.as_dict(), "dry_run": args.dry_run})
    return 1 if summary.errors else 0


def _report(args: argparse.Namespace) -> int:
    report = build_quality_report(read_jsonl(args.input))
    if not args.dry_run:
        write_quality_report(args.output, report)
    _print_json({**report, "dry_run": args.dry_run})
    return 0


def _write_dedup_reports(directory: Path, result: DeduplicationResult) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, rows in (
        ("exact_duplicates.csv", result.exact_pairs),
        ("reordered_duplicates.csv", result.reordered_pairs),
        ("suspected_duplicates.csv", result.suspected_pairs),
    ):
        path = directory / name
        fields = [
            "question_id_1",
            "question_id_2",
            "duplicate_type",
            "similarity",
            "question_1",
            "question_2",
            "options_1",
            "options_2",
            "source_1",
            "source_2",
            "suggested_keep",
            "answer_equivalence",
            "human_status",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        key: _safe_csv(
                            json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value
                        )
                        for key, value in row.items()
                    }
                )
    write_quality_report(directory / "summary.json", result.summary())


def _registry_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--registry", default="config/source_registry.yaml")


def _input_output_arguments(
    parser: argparse.ArgumentParser, default_output: str | None = None
) -> None:
    parser.add_argument("--input", required=True)
    if default_output is None:
        parser.add_argument("--output", required=True)
    else:
        parser.add_argument("--output", default=default_output)
    parser.add_argument("--dry-run", action="store_true")


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _configure_logging(path: str) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )


def _print_json(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _safe_csv(value: Any) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


if __name__ == "__main__":
    raise SystemExit(main())
