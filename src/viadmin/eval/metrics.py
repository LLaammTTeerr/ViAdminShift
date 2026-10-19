"""Aggregate labelled predictions into scores.json.

Layout::

  {
    "n_predictions": int,          # predictions of items in the items file
    "n_unscored_predictions": int, # predictions whose item_id is not in the items file
    "models": [...],
    "by_condition": {
      <condition>: {
        "all":        <stats>,
        "by_qtype":   {<qtype>: {"all": <stats>, "cells": {"pc1_wc1": <stats>, ...}}},
        "by_format":  {"mcq": <stats>, "short": <stats>},
        "by_diacritics": {"with": <stats>, "without": <stats>},
        "by_qtype_format": {"T1_membership|mcq": <stats>, ...},
        "consistency": <consistency>
      }
    }
  }

<stats> = {n, accuracy, outdated_rate, accuracy_nodiac, outdated_rate_nodiac,
           labels: {correct, outdated, other_wrong, invalid},
           labels_nodiac: {...}, match_detail: {...}, truncated}
accuracy_nodiac / outdated_rate_nodiac use ``label_nodiac`` (diacritic-insensitive
matching against gold, old and legacy names; MCQ: == label). Rows written before
label_nodiac existed fall back to correct_nodiac (outdated_rate_nodiac then null).
Cell key: "pc{0|1}_wc{0|1}" from meta.province_changed / meta.ward_changed; "na" when
either is null/missing (e.g. T0_headline).

Consistency (per condition), over consistency_group values shared by >=1 T6_reverse
item and >=1 other item:
  surface_correct: all T6_reverse items of the group are correct
  n_groups, surface_acc            fraction of groups with surface_correct
  deep_acc_given_surface           item-level accuracy of the group's non-T6 items, in
                                   groups whose surface is correct
  deep_acc_given_surface_wrong     same, groups whose surface is wrong
  fully_consistent_rate            surface correct AND all deep items correct
  surface_only_rate                surface correct AND >=1 deep item not correct
                                   (the surface-vs-deep update gap)
  deep_only_rate                   surface wrong AND all deep items correct
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable

from viadmin.eval.scorer import LABELS


def cell_key(meta: dict | None) -> str:
    meta = meta or {}
    pc, wc = meta.get("province_changed"), meta.get("ward_changed")
    if pc is None or wc is None:
        return "na"
    return f"pc{int(bool(pc))}_wc{int(bool(wc))}"


def stats(rows: list[dict]) -> dict:
    n = len(rows)
    lab = Counter(r["label"] for r in rows)
    md = Counter(str(r.get("match_detail")) for r in rows)
    def nd_label(r: dict) -> str | None:
        if r.get("label_nodiac") is not None:
            return r["label_nodiac"]
        if r.get("format") == "mcq":
            return r["label"]
        return None

    nd = [nd_label(r) for r in rows]
    have_nd = [x for x in nd if x is not None]
    legacy = [r for r, x in zip(rows, nd) if x is None and r.get("correct_nodiac") is not None]
    lab_nd = Counter(have_nd)
    n_nd = len(have_nd) + len(legacy)
    acc_nd = ((lab_nd["correct"] + sum(bool(r["correct_nodiac"]) for r in legacy)) / n_nd) if n_nd else None
    out = _stats_core(rows, n, lab, md, lab_nd, n_nd, acc_nd, have_nd, legacy)
    comp = _component_stats(rows)
    if comp:
        out["components"] = comp
    return out


def _component_stats(rows: list[dict]) -> dict:
    """T4 addresses: accuracy / outdated rate of the ward and province components
    (prediction rows carrying ``components`` = {"ward": label, "province": label})."""
    cr = [r["components"] for r in rows if isinstance(r.get("components"), dict)]
    if not cr:
        return {}
    out = {}
    for part in ("ward", "province"):
        c = Counter(x.get(part) for x in cr)
        out[part] = {"n": len(cr), "accuracy": c["correct"] / len(cr), "outdated_rate": c["outdated"] / len(cr),
                     "labels": {k: c.get(k, 0) for k in LABELS}}
    both = sum(x.get("ward") == "correct" and x.get("province") == "correct" for x in cr)
    out["both_correct_rate"] = both / len(cr)
    return out


def _stats_core(rows, n, lab, md, lab_nd, n_nd, acc_nd, have_nd, legacy) -> dict:
    return {
        "n": n,
        "accuracy": (lab["correct"] / n) if n else None,
        "outdated_rate": (lab["outdated"] / n) if n else None,
        "accuracy_nodiac": acc_nd,
        "outdated_rate_nodiac": (lab_nd["outdated"] / len(have_nd)) if have_nd and not legacy else None,
        "labels": {k: lab.get(k, 0) for k in LABELS},
        "labels_nodiac": {k: lab_nd.get(k, 0) for k in LABELS},
        "match_detail": dict(sorted(md.items())),
        "truncated": sum(bool(r.get("truncated")) for r in rows),
    }


def consistency(rows: list[dict]) -> dict:
    groups: dict[str, dict[str, list[bool]]] = defaultdict(lambda: {"surface": [], "deep": []})
    for r in rows:
        g = (r.get("meta") or {}).get("consistency_group")
        if g is None:
            continue
        kind = "surface" if r.get("qtype") == "T6_reverse" else "deep"
        groups[str(g)][kind].append(r["label"] == "correct")
    groups = {k: v for k, v in groups.items() if v["surface"] and v["deep"]}
    if not groups:
        return {"n_groups": 0}
    s_ok = {k: all(v["surface"]) for k, v in groups.items()}
    deep_s = [x for k, v in groups.items() if s_ok[k] for x in v["deep"]]
    deep_w = [x for k, v in groups.items() if not s_ok[k] for x in v["deep"]]
    n = len(groups)
    return {
        "n_groups": n,
        "n_deep_items": sum(len(v["deep"]) for v in groups.values()),
        "surface_acc": sum(s_ok.values()) / n,
        "deep_acc_given_surface": (sum(deep_s) / len(deep_s)) if deep_s else None,
        "deep_acc_given_surface_wrong": (sum(deep_w) / len(deep_w)) if deep_w else None,
        "fully_consistent_rate": sum(s_ok[k] and all(v["deep"]) for k, v in groups.items()) / n,
        "surface_only_rate": sum(s_ok[k] and not all(v["deep"]) for k, v in groups.items()) / n,
        "deep_only_rate": sum((not s_ok[k]) and all(v["deep"]) for k, v in groups.items()) / n,
    }


def aggregate(preds: Iterable[dict], items_by_id: dict[str, dict]) -> dict:
    """``preds`` rows need item_id, condition, label (+ correct_nodiac, match_detail)."""
    rows = []
    n_unknown = 0
    for p in preds:
        it = items_by_id.get(p["item_id"])
        if it is None:
            n_unknown += 1
            continue
        rows.append({**p, "qtype": it.get("qtype"), "format": it.get("format"), "meta": it.get("meta") or {}})

    by_cond: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cond[r["condition"]].append(r)

    out = {
        "n_predictions": len(rows),
        "n_unscored_predictions": n_unknown,
        "models": sorted({r.get("model") for r in rows if r.get("model")}),
        "by_condition": {},
    }
    for cond, rs in sorted(by_cond.items()):
        q: dict[str, list] = defaultdict(list)
        qc: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        fm: dict[str, list] = defaultdict(list)
        dia: dict[str, list] = defaultdict(list)
        qf: dict[str, list] = defaultdict(list)
        for r in rs:
            q[r["qtype"]].append(r)
            qc[r["qtype"]][cell_key(r["meta"])].append(r)
            fm[r["format"]].append(r)
            hd = r["meta"].get("has_diacritics")
            dia["na" if hd is None else ("with" if hd else "without")].append(r)
            qf[f"{r['qtype']}|{r['format']}"].append(r)
        out["by_condition"][cond] = {
            "all": stats(rs),
            "by_qtype": {
                k: {"all": stats(v), "cells": {c: stats(cv) for c, cv in sorted(qc[k].items())}}
                for k, v in sorted(q.items())
            },
            "by_format": {k: stats(v) for k, v in sorted(fm.items())},
            "by_diacritics": {k: stats(v) for k, v in sorted(dia.items())},
            "by_qtype_format": {k: stats(v) for k, v in sorted(qf.items())},
            "consistency": consistency(rs),
        }
    return out
