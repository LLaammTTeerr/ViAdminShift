"""Province-clustered intervals and tests for the probing track (post hoc; paper Section "Uncertainty").

Absorbed wards of one old province share their old and new province, so unit-level intervals are too narrow. For every
paired difference reported with a unit-level bootstrap (analyze_cue.py, analyze_sys.py, agent_date.py), this script adds

  * a paired cluster bootstrap 95% interval: old provinces are resampled with replacement (B=10,000, percentile), and
  * a Rademacher wild cluster bootstrap test of a zero mean difference: the null is imposed, each province's paired
    differences are multiplied by +-1, and the CR1 cluster-robust t statistic is compared with its bootstrap
    distribution (B=10,000, two-sided).

An effect counts as established when the cluster interval excludes zero and the wild test gives p < 0.05. The cluster of
a unit is its old province: the province itself for T6, the old province for absorbed T1/T1np units, the (unchanged)
province name for kept ones, and the province in the question for T5. The summary compares these with the unit-level
intervals (B=2,000) on which the prespecified criteria were evaluated, and gives the one-sided 97.5% Clopper-Pearson
upper bound for 0 of k when the provinces are taken as the effective sample size.

    python3 scripts/clustered_ci.py   # -> results/analysis/clustered.json, clustered.md
"""
import collections
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import agent_date  # noqa: E402
import analyze_sys  # noqa: E402
from analyze_cue import (API_ALIAS, CUES, HEADLINE, KEPT_SPLIT, PAPER, STRATA, UNCHANGED, analyse, boot_delta,  # noqa: E402
                         collect, label2)
from minitest import load, short  # noqa: E402

B = 10_000
SEED = 0
ALPHA = 0.05
_PROV_RE = re.compile(r"\(([^()]*)\) thuộc đơn vị hành chính cấp xã")


def cluster_of(p):
    """Old province of a probe unit (prediction or item row)."""
    if p.get("qtype", "").startswith("T5_ward_successor/"):
        m = _PROV_RE.search(p.get("question", ""))
        return short(m.group(1).split(", ")[-1]) if m else None
    return short((p.get("old") or p.get("gold"))[0])


def _t5_clusters():
    """T5 prediction rows carry no question; their province comes from the item files, by base."""
    out = {}
    for f in ("results/minitest/items/cue3sub_items.jsonl", "results/minitest/items/cue3full_items.jsonl"):
        if os.path.exists(f):
            for i in load(f):
                if i["qtype"].startswith("T5_ward_successor/"):
                    out[i["base"]] = cluster_of(i)
    return out


T5_CLUSTER = _t5_clusters()


def unit_cluster(p):
    if p.get("qtype", "").startswith("T5_ward_successor/"):
        return T5_CLUSTER.get(p["base"]) or cluster_of(p)
    return cluster_of(p)


def _sums(d, g):
    """Per-cluster sums and sizes of the paired differences d (clusters labelled g)."""
    idx = {c: k for k, c in enumerate(sorted(set(g)))}
    gi = np.array([idx[c] for c in g])
    D = np.bincount(gi, weights=d, minlength=len(idx))
    n = np.bincount(gi, minlength=len(idx)).astype(float)
    return D, n


def cluster_boot(d, g, b=B, seed=SEED):
    """Paired cluster bootstrap percentile 95% interval of mean(d): resample whole clusters."""
    D, n = _sums(np.asarray(d, float), g)
    G = len(D)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, G, size=(b, G))
    ms = np.sort(D[pick].sum(1) / n[pick].sum(1))
    return float(ms[int(0.025 * b)]), float(ms[int(0.975 * b) - 1])


def _t_cr1(D, n, N, G):
    """t statistic of the mean with CR1 cluster-robust variance; D may be a (b, G) matrix of cluster sums."""
    beta = D.sum(-1) / N
    S = D - beta[..., None] * n
    var = G / (G - 1) * (S ** 2).sum(-1) / N ** 2
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(var > 0, beta / np.sqrt(var), np.where(beta == 0, 0.0, np.sign(beta) * np.inf))
    return t


def wild_p(d, g, b=B, seed=SEED):
    """Rademacher wild cluster bootstrap p-value (null imposed, two-sided) for mean(d) = 0."""
    d = np.asarray(d, float)
    D, n = _sums(d, g)
    G, N = len(D), float(len(d))
    if G < 2 or not D.any():
        return 1.0
    t0 = abs(_t_cr1(D, n, N, G))
    rng = np.random.default_rng(seed + 1)
    w = rng.choice((-1.0, 1.0), size=(b, G))
    tb = np.abs(_t_cr1(w * D, n, N, G))
    return float((tb >= t0).mean())


