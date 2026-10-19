"""Build data/wiki/passages.jsonl from Vietnamese Wikipedia revisions.

    uv run python -m viadmin.wiki.build [--no-districts] [--offline] [--workers 3] [--new-before ISO|latest]
    uv run python -m viadmin.wiki.build --codes-only     # re-attach entity_code from data/processed

For each entity (63 old provinces, 34 new provinces, 696 old districts):
* era "old": last revision strictly before OLD_CUTOFF (2025-06-12T00:00:00Z) of the page that
  carried the entity's article at that time. Titles are resolved *historically*: redirects as
  of the cut-off are followed via the old wikitext, and pages moved after the cut-off are found
  through the move log (page id follows the page across moves).
  If that revision already shows the post-reform state, earlier revisions are tried
  (repair_old / stale_reason).
* era "new": last revision of the same page (by page id) before NEW_BEFORE (2026-01-01, the
  end-2025 state matching the gold; `--new-before latest` = latest revision); kept only if it is
  after NEW_MIN (2025-07-15T00:00:00Z) and not a redirect.
Every passage is validated (entity name in lead; for districts, also parent province and unit
type); failures are excluded and logged to data/wiki/fetch_log.jsonl.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .api import ROOT, WikiClient
from .entities import Entity, nfc, new_provinces, old_districts, old_provinces
from .text import extract, find_admin_section, tidy_section, truncate

OLD_CUTOFF = "2025-06-12T00:00:00Z"
NEW_MIN = "2025-07-15T00:00:00Z"
# era "new" = last revision strictly before NEW_BEFORE: the end-2025 state matches the 1/7/2025
# gold; later revisions carry 2026 changes (Bắc Ninh / Đồng Nai / Quảng Ninh became centrally-run
# cities, some xã became phường) that contradict data/processed. `--new-before latest` = latest rev.
NEW_BEFORE = "2026-01-01T00:00:00Z"
# old-era step-back (repair_old): earlier revisions tried when the cut-off revision already
# describes the post-reform state; never earlier than the 2025-01-01 commune mergers.
STEPBACK_MIN = "2025-01-01T00:00:00Z"
STEPBACK_MAX = 10
LEAD_CHARS = 1500
ADMIN_CHARS = 8000
OUT_DIR = ROOT / "data" / "wiki"
PROCESSED = ROOT / "data" / "processed"

REDIRECT_RE = re.compile(r"^\s*#\s*(?:đổi|REDIRECT|chuyển|đổi hướng)\s*:?\s*\[\[([^\]|#]+)", re.I)
KEY_FACTS = ("Thủ phủ", "Tỉnh lỵ", "Huyện lỵ", "Thị lỵ", "Trung tâm hành chính", "Trụ sở UBND",
             "Phân chia hành chính", "Diện tích", "Tổng cộng", "Thành lập", "Mã hành chính")


# --------------------------------------------------------------------------------------------
def slug(s: str) -> str:
    s = nfc(s).replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def norm(s: str) -> str:
    """Loose comparison key: NFC, casefold, unify dashes/spaces."""
    s = nfc(s).casefold()
    s = re.sub(r"[‐-―−-]", "-", s)
    s = re.sub(r"\s*-\s*", " - ", s)
    return re.sub(r"\s+", " ", s).strip()


def redirect_target(client: WikiClient, rev: dict) -> str | None:
    if rev.get("size", 0) > 1500:
        return None
    m = REDIRECT_RE.match(client.wikitext_revision(rev["revid"]))
    return nfc(m.group(1).replace("_", " ")) if m else None


def resolve_historical(client: WikiClient, title: str, cutoff: str, trail: list[str] | None = None):
    """Return (pageid, title_at_cutoff, revision, trail) for the article at `title` as of `cutoff`.

    1) If the page was moved *away* from this title after the cut-off, that page held the title at
       the cut-off (the page now at the title may be a different article moved onto it later, e.g.
       "An Dương" = Anyang (China) today, the Hải Phòng district before). Page ids follow moves.
       If that page has no pre-cut-off revisions any more (history merged elsewhere), follow the
       move target recursively.
    2) If the title's pre-cut-off history was merged into another page (Special:MergeHistory)
       after the cut-off, follow the merge destination.
    3) Otherwise the page currently at the title; redirects as of the cut-off are followed.
    """
    trail = (trail or []) + [title]
    if len(trail) > 8:
        return None, title, None, trail
    events = [e for e in client.move_log(title) + client.merge_log(title)
              if e.get("timestamp", "") >= cutoff]
    events.sort(key=lambda e: e["timestamp"])
    pageid, rev = client.revision_before(title, cutoff)
    if rev and not events:
        tgt = redirect_target(client, rev)
        if tgt is None:
            return pageid, title, rev, trail
        return resolve_historical(client, tgt, cutoff, trail + ["(redirect@cutoff)"])
    for e in events:
        if e["type"] == "move" and e.get("logpage"):
            _, mrev = client.revision_before(pageid=e["logpage"], before=cutoff)
            if mrev:
                tgt = redirect_target(client, mrev)
                if tgt is None:
                    return e["logpage"], title, mrev, trail + [f"(moved→{e['params'].get('target_title')})"]
                return resolve_historical(client, tgt, cutoff, trail + ["(redirect@cutoff)"])
            dest = e["params"].get("target_title")
        elif e["type"] == "merge":
            dest = e["params"].get("dest_title")
        else:
            continue
        if dest and dest not in trail:
            r = resolve_historical(client, dest, cutoff, trail + [f"({e['type']}→)"])
            if r[2] is not None:
                return (r[0], title, r[2], r[3])
    # nothing better: the page currently at the title
    if rev:
        tgt = redirect_target(client, rev)
        if tgt is None:
            return pageid, title, rev, trail + ["(fallback-current)"]
        return resolve_historical(client, tgt, cutoff, trail + ["(redirect@cutoff)"])
    return None, title, None, trail


def resolve_current(client: WikiClient, title: str) -> tuple[int | None, str]:
    r = client.resolve_titles([title])[title]
    if r["missing"] or r["disambig"]:
        return None, r["title"]
    return r["pageid"], r["title"]


# --------------------------------------------------------------------------------------------
def build_texts(html: str) -> dict:
    pt = extract(html)
    lead = truncate(pt.lead, LEAD_CHARS)
    facts = []
    for line in pt.infobox:
        key = line.split(":", 1)[0]
        short = key.split(" – ")[-1]
        if any(short.startswith(k) for k in KEY_FACTS):
            facts.append(line)
    text = lead
    if len(text) < LEAD_CHARS * 0.8 and facts:
        extra = "\n".join(facts)
        text = (text + "\n" + extra).strip() if text else extra
        text = truncate(text, LEAD_CHARS, at_sentence=False)
    admin = find_admin_section(pt.sections)
    admin_heading, admin_text = (None, None)
    if admin and admin[1].strip():
        admin_heading = admin[0]
        admin_text = truncate(tidy_section(admin[1]), ADMIN_CHARS, at_sentence=False)
    code = None
    for line in pt.infobox:
        if "Mã hành chính" in line.split(":", 1)[0]:
            m = re.search(r"\d+", line.split(":", 1)[1])
            code = m.group(0) if m else None
            break
    return {"text": text, "lead_full": pt.lead, "admin_heading": admin_heading,
            "admin_text": admin_text, "infobox_text": "\n".join(pt.infobox) or None,
            "wiki_admin_code": code}


TYPE_WORDS = {"huyện": "huyện", "huyện đảo": "huyện", "quận": "quận", "thị xã": "thị xã",
              "thành phố": "thành phố"}
DISTRICT_TYPES_RE = re.compile(r"(huyện|quận|thị xã|thành phố)")
SUBJECT_TYPES_RE = re.compile(r"(đặc khu|thị trấn|phường|xã|thị xã|huyện|quận|thành phố|tỉnh|quần đảo|"
                              r"địa cấp thị|châu tự trị|phủ|làng|cầu|sông|núi)")


def first_sentence(lead: str) -> str:
    """First sentence of the (normalised) lead with parentheticals removed."""
    s = lead.split("\n", 1)[0]
    for _ in range(3):
        s = re.sub(r"\([^()]*\)", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    m = re.search(r"\.(\s|$)", s)
    return s[:m.start()] if m else s[:400]


FORMER_LEAD_RE = re.compile(r"\bcũ\b|\btrước đây là\b|\bnay là\b|\bnay thuộc\b", re.I)


def lead_marks_former(lead: str) -> bool:
    """The first sentence calls the entity a former unit ("là một huyện cũ", "trước đây là ...")."""
    return bool(FORMER_LEAD_RE.search(first_sentence(lead)))


def subject_info(ent_name: str, lead: str) -> tuple[bool, str | None, str]:
    """(entity is the grammatical subject, first admin-type word of the predicate, predicate)."""
    fs = first_sentence(lead)
    m = re.search(r"(?:^|\s)là\s", fs)
    if m:
        subj, pred = fs[:m.start() + 1], fs[m.end():]
    else:  # e.g. "Sơn Hòa một huyện miền núi ..." (missing "là")
        subj, pred = fs[:len(ent_name) + 25], fs[len(ent_name):]
    t = SUBJECT_TYPES_RE.search(pred[:60])
    return ent_name in subj, (t.group(1) if t else None), pred


def validate(ent: Entity, era: str, t: dict) -> tuple[list[str], list[str]]:
    """Return (problems, warnings). Any problem excludes the passage."""
    problems, warnings = [], []
    lead = norm(t["lead_full"][:2500])
    box = norm(t["infobox_text"] or "")
    name = norm(ent.name)
    if ent.entity_type == "province" and name.startswith("thành phố "):
        name = name[len("thành phố "):]
    if name not in lead and name not in box:
        problems.append("name_not_in_lead")
    if ent.entity_type == "district":
        is_subj, stype, pred = subject_info(name, lead)
        t["subject_type"] = stype
        if not is_subj:
            problems.append("lead_subject_not_entity")
        elif era == "old":
            want = TYPE_WORDS.get(ent.subtype or "huyện", "huyện")
            if want not in pred:
                other = DISTRICT_TYPES_RE.search(pred)
                if other:
                    warnings.append(f"subtype_differs:{other.group(1)}")
                else:
                    problems.append("type_word_not_in_lead")
        elif era == "new" and stype in ("phường", "xã", "đặc khu", "thị trấn"):
            warnings.append(f"new_page_is_commune:{stype}")
        if era == "old":
            parent = norm(ent.parent_name or "")
            if lead_marks_former(lead):
                warnings.append("premature_lead")
            alt = {parent, parent.replace("huế", "thừa thiên huế")}
            if not any(p in lead + " " + box for p in alt):
                problems.append("parent_not_in_lead")
    return problems, warnings


def make_passage(client: WikiClient, ent: Entity, era: str, pageid: int, title: str,
                 rev: dict) -> tuple[dict | None, dict]:
    parsed = client.parse_revision(rev["revid"])
    html = parsed["text"]
    log = {"entity_set": ent.entity_set, "name": ent.name, "parent": ent.parent_name,
           "subtype": ent.subtype, "era": era, "page_id": pageid, "title": title,
           "revision_id": rev["revid"], "revision_timestamp": rev["timestamp"]}
    if "redirectMsg" in html[:3000]:
        log["status"] = "redirect"
        return None, log
    t = build_texts(html)
    problems, warnings = validate(ent, era, t)
    log["problems"] = problems
    if warnings:
        log["warnings"] = warnings
    log["lead_head"] = t["lead_full"][:200]
    if problems:
        log["status"] = "rejected"
        return None, log
    log["status"] = "ok"
    if ent.entity_type == "district":
        key = f"{slug(ent.parent_name or '')}--{slug(ent.subtype or '')}-{slug(ent.name)}"
    else:
        key = slug(ent.name)
    row = {
        "passage_id": f"wiki-{ent.entity_set.replace('_', '')}-{key}-{era}",
        "title": title,
        "entity_type": ent.entity_type,
        "entity_set": ent.entity_set,
        "entity_name": ent.name,
        "entity_subtype": ent.subtype,
        "parent_name": ent.parent_name,
        "entity_code": None,
        "entity_code_method": None,
        "lead_subject_type": t.get("subject_type"),
        "wiki_admin_code": t["wiki_admin_code"],
        "era": era,
        "page_id": pageid,
        "revision_id": rev["revid"],
        "revision_timestamp": rev["timestamp"],
        "text": t["text"],
        "admin_heading": t["admin_heading"],
        "admin_text": t["admin_text"],
        "infobox_text": t["infobox_text"],
    }
    return row, log


def process_entity(client: WikiClient, ent: Entity, new_before: str | None,
                   old_fallback: dict[str, tuple] | None = None) -> tuple[list[dict], list[dict]]:
    rows, logs = [], []
    # ---- page identification
    if ent.entity_set == "new_province":
        pageid, cur_title = resolve_current(client, ent.link_title)
        old_pid, old_title, old_rev = None, None, None
        if pageid:
            _, old_rev = client.revision_before(pageid=pageid, before=OLD_CUTOFF)
            old_pid, old_title = pageid, ent.name
            if old_rev and redirect_target(client, old_rev):
                old_rev = None
        if old_rev is None and old_fallback and ent.name in old_fallback:
            old_pid, old_title, old_rev = old_fallback[ent.name]
    else:
        old_pid, old_title, old_rev, trail = resolve_historical(client, ent.link_title, OLD_CUTOFF)
        pageid = old_pid
        cur_title = None
    # ---- old era
    if old_rev:
        r, lg = make_passage(client, ent, "old", old_pid, old_title, old_rev)
        logs.append(lg)
        if r:
            rows.append(r)
    else:
        logs.append({"entity_set": ent.entity_set, "name": ent.name, "parent": ent.parent_name,
                     "subtype": ent.subtype, "era": "old", "status": "no_revision",
                     "link_title": ent.link_title})
    # ---- new era
    if pageid:
        if new_before:
            _, new_rev = client.revision_before(pageid=pageid, before=new_before)
        else:
            _, new_rev = client.latest_revision(pageid=pageid)
        if cur_title is None:
            info = client.get(action="query", pageids=pageid)
            cur_title = info["query"]["pages"][0].get("title")
        if new_rev and new_rev["timestamp"] >= NEW_MIN and not redirect_target(client, new_rev):
            r, lg = make_passage(client, ent, "new", pageid, cur_title, new_rev)
            logs.append(lg)
            if r:
                rows.append(r)
        else:
            logs.append({"entity_set": ent.entity_set, "name": ent.name, "parent": ent.parent_name,
                         "subtype": ent.subtype, "era": "new", "page_id": pageid,
                         "status": "no_new_revision" if not new_rev or new_rev["timestamp"] < NEW_MIN
                         else "redirect_now",
                         "latest_timestamp": new_rev["timestamp"] if new_rev else None})
    else:
        logs.append({"entity_set": ent.entity_set, "name": ent.name, "era": "new",
                     "parent": ent.parent_name, "subtype": ent.subtype, "status": "no_page"})
    return rows, logs


# --------------------------------------------------------------------------------------------
_PREFIXES = ("thành phố ", "tỉnh ", "tp. ", "tp ", "quận ", "huyện ", "thị xã ")


def _strip_prefix(name: str) -> str:
    n = norm(name)
    if n in ("thành phố hồ chí minh", "tp. hồ chí minh", "tp hồ chí minh"):
        return "hồ chí minh"
    for p in _PREFIXES:
        if n.startswith(p):
            return n[len(p):]
    return n


def _key_name(r: dict) -> str:
    return _strip_prefix(r.get("short_name") or r["name"])


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


def loose_key(name: str) -> str:
    """Spelling-variant-insensitive key: tone placement (Hoà/Hòa), Đak/Đăk, spacing, apostrophes."""
    from .report import canon
    k = canon(_strip_prefix(name)).casefold()
    k = k.replace("đăk", "đak").replace("đắk", "đak").replace("căng", "cang").replace("'", "")
    return re.sub(r"[\s\-]+", "", k)


def _fold(s: str) -> str:
    s = nfc(s).replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn").casefold()


def attach_codes(rows: list[dict]) -> dict:
    """Fill entity_code (+ entity_code_method) from data/processed tables. Returns stats.

    Provinces: normalised short name. Districts: (name, old province code[, type]) exact, then a
    spelling-variant-insensitive key, then the infobox "Mã hành chính" if it names a district of
    the same province with a similar (diacritic-folded, fuzzy >= 70) name."""
    from rapidfuzz import fuzz
    pold = {_key_name(r): r for r in _load(PROCESSED / "provinces_old.jsonl")}
    pnew = {_key_name(r): r for r in _load(PROCESSED / "provinces_new.jsonl")}
    dlist = _load(PROCESSED / "districts_old.jsonl")
    dold: dict[tuple, list[dict]] = {}
    dloose: dict[tuple, list[dict]] = {}
    dcode = {r["code"]: r for r in dlist}
    for r in dlist:
        dold.setdefault((_key_name(r), r["province_code"]), []).append(r)
        dloose.setdefault((loose_key(r.get("short_name") or r["name"]), r["province_code"]), []).append(r)
    stats: dict = {"tables_present": bool(pold or pnew or dold), "joined": 0, "unjoined": 0,
                   "code_mismatch": [], "methods": {}}
    if not stats["tables_present"]:
        return stats
    # old-era infobox code per district entity (shared by its old/new rows)
    ent_key = lambda r: (r["entity_set"], r["parent_name"], r["entity_subtype"], r["entity_name"])
    old_wc = {ent_key(r): r.get("wiki_admin_code") for r in rows if r["era"] == "old"}
    for row in rows:
        code, method = None, None
        if row["entity_set"] == "old_province":
            code = (pold.get(_strip_prefix(row["entity_name"])) or {}).get("code")
            method = "name" if code else None
        elif row["entity_set"] == "new_province":
            code = (pnew.get(_strip_prefix(row["entity_name"])) or {}).get("code")
            method = "name" if code else None
        elif row["entity_set"] == "old_district":
            pc = (pold.get(_strip_prefix(row["parent_name"] or "")) or {}).get("code")
            want = "huyện" if row["entity_subtype"] == "huyện đảo" else (row["entity_subtype"] or "")
            for meth, cands in (("name", dold.get((_strip_prefix(row["entity_name"]), pc), [])),
                                ("name_variant", dloose.get((loose_key(row["entity_name"]), pc), []))):
                if len(cands) > 1:
                    cands = [c for c in cands if norm(c.get("type", "")) == norm(want)]
                if len(cands) == 1:
                    code, method = cands[0]["code"], meth
                    if norm(cands[0].get("type", "")) != norm(want):
                        stats.setdefault("district_type_mismatch", []).append(
                            (row["passage_id"], want, cands[0].get("type")))
                    break
            if code is None:
                wc = old_wc.get(ent_key(row))
                cand = dcode.get(wc.zfill(3)) if wc else None
                if cand and cand["province_code"] == pc and fuzz.ratio(
                        _fold(_strip_prefix(cand.get("short_name") or cand["name"])),
                        _fold(_strip_prefix(row["entity_name"]))) >= 70:
                    code, method = cand["code"], "wiki_infobox_code"
        row["entity_code"] = code
        row["entity_code_method"] = method
        stats["methods"][str(method)] = stats["methods"].get(str(method), 0) + 1
        if code is None:
            stats["unjoined"] += 1
        else:
            stats["joined"] += 1
            wc = row.get("wiki_admin_code")
            # the infobox code should describe the entity in the era matching its table
            era_matches = (row["era"] == "new") == (row["entity_set"] == "new_province")
            if wc and era_matches and str(code).isdigit() and wc.isdigit() and int(wc) != int(code):
                stats["code_mismatch"].append((row["passage_id"], wc, code))
    return stats


# --------------------------------------------------------------------------------------------
def _gold_old_wards() -> dict[str, list[str]]:
    by: dict[str, list[str]] = {}
    for w in _load(PROCESSED / "wards_old.jsonl"):
        by.setdefault(w["district_code"], []).append(w.get("short_name") or w["name"])
    return by


def stale_reason(row: dict, gold: dict[str, list[str]]) -> str | None:
    """Why an old-era passage already describes the post-reform state (None if it does not).

    * premature_lead: its first sentence calls the entity former ("là một huyện cũ").
    * stale_admin (districts, needs the gold join): < 50% of the district's gold old wards are
      named in admin_text AND the stated commune count differs from the gold count (e.g. Hoài
      Nhơn rev 73537879: "7 phường: Hoài Nhơn Bắc, ..." vs 17 gold units). Spelling-only misses
      (Ia/Ea, Đăk/Đắk) keep the stated count equal to gold and are not flagged."""
    from .report import name_in_text, stated_commune_count
    if row["era"] != "old":
        return None
    if lead_marks_former(row["text"]):
        return "premature_lead"
    if row["entity_set"] == "old_district" and row.get("entity_code"):
        names = gold.get(row["entity_code"], [])
        if names:
            found = sum(1 for n in names if name_in_text(n, row.get("admin_text") or ""))
            stated = stated_commune_count(row)
            if found / len(names) < 0.5 and stated is not None and stated != len(names):
                return f"stale_admin:{found}/{len(names)} named, stated {stated}"
    return None


def _entity_of(row: dict) -> Entity:
    return Entity(row["entity_set"], row["entity_type"], row["entity_name"], row["title"],
                  row.get("parent_name"), row.get("entity_subtype"))


def repair_old(client: WikiClient, rows: list[dict], logs: list[dict],
               gold: dict[str, list[str]] | None = None) -> tuple[list[dict], list[dict]]:
    """Step back over earlier revisions (<= STEPBACK_MAX, not before STEPBACK_MIN) of the same page
    for old-era passages whose cut-off revision already shows the post-reform state (stale_reason).
    The newest earlier revision that validates and is not stale replaces the row; if none does,
    the passage is dropped (a wrong 'old' passage is worse than a missing one). Logged."""
    gold = _gold_old_wards() if gold is None else gold
    out = []
    for row in rows:
        reason = stale_reason(row, gold)
        if reason is None:
            out.append(row)
            continue
        ent = _entity_of(row)
        tried, new_row = [], None
        for rev in client.revisions_before(row["page_id"], row["revision_timestamp"], STEPBACK_MAX):
            if rev["timestamp"] < STEPBACK_MIN:
                break
            r, lg = make_passage(client, ent, "old", row["page_id"], row["title"], rev)
            tried.append(rev["revid"])
            if r is None:
                continue
            for k in ("entity_code", "entity_code_method"):
                r[k] = row[k]
            if stale_reason(r, gold) is None:
                new_row = r
                break
        log = {"entity_set": row["entity_set"], "name": row["entity_name"],
               "parent": row.get("parent_name"), "subtype": row.get("entity_subtype"), "era": "old",
               "page_id": row["page_id"], "title": row["title"], "stale_revision_id": row["revision_id"],
               "stale_revision_timestamp": row["revision_timestamp"], "stale_reason": reason,
               "tried_revision_ids": tried}
        for old_log in logs:   # the cut-off revision's own log line no longer describes a passage
            if (old_log.get("era") == "old" and old_log.get("revision_id") == row["revision_id"]
                    and old_log.get("entity_set") == row["entity_set"]
                    and old_log.get("name") == row["entity_name"]
                    and old_log.get("parent") == row.get("parent_name")):
                old_log["status"] = "superseded_stale"
        if new_row:
            log.update(status="stepped_back", revision_id=new_row["revision_id"],
                       revision_timestamp=new_row["revision_timestamp"])
            out.append(new_row)
        else:
            log["status"] = "rejected_stale_content"
        logs.append(log)
    return out, logs


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--no-districts", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--new-before", default=NEW_BEFORE,
                    help=f"ISO timestamp: era 'new' = last revision before it (default {NEW_BEFORE}); "
                         "'latest' = latest revision")
    ap.add_argument("--codes-only", action="store_true")
    ap.add_argument("--out", default=str(OUT_DIR / "passages.jsonl"))
    a = ap.parse_args(argv)
    out = Path(a.out)
    if a.codes_only:
        rows = _load(out)
        print(attach_codes(rows))
        write_jsonl(out, rows)
        return
    new_before = None if a.new_before == "latest" else a.new_before
    client = WikiClient(offline=a.offline)
    olds, news = old_provinces(client), new_provinces(client)
    dists = [] if a.no_districts else old_districts(client)
    print(f"entities: {len(olds)} old provinces, {len(news)} new provinces, {len(dists)} districts",
          file=sys.stderr)

    def run(ents, fallback=None):
        with ThreadPoolExecutor(a.workers) as ex:
            res = list(ex.map(lambda e: process_entity(client, e, new_before, fallback), ents))
        return res

    res_old = run(olds)
    fallback = {}
    for ent, (rows, _logs) in zip(olds, res_old):
        for r in rows:
            if r["era"] == "old":
                fallback[ent.name] = (r["page_id"], r["title"],
                                      {"revid": r["revision_id"], "timestamp": r["revision_timestamp"]})
    res_new = run(news, fallback)
    res_dist = run(dists) if dists else []
    rows, logs = [], []
    for rs, ls in res_old + res_new + res_dist:
        rows.extend(rs)
        logs.extend(ls)
    ids = [r["passage_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate passage ids"
    stats = attach_codes(rows)
    rows, logs = repair_old(client, rows, logs)
    write_jsonl(out, rows)
    write_jsonl(out.parent / "fetch_log.jsonl", logs)
    print(f"wrote {len(rows)} passages; live requests {client.live_requests}; codes {stats}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
