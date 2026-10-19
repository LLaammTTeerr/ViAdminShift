"""Tests for the benchmark generator (src/viadmin/gen) and the generated data/benchmark files."""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

import pytest

from viadmin.eval import validate as eval_validate
from viadmin.gen import generate
from viadmin.gen import validate as V
from viadmin.gen.common import BENCH, PROCESSED, load_jsonl, load_tables

FILES = ("items.jsonl", "template_passages.jsonl", "contexts.jsonl")
HAVE_DATA = all((BENCH / f).exists() for f in FILES)
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="run `uv run python -m viadmin.gen.generate` first")
HAVE_TABLES = (PROCESSED / "provinces_old.jsonl").exists()  # rebuilt locally, not shipped
needs_tables = pytest.mark.skipif(
    not HAVE_TABLES, reason="run `bash scripts/fetch_sources.sh && uv run python -m viadmin.data.build` first")


@pytest.fixture(scope="module")
def items() -> list[dict]:
    return load_jsonl(BENCH / "items.jsonl")


@pytest.fixture(scope="module")
def by_id(items) -> dict[str, dict]:
    return {it["id"]: it for it in items}


@pytest.fixture(scope="module")
def tables():
    return load_tables()


@needs_data
@needs_tables
def test_benchmark_validates():
    assert V.validate_dir(BENCH) == []


@needs_data
def test_eval_linter_clean():
    assert eval_validate.lint_file(str(BENCH / "items.jsonl")) == []


def test_new_qtypes_known_to_linter():
    assert {"T1_newname", "T5_ward_successor"} <= eval_validate.QTYPES


@needs_data
@needs_tables
def test_deterministic_rebuild(tmp_path: Path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert generate.main(["--out", str(a)]) == 0
    assert generate.main(["--out", str(b)]) == 0
    for f in FILES:
        assert (a / f).read_bytes() == (b / f).read_bytes(), f
        assert (a / f).read_bytes() == (BENCH / f).read_bytes(), f"{f}: committed file is stale"


@needs_data
def test_counts_and_cells(items):
    q = Counter(it["qtype"] for it in items)
    assert q["T2_composition"] == 34
    assert q["T6_reverse"] == 63 * 2 * 3
    assert 10 <= q["T0_headline"] <= 15
    t1 = Counter((it["meta"]["province_changed"], it["meta"]["ward_changed"])
                 for it in items if it["qtype"] == "T1_membership" and it["meta"]["cue"] == "none")
    assert t1[(False, False)] == 43 and t1[(True, False)] == 84  # control cells used in full
    assert t1[(False, True)] == 400 and t1[(True, True)] == 400
    t4 = [it for it in items if it["qtype"] == "T4_address"]
    assert sum(it["meta"]["has_diacritics"] for it in t4) == 800
    assert sum(not it["meta"]["has_diacritics"] for it in t4) == 400
    t3 = Counter(it["meta"]["t3_exists"] for it in items if it["qtype"] == "T3_existence")
    assert abs(t3[True] - t3[False]) <= 10


@needs_data
def test_mcq_old_answer_present_when_province_changed(items):
    for it in items:
        if it["qtype"] == "T1_membership" and it["meta"]["province_changed"] and it["meta"]["surface_answer_changed"]:
            assert it["old_answer"] is not None
            assert it["choices"]["ABCD".index(it["old_answer"])] == it["meta"]["old_province_name"]


@needs_data
@needs_tables
def test_no_divided_wards_in_ward_level_golds(items, tables):
    for it in items:
        if it["qtype"] in ("T4_address", "T5_ward_successor"):
            assert len(tables.rows_by_old[it["meta"]["old_ward_code"]]) == 1


@needs_data
def test_cue_none_has_no_markers(items):
    for it in items:
        if it["meta"].get("cue") == "none":
            masked = V._mask_names(it["question"], it["meta"]).lower()
            assert not V.CUE_MARKERS.search(masked), it["question"]


# ----------------------------------------------------------------------- negative tests of the checks

@needs_data
def test_leak_detector_fires(by_id):
    it = copy.deepcopy(by_id[next(k for k, v in by_id.items()
                                  if v["qtype"] == "T1_membership" and v["old_answer"] is not None)])
    gold = it["choices"]["ABCD".index(it["answer"])]
    it["question"] = it["question"].replace(" thuộc tỉnh/thành phố nào?", f", nay là {gold.lower()}, thuộc tỉnh/thành phố nào?")
    assert V.check_leakage([it])


@needs_data
def test_cue_marker_detector_fires(by_id):
    grp = [copy.deepcopy(v) for v in by_id.values() if v["meta"].get("cue_group") == "T6-30-mcq"]
    base = next(x for x in grp if x["meta"]["cue"] == "none")
    base["question"] = "Trước đây, " + base["question"][:1].lower() + base["question"][1:]
    assert any("marker" in e for e in V.check_cues(grp))


@needs_data
def test_context_checker_fires(items):
    ctx = load_jsonl(BENCH / "contexts.jsonl")
    passages = {p["passage_id"]: p for p in load_jsonl(BENCH / "template_passages.jsonl")}
    it = next(x for x in items if x["qtype"] == "T5_ward_successor")
    rows = [copy.deepcopy(r) for r in ctx if r["item_id"] == it["id"]]
    other_old = next(p for p in passages.values() if p["era"] == "new" and p["passage_id"] not in rows[1]["passages"])
    for r in rows:
        if r["condition"] == "new":
            r["passages"] = [other_old["passage_id"]]
    assert V.check_contexts([it], rows, passages)


# ----------------------------------------------------------------------- spot checks against the tables

@needs_data
@needs_tables
def test_t1_gold_matches_mapping(items, tables):
    for it in items:
        if it["qtype"] == "T1_membership":
            rows = tables.rows_by_old[it["meta"]["old_ward_code"]]
            assert it["choices"]["ABCD".index(it["answer"])] == rows[0]["new_province_name"]


@needs_data
@needs_tables
def test_t2_gold_is_composition(items, tables):
    for it in items:
        if it["qtype"] != "T2_composition":
            continue
        g = tables.pnew[it["meta"]["new_province_code"]]
        gold = it["choices"]["ABCD".index(it["answer"])]
        for c in g["merged_from"]:
            assert tables.pold[c]["short_name"] in gold
        for ch in it["choices"]:
            if ch != gold:
                assert {tables.pold[c]["short_name"] for c in g["merged_from"]} != \
                       {p["short_name"] for p in tables.provinces_old if p["short_name"] in ch} or "Chỉ có" in ch


@needs_data
def test_contexts_short_and_ordered():
    ctx = load_jsonl(BENCH / "contexts.jsonl")
    passages = {p["passage_id"]: p for p in load_jsonl(BENCH / "template_passages.jsonl")}
    for r in ctx:
        if r["condition"] == "mixed":
            assert sum(len(passages[p]["text"]) for p in r["passages"]) <= 2500
    # mixed order is not always new-last (deterministic shuffle)
    firsts = Counter(r["eras"][0] for r in ctx if r["condition"] == "mixed")
    assert firsts["old"] > 0 and firsts["new"] > 0


def test_build_stats_written_with_hashes():
    if not (BENCH / "build_stats.json").exists():
        pytest.skip("no build")
    s = json.loads((BENCH / "build_stats.json").read_text())
    assert set(s["sha256"]) == set(FILES)
