from pathlib import Path

from chis_eval.parsers.html import HtmlSelectorSpec, ParserContext, parse_html


def test_html_parser_extracts_material_questions_options_and_answers() -> None:
    html = Path("tests/fixtures/sample_questions.html").read_text(encoding="utf-8")
    selectors = HtmlSelectorSpec(
        group="section.question-group",
        shared_material=".material",
        question_block="article.question-block",
        question=".stem",
        option=".option",
        answer=".answer",
    )
    context = ParserContext(
        source_id="fixture",
        site_name="Synthetic fixture",
        url="https://example.test/paper/1",
        raw_file="data/raw/fixture/example.html",
        content_hash="abc",
        collector="tester",
    )
    records = parse_html(html, selectors, context)
    assert len(records) == 3
    assert records[0]["group_id"] == records[1]["group_id"]
    assert records[1]["group_id"] != records[2]["group_id"]
    assert records[0]["shared_material"].startswith("材料")
    assert records[0]["options"]["A"] == "加强中央控制"
    assert records[1]["answer"] == "B"
    assert records[2]["answer"] == ""
    assert records[2]["quality"]["answer_status"] == "missing"


def test_html_parser_returns_empty_when_adapter_group_selector_does_not_match() -> None:
    context = ParserContext("fixture", "Fixture", "https://example.test", "x.html", "abc")
    selectors = HtmlSelectorSpec(".missing", ".question", ".stem", ".option")
    assert parse_html("<html><body>nothing</body></html>", selectors, context) == []
