"""Offline tests for historical title resolution and passage validation (stub API client)."""
from viadmin.wiki.build import resolve_historical, subject_info, validate
from viadmin.wiki.entities import Entity

CUT = "2025-06-12T00:00:00Z"


class StubClient:
    """pages: pageid -> list of (timestamp, revid, size, wikitext); titles: title -> pageid now."""

    def __init__(self, pages, titles, moves=None, merges=None):
        self.pages, self.titles = pages, titles
        self.moves, self.merges = moves or {}, merges or {}

    def _before(self, pid, before):
        revs = [r for r in self.pages.get(pid, []) if r[0] < before]
        if not revs:
            return pid, None
        ts, revid, size, _ = max(revs)
        return pid, {"revid": revid, "timestamp": ts, "size": size}

    def revision_before(self, title=None, before="", pageid=None):
        pid = pageid or self.titles.get(title)
        return (None, None) if pid is None else self._before(pid, before)

    def wikitext_revision(self, revid):
        for revs in self.pages.values():
            for r in revs:
                if r[1] == revid:
                    return r[3]
        raise KeyError(revid)

    def move_log(self, title):
        return self.moves.get(title, [])

    def merge_log(self, title):
        return self.merges.get(title, [])


def test_article_moved_away_and_title_reused():
    # page 1 = district article at "An Dương" until 2025-07; page 2 = Anyang article moved onto it.
    pages = {1: [("2025-05-31T00:00:00Z", 11, 9000, "An Dương là một quận")],
             2: [("2025-03-17T00:00:00Z", 21, 9000, "An Dương (Trung Quốc)")]}
    titles = {"An Dương": 2, "An Dương (quận)": 1}
    moves = {"An Dương": [{"type": "move", "timestamp": "2025-07-02T00:00:00Z", "logpage": 1,
                           "params": {"target_title": "An Dương (quận)"}}]}
    pid, title, rev, _ = resolve_historical(StubClient(pages, titles, moves), "An Dương", CUT)
    assert pid == 1 and rev["revid"] == 11 and title == "An Dương"


def test_redirect_at_cutoff_is_followed():
    pages = {1: [("2024-12-31T00:00:00Z", 11, 17, "#đổi [[Huế]]")],
             2: [("2025-05-27T00:00:00Z", 21, 9000, "Huế là thành phố")]}
    titles = {"Thừa Thiên Huế": 1, "Huế": 2}
    pid, _, rev, _ = resolve_historical(StubClient(pages, titles), "Thừa Thiên Huế", CUT)
    assert pid == 2 and rev["revid"] == 21


def test_history_merged_elsewhere():
    pages = {1: [("2025-09-03T00:00:00Z", 12, 40, "#đổi [[X (định hướng)]]")],
             3: [("2025-05-25T00:00:00Z", 31, 9000, "Hoài Nhơn là một thị xã"),
                 ("2025-09-02T00:00:00Z", 32, 9000, "Hoài Nhơn là thị xã cũ")]}
    titles = {"Hoài Nhơn": 1, "Hoài Nhơn (thị xã)": 3}
    merges = {"Hoài Nhơn": [{"type": "merge", "timestamp": "2025-10-23T00:00:00Z",
                             "params": {"dest_title": "Hoài Nhơn (thị xã)"}}]}
    pid, title, rev, _ = resolve_historical(StubClient(pages, titles, merges=merges), "Hoài Nhơn", CUT)
    assert pid == 3 and rev["revid"] == 31 and title == "Hoài Nhơn"


def test_no_history_before_cutoff():
    pages = {1: [("2025-08-01T00:00:00Z", 11, 9000, "new page")]}
    assert resolve_historical(StubClient(pages, {"X": 1}), "X", CUT)[2] is None


def _t(lead, box=""):
    return {"lead_full": lead, "infobox_text": box}


def test_validate_district():
    ent = Entity("old_district", "district", "Châu Thành", "Châu Thành, Tiền Giang",
                 parent_name="Tiền Giang", subtype="huyện")
    ok, _ = validate(ent, "old", _t("Châu Thành là một huyện thuộc tỉnh Tiền Giang, Việt Nam."))
    assert ok == []
    bad, _ = validate(ent, "old", _t("Tân Hiệp là thị trấn huyện lỵ của huyện Châu Thành, tỉnh Tiền Giang."))
    assert "lead_subject_not_entity" in bad
    wrong_prov, _ = validate(ent, "old", _t("Châu Thành là một huyện thuộc tỉnh Long An, Việt Nam."))
    assert "parent_not_in_lead" in wrong_prov
    china, _ = validate(Entity("old_district", "district", "Mai Châu", "Mai Châu", "Hòa Bình", "huyện"),
                        "old", _t("Mai Châu (tiếng Trung: 梅州) là địa cấp thị ở tỉnh Quảng Đông, Trung Quốc."))
    assert "type_word_not_in_lead" in china and "parent_not_in_lead" in china


def test_subject_info_strips_parentheticals():
    is_subj, stype, _ = subject_info("na hang", "na hang (tên chính xác là nà hang - ruộng là đây) là một huyện")
    assert is_subj and stype == "huyện"


# ---- old-era step-back (review finding: Hoài Nhơn rev 73537879 already listed the 7 new phường)
from viadmin.wiki.build import lead_marks_former, repair_old, stale_reason  # noqa: E402