def clustered(by_base, a, b_, clusters):
    """Unit-level (analyze_cue.boot_delta, B=2,000) and clustered results for mean(by_base[.][a] - by_base[.][b_])."""
    bases = [k for k, v in by_base.items() if a in v and b_ in v and clusters.get(k)]
    if not bases:
        return None
    d = [by_base[k][a] - by_base[k][b_] for k in bases]
    g = [clusters[k] for k in bases]
    u = boot_delta({k: by_base[k] for k in bases}, a, b_)
    lo, hi = cluster_boot(d, g)
    p = wild_p(d, g)
    return {"delta": sum(d) / len(d), "n": len(d), "G": len(set(g)), "unit_lo": u[1], "unit_hi": u[2],
            "cl_lo": lo, "cl_hi": hi, "wild_p": p,
            "unit_est": not (u[1] <= 0 <= u[2]), "cl_excl0": not (lo <= 0 <= hi), "established": not (lo <= 0 <= hi) and p < ALPHA}


def cue_effects(runs):
    """Delta date and Delta reform (strict and new-first) per stratum, as in analyze_cue._cell."""
    out = {}
    for key, preds in runs.items():
        preds = list(preds.values())
        meta = analyse(preds)["_meta"]
        res = {}
        for name, qt, ab in STRATA:
            ps = [p for p in preds if p["qtype"].startswith(qt + "/") and bool(p.get("absorbed")) == ab]
            groups = [(name, ps)]
            if name in dict(KEPT_SPLIT):
                groups += [(f"{name} {sub}", [p for p in ps if (short(p["gold"][0]) in UNCHANGED) == keep])
                           for sub, keep in (("unmerged", True), ("merged", False))]
            for gname, gps in groups:
                if not gps:
                    continue
                strict, new1, cl = collections.defaultdict(dict), collections.defaultdict(dict), {}
                for p in gps:
                    if p["cue"] in CUES:
                        l = label2(p)
                        strict[p["base"]][p["cue"]] = float(l == "correct")
                        new1[p["base"]][p["cue"]] = float(l in ("correct", "both_new"))
                        cl[p["base"]] = unit_cluster(p)
                cell = {}
                for c in ("date", "reform"):
                    r = clustered(strict, c, "none", cl)
                    if r:
                        cell[f"d_{c}"] = r
                    r = clustered(new1, c, "none", cl)
                    if r:
                        cell[f"d_{c}_new1st"] = r
                if cell:
                    res[gname] = cell
        out[f"{key[0]}|{key[1]}"] = {"_meta": {k: meta[k] for k in ("valid", "knows", "kept_ok")}, **res}
    return out


def sys_effects():
    """Old-only paired differences of the date-placement experiment (analyze_sys.py): date conditions against today's
    date in the system prompt, and reasoning on against off."""
    _, olds = analyze_sys.main(out=None)
    clusters = {}
    for f in ("results/minitest/items/sysdate_items.jsonl", "results/minitest/items/cue3np_items.jsonl",
              "results/minitest/items/cue3_items.jsonl"):
        for i in load(f):
            clusters.setdefault(i["base"], cluster_of(i))
    out = collections.defaultdict(dict)
    for (model, src, name), old in olds.items():
        r = {tag: clustered(old, tag, "sys1", clusters) for tag in ("sys0q", "sys0qm", "sysasof")}
        out[f"{model}|{src}"][name] = {"old_only_vs_sys1": {k: v for k, v in r.items() if v}}
    for (model, src, name), old in olds.items():
        off = olds.get((model, src[:-len("_think")], name)) if src.endswith("_think") else None
        if not off:
            continue
        res = {}
        for tag in ("sys1", "sys0q", "sys0qm", "sysasof"):
            pair = {k: {"on": old[k][tag], "off": off[k][tag]} for k in old if k in off and tag in old[k] and tag in off[k]}
            r = clustered(pair, "on", "off", clusters)
            if r:
                res[tag] = r
        out[f"{model}|{src}"][name]["old_only_think_vs_off"] = res
    return dict(out)


def n300_effects():
    """Old-only differences against today's date in the system prompt on the 300 absorbed T1np units (agent_date.py,
    reasoning off)."""
    agent_date.EXT, agent_date.PAPER_ONLY = True, False
    ext = {it["base"] for it in agent_date.items()}
    agent_date.EXT = False
    out = {}
    for m in agent_date.MODELS:
        path = agent_date.out_path(m)
        if not os.path.exists(path):
            continue
        by, cl = collections.defaultdict(dict), {}
        for p in load(path):
            if p["base"] in ext and p["absorbed"]:
                by[p["base"]][p["cond"]] = float(label2(p) == "outdated")
                cl[p["base"]] = cluster_of(p)
        r = {c: clustered(by, c, "sys1", cl) for c in ("sys0q", "sys0qm", "sysasof")}
        if all(r.values()):
            out[m] = r
    return out


def cp_upper0(n, alpha=0.025):
    """One-sided (1 - alpha) Clopper-Pearson upper bound for 0 successes in n trials."""
    return 1 - alpha ** (1 / n)


