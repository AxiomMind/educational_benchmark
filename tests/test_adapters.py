from __future__ import annotations

from chis_eval.config import SourceRegistry
from chis_eval.crawlers.adapters import get_adapter, GaokaoBenchAdapter, AgiEvalAdapter, GaokaoMmAdapter, ZujuanAdapter


def test_registered_adapters():
    registry = SourceRegistry.load("config/source_registry.yaml")

    bench_entry = registry.require_source("GAOKAO_BENCH")
    adapter_bench = get_adapter(bench_entry.adapter, bench_entry)
    assert isinstance(adapter_bench, GaokaoBenchAdapter)

    agi_entry = registry.require_source("AGIEVAL_GAOKAO")
    adapter_agi = get_adapter(agi_entry.adapter, agi_entry)
    assert isinstance(adapter_agi, AgiEvalAdapter)

    mm_entry = registry.require_source("GAOKAO_MM")
    adapter_mm = get_adapter(mm_entry.adapter, mm_entry)
    assert isinstance(adapter_mm, GaokaoMmAdapter)

    zujuan_entry = registry.require_source("ZUJUAN_XKW")
    adapter_zujuan = get_adapter(zujuan_entry.adapter, zujuan_entry)
    assert isinstance(adapter_zujuan, ZujuanAdapter)
    assert isinstance(adapter_zujuan._get_cookie_dict(), dict)