def _html(lead: str, admin: str) -> str:
    return (f'<div class="mw-parser-output"><p>{lead}</p>'
            f'<div class="mw-heading mw-heading2"><h2>Hành chính</h2></div><p>{admin}</p></div>')


OLD17 = ("Thị xã Hoài Nhơn có 17 đơn vị hành chính cấp xã trực thuộc, bao gồm 11 phường: Bồng Sơn, "
         "Hoài Đức, Hoài Hảo, Hoài Hương, Hoài Tân, Hoài Thanh, Hoài Thanh Tây, Hoài Xuân, Tam Quan, "
         "Tam Quan Bắc, Tam Quan Nam và 6 xã: Hoài Châu, Hoài Châu Bắc, Hoài Hải, Hoài Mỹ, Hoài Phú, "
         "Hoài Sơn.")
NEW7 = ("Thị xã Hoài Nhơn có 7 đơn vị hành chính cấp xã trực thuộc, bao gồm 7 phường: Bồng Sơn, "
        "Hoài Nhơn Bắc, Tam Quan, Hoài Nhơn, Hoài Nhơn Đông, Hoài Nhơn Nam và Hoài Nhơn Tây.")
GOLD17 = ["Bồng Sơn", "Hoài Đức", "Hoài Hảo", "Hoài Hương", "Hoài Tân", "Hoài Thanh", "Hoài Thanh Tây",
          "Hoài Xuân", "Tam Quan", "Tam Quan Bắc", "Tam Quan Nam", "Hoài Châu", "Hoài Châu Bắc",
          "Hoài Hải", "Hoài Mỹ", "Hoài Phú", "Hoài Sơn"]
LEAD = "Hoài Nhơn là một thị xã thuộc tỉnh Bình Định, Việt Nam."


class StepBackClient:
    def __init__(self, revs):   # revs: newest first, (revid, timestamp, html)
        self.revs = revs

    def revisions_before(self, pageid, before, limit=20):
        return [{"revid": r, "timestamp": t} for r, t, _ in self.revs if t < before][:limit]

    def parse_revision(self, revid):
        return {"text": next(h for r, _, h in self.revs if r == revid)}


def _row(revid, ts, html):
    from viadmin.wiki.build import make_passage
    ent = Entity("old_district", "district", "Hoài Nhơn", "Hoài Nhơn", "Bình Định", "thị xã")
    r, _ = make_passage(StepBackClient([(revid, ts, html)]), ent, "old", 1, "Hoài Nhơn",
                        {"revid": revid, "timestamp": ts})
    r["entity_code"], r["entity_code_method"] = "540", "name"
    return r


def test_repair_old_steps_back_past_premature_revisions():
    revs = [(4, "2025-05-25T00:00:00Z", _html(LEAD, NEW7)),     # selected at cut-off (stale)
            (3, "2025-05-23T00:00:00Z", _html(LEAD, NEW7)),     # anonymous re-application
            (2, "2025-05-22T00:00:00Z", _html(LEAD, OLD17)),    # stable revision
            (1, "2025-05-21T00:00:00Z", _html(LEAD, OLD17))]
    gold = {"540": GOLD17}
    row = _row(4, revs[0][1], revs[0][2])
    assert stale_reason(row, gold).startswith("stale_admin")
    orig_log = {"era": "old", "revision_id": 4, "entity_set": "old_district", "name": "Hoài Nhơn",
                "parent": "Bình Định", "status": "ok"}
    rows, logs = repair_old(StepBackClient(revs), [row], [orig_log], gold)
    assert logs[0]["status"] == "superseded_stale"
    assert [r["revision_id"] for r in rows] == [2]
    assert rows[0]["entity_code"] == "540" and stale_reason(rows[0], gold) is None
    assert logs[-1]["status"] == "stepped_back" and logs[-1]["tried_revision_ids"] == [3, 2]


def test_repair_old_drops_when_no_clean_revision():
    revs = [(4, "2025-05-25T00:00:00Z", _html(LEAD, NEW7)),
            (3, "2024-12-01T00:00:00Z", _html(LEAD, OLD17))]   # before STEPBACK_MIN: not used
    rows, logs = repair_old(StepBackClient(revs), [_row(4, revs[0][1], revs[0][2])], [], {"540": GOLD17})
    assert rows == [] and logs[-1]["status"] == "rejected_stale_content"


def test_lead_marks_former():
    assert lead_marks_former("Quỳnh Lưu là một huyện cũ đồng bằng ven biển nằm ở phía đông bắc tỉnh Nghệ An.")
    assert lead_marks_former("Bà Rịa trước đây là thành phố tỉnh lỵ thuộc tỉnh Bà Rịa – Vũng Tàu.")
    assert not lead_marks_former("Quỳnh Lưu là một huyện đồng bằng ven biển nằm ở phía đông bắc tỉnh Nghệ An.")
    # spelling-only misses with a matching stated count are not stale
    row = {"era": "old", "entity_set": "old_district", "entity_code": "1", "entity_name": "Mang Yang",
           "text": "Mang Yang là một huyện thuộc tỉnh Gia Lai.",
           "admin_text": "Huyện Mang Yang có 2 đơn vị hành chính cấp xã trực thuộc, bao gồm 2 xã: Ia Ba, Đăk Yă."}
    assert stale_reason(row, {"1": ["Ia Bă", "Đắk Yă"]}) is None