def summary(cue):
    """Prespecified decisions with cluster intervals (every knower run), and effects (Delta date and Delta reform, strict,
    per stratum, kept strata also split into merged and unmerged provinces) whose unit-level support clustering removes,
    over the knower rows of the cue table (analyze_cue.PAPER). Several such intervals end at exactly zero, so these
    counts can move by one or two with the bootstrap draws."""
    runs = {k: v for k, v in cue.items() if v["_meta"]["knows"]}
    distinct = {API_ALIAS.get(k.split("|")[0], k.split("|")[0]) for k in runs if "-nodate" not in k and "-UD-" not in k}
    knowers = {k: v for k, v in runs.items() if tuple(k.split("|", 1)) in PAPER}
    changed, lost, wild_fail = [], [], []
    for k, v in runs.items():
        h = v.get(HEADLINE, {}).get("d_reform")
        if h:
            unit_dep = h["delta"] >= 0.30 and h["unit_est"]
            cl_dep = h["delta"] >= 0.30 and h["cl_excl0"] and h["wild_p"] < ALPHA
            if unit_dep != cl_dep:
                changed.append(k)
    for k, v in knowers.items():
        for name, cell in v.items():
            if name.startswith("_"):
                continue
            for dk in ("d_date", "d_reform"):
                r = cell.get(dk)
                if not r or not r["unit_est"]:
                    continue
                if not r["cl_excl0"]:
                    lost.append((k, name, dk))
                elif r["wild_p"] >= ALPHA:
                    wild_fail.append((k, name, dk))
    return {"knowers": len(distinct), "knower_runs": len(runs), "table_rows": len(knowers), "cue_dependence_changed": changed,
            "unit_established_lost": len(lost), "unit_established_lost_kept": sum("kept" in n for _, n, _ in lost),
            "unit_established_fail_wild": len(wild_fail),
            "lost": [list(x) for x in lost], "fail_wild": [list(x) for x in wild_fail],
            "cp_upper_0_of_k": {G: cp_upper0(G) for G in (24, 29, 80)},
            "clusters_T1_absorbed": sorted({v[HEADLINE]["d_reform"]["G"] for v in knowers.values() if HEADLINE in v and "d_reform" in v[HEADLINE]})}


def pp(r):
    return (f"{100 * r['delta']:+.0f} unit [{100 * r['unit_lo']:+.0f}, {100 * r['unit_hi']:+.0f}] "
            f"cluster [{100 * r['cl_lo']:+.0f}, {100 * r['cl_hi']:+.0f}] p={r['wild_p']:.3f} G={r['G']} n={r['n']}"
            + ("" if r["established"] else "  (not established)"))


def md(res):
    L = ["# Province-clustered intervals (percentage points)", "",
         "Unit: paired unit-level bootstrap (B=2,000). Cluster: paired cluster bootstrap over old provinces (B=10,000). "
         "p: Rademacher wild cluster bootstrap (B=10,000). G: provinces, n: units.", "", "## Cue ladder (strict)", ""]
    for k, v in res["cue"].items():
        if not v["_meta"]["valid"]:
            continue
        L.append(f"### {k}{' (knower)' if v['_meta']['knows'] else ''}")
        for name, cell in v.items():
            if name.startswith("_"):
                continue
            for dk in ("d_date", "d_reform"):
                if dk in cell:
                    L.append(f"- {name}, {dk[2:]} - none: {pp(cell[dk])}")
        L.append("")
    L += ["## Date placement: old-only against today's date in the system prompt", ""]
    for k, v in res["sys"].items():
        for name, cell in v.items():
            for tag, r in cell.get("old_only_vs_sys1", {}).items():
                L.append(f"- {k}, {name}, {tag} - sys1: {pp(r)}")
            for tag, r in cell.get("old_only_think_vs_off", {}).items():
                L.append(f"- {k}, {name}, {tag}, reasoning on - off: {pp(r)}")
    L += ["", "## 300 absorbed T1np units (reasoning off): old-only against sys1", ""]
    for m, v in res["n300"].items():
        for tag, r in v.items():
            L.append(f"- {m}, {tag} - sys1: {pp(r)}")
    s = res["summary"]
    L += ["", "## Summary", "",
          f"- knowers: {s['knowers']} distinct models ({s['knower_runs']} runs); prespecified cue-dependence decisions changed by clustering: {len(s['cue_dependence_changed'])} {s['cue_dependence_changed']}",
          f"- over the {s['table_rows']} knower rows of the cue table, effects established at the unit level whose cluster interval includes zero: {s['unit_established_lost']} ({s['unit_established_lost_kept']} on kept units)",
          f"- further effects that fail the wild test: {s['unit_established_fail_wild']}",
          "- one-sided 97.5% Clopper-Pearson bound for 0 of k: " + ", ".join(f"k={G}: {100 * x:.1f}%" for G, x in s["cp_upper_0_of_k"].items())]
    return "\n".join(L) + "\n"


def main(out="results/analysis/clustered"):
    cue = cue_effects(collect("results/minitest"))
    res = {"cue": cue, "sys": sys_effects(), "n300": n300_effects()}
    res["summary"] = summary(cue)
    json.dump(res, open(out + ".json", "w"), indent=1, ensure_ascii=False)
    open(out + ".md", "w").write(md(res))
    print(md(res).split("## Summary")[1])


if __name__ == "__main__":
    main()
