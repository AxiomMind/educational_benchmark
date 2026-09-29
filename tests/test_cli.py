from chis_eval.cli import main


def test_empty_registry_blocks_unknown_source(capsys) -> None:
    exit_code = main(["crawl", "--source", "not_registered", "--limit", "20", "--dry-run"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Unknown source_id" in captured.err
