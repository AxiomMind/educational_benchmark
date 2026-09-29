from chis_eval.parsers.pdf import classify_page_texts


def test_pdf_text_layer_classification() -> None:
    text = "这是一段足够长的中文历史试题文本，用于确认页面包含可提取的文字层。" * 2
    assert classify_page_texts([text, text]) == "text"
    assert classify_page_texts(["", "  "]) == "scan"
    assert classify_page_texts([text, ""]) == "mixed"
