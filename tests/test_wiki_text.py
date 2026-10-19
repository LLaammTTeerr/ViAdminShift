"""Offline tests for the MediaWiki HTML -> plain text cleaner (viadmin.wiki.text)."""
import unicodedata

from viadmin.wiki.text import (clean_text, extract, find_admin_section, is_redirect_html,
                               tidy_section, truncate)

PAGE = """
<div class="mw-content-ltr mw-parser-output" lang="vi" dir="ltr">
<style>.mw-parser-output .ambox{border:1px}</style>
<table class="box-Chú_thích plainlinks metadata ambox"><tbody><tr><td>Bài viết này cần thêm chú thích.</td></tr></tbody></table>
<div role="note" class="hatnote navigation-not-searchable">Bài này viết về tỉnh. Đối với thành phố, xem X.</div>
<table class="infobox"><tbody>
<tr><th colspan="2">Tuyên Quang</th></tr>
<tr><th colspan="2" class="infobox-header">Hành chính</th></tr>
<tr><th scope="row" class="infobox-label">Tỉnh lỵ</th><td class="infobox-data">Phường <a href="/wiki/Minh_Xuân">Minh Xuân</a><sup class="reference"><a href="#c1">[1]</a></sup></td></tr>
<tr><th scope="row" class="infobox-label">Phân chia hành chính</th><td class="infobox-data">7 phường, 117 xã</td></tr>
<tr><th colspan="2" class="infobox-header">Khác</th></tr>
<tr><th scope="row" class="infobox-label">Mã hành chính</th><td class="infobox-data">08</td></tr>
</tbody></table>
<p><b>Tuyên Quang</b> là một tỉnh thuộc vùng <a href="/wiki/Đông_Bắc_Bộ">Đông Bắc Bộ</a>, Việt Nam.<sup id="cite_ref-1" class="reference"><a href="#cite_note-1"><span class="cite-bracket">[</span>1<span class="cite-bracket">]</span></a></sup>
</p>
<p>Năm 2025, tỉnh được sáp nhập với Hà Giang.<sup class="noprint Inline-Template"><i>[cần dẫn nguồn]</i></sup></p>
<div class="mw-heading mw-heading2"><h2 id="Địa_lý">Địa lý<span class="mw-editsection">[sửa]</span></h2></div>
<p>Địa hình đồi núi.</p>
<figure><img src="x.png"/><figcaption>Một bức ảnh</figcaption></figure>
<div class="mw-heading mw-heading2"><h2 id="Hành_chính">Hành chính</h2></div>
<div role="note" class="hatnote">Bài chi tiết: Danh sách đơn vị hành chính</div>
<p>Tỉnh có 124 đơn vị hành chính cấp xã.</p>
<table class="wikitable"><tbody>
<tr><th>Tên</th><th>Diện tích<br />(km²)</th></tr>
<tr><td colspan="2"><b>Phường (2)</b></td></tr>
<tr><td><a href="/wiki/An_Tường">An Tường</a></td><td>53,44</td></tr>
<tr><td><a href="/wiki/Minh_Xuân">Minh Xuân</a></td><td>34,90</td></tr>
</tbody></table>
<table class="wikitable"><tbody>
<tr><th>Tên</th><th>Diện tích<br />(km²)</th></tr>
<tr><td>Bạch Đích</td><td>95,17</td></tr>
</tbody></table>
<p>Nguồn: Nghị quyết 1684/NQ-UBTVQH15</p>
<div class="mw-heading mw-heading3"><h3 id="Lịch_sử_hành_chính">Lịch sử hành chính</h3></div>
<ul><li>Năm 1991 tái lập tỉnh.</li></ul>
<div class="mw-heading mw-heading2"><h2 id="Kinh_tế">Kinh tế</h2></div>
<p>Nông nghiệp.</p>
<div class="navbox"><table><tr><td>Các tỉnh Việt Nam</td></tr></table></div>
<div class="mw-references-wrap"><ol class="references"><li>Nguồn 1</li></ol></div>
</div>
"""


def test_lead_drops_noise_and_references():
    pt = extract(PAGE)
    assert pt.lead.startswith("Tuyên Quang là một tỉnh thuộc vùng Đông Bắc Bộ, Việt Nam.")
    assert "[1]" not in pt.lead and "cần dẫn nguồn" not in pt.lead
    assert "chú thích" not in pt.lead.lower()          # maintenance box removed
    assert "Bài này viết về" not in pt.lead            # hatnote removed
    assert "Tỉnh lỵ" not in pt.lead                    # infobox not in prose
    assert "Năm 2025, tỉnh được sáp nhập với Hà Giang." in pt.lead


def test_infobox_key_value_lines():
    pt = extract(PAGE)
    assert "Hành chính – Tỉnh lỵ: Phường Minh Xuân" in pt.infobox
    assert "Phân chia hành chính: 7 phường, 117 xã" in pt.infobox
    assert "Khác – Mã hành chính: 08" in pt.infobox


def test_sections_and_admin_section():
    pt = extract(PAGE)
    titles = [(s.level, s.title) for s in pt.sections]
    assert titles == [(2, "Địa lý"), (2, "Hành chính"), (3, "Lịch sử hành chính"), (2, "Kinh tế")]
    assert "Một bức ảnh" not in pt.sections[0].text      # figure dropped
    head, admin = find_admin_section(pt.sections)
    assert head == "Hành chính"
    assert "Tỉnh có 124 đơn vị hành chính cấp xã." in admin
    assert "An Tường | 53,44" in admin
    assert "Tên | Diện tích (km²)" in admin               # <br> inside a cell -> space
    assert "Bài chi tiết" not in admin
    assert "Năm 1991 tái lập tỉnh." in admin             # subsection included
    assert "Nông nghiệp" not in admin                     # next h2 excluded
    tidy = tidy_section(admin)
    assert tidy.count("Tên | Diện tích (km²)") == 1       # repeated table header removed
    assert "Nguồn:" not in tidy


def test_admin_section_variants():
    from viadmin.wiki.text import Section
    secs = [Section("Lịch sử hành chính", 2, "cũ"), Section("Kinh tế", 2, "x"),
            Section("Đơn vị hành chính", 2, "mới"), Section("Xã", 3, "A, B")]
    head, txt = find_admin_section(secs)
    assert head == "Đơn vị hành chính" and txt == "mới\nXã\nA, B"
    assert find_admin_section([Section("Kinh tế", 2, "x")]) is None
    # history-only heading is used only as a fallback when nothing better exists... but never
    # when it starts with "Lịch sử"
    assert find_admin_section([Section("Lịch sử hành chính", 2, "cũ")]) is None


def test_nfc_and_cleanup():
    decomposed = unicodedata.normalize("NFD", "Thừa Thiên Huế [12] , abc")
    out = clean_text(decomposed)
    assert out == "Thừa Thiên Huế, abc"
    assert unicodedata.is_normalized("NFC", out)


def test_truncate_boundaries():
    s = "Câu một. Câu hai dài hơn. Câu ba."
    assert truncate(s, 100) == s
    assert truncate(s, 28) == "Câu một. Câu hai dài hơn."
    lines = "\n".join(f"dòng {i}" for i in range(100))
    t = truncate(lines, 50, at_sentence=False)
    assert len(t) <= 50 and t.endswith(t.split("\n")[-1]) and "\n" in t


def test_redirect_detection():
    assert is_redirect_html('<div class="redirectMsg"><p>Đổi hướng đến:</p></div>')
    assert not is_redirect_html(PAGE)


def test_unbalanced_html_does_not_crash():
    pt = extract('<div class="mw-parser-output"><p>Văn <b>bản</p><p>thứ hai</i></p></div>')
    assert "Văn bản" in pt.lead and "thứ hai" in pt.lead


def test_admin_section_prefers_exact_subsection():
    from viadmin.wiki.text import Section
    secs = [Section("Tổ chức hành chính và chính quyền", 2, ""),
            Section("Tổ chức hành chính", 3, "30 quận huyện"),
            Section("Chính quyền", 3, "HĐND")]
    assert find_admin_section(secs) == ("Tổ chức hành chính", "30 quận huyện")


def test_map_overlay_labels_dropped():
    html = ('<div class="mw-parser-output"><p>Lead.</p><h2>Hành chính</h2>'
            '<div style="position: absolute; left: 10px">Q. Ninh Kiều</div><p>9 quận huyện.</p></div>')
    pt = extract(html)
    assert find_admin_section(pt.sections) == ("Hành chính", "9 quận huyện.")


def test_commune_navbox_inside_admin_section_is_kept():
    html = ('<div class="mw-parser-output"><p>Lead.</p>'
            '<div class="mw-heading mw-heading2"><h2>Hành chính</h2></div>'
            '<p>Huyện có 3 xã:</p>'
            '<div role="navigation" class="navbox"><table class="nowraplinks navbox-inner"><tbody>'
            '<tr><th colspan="2" class="navbox-title"><div class="navbar plainlinks"><ul><li>x</li>'
            '<li>t</li></ul></div><div>Xã thuộc huyện Ba Tơ</div></th></tr>'
            '<tr><th class="navbox-group">Xã (3)</th><td class="navbox-list"><div><ul>'
            '<li>Ba Bích</li><li>Ba Cung</li><li>Ba Dinh</li></ul></div></td></tr>'
            '</tbody></table></div>'
            '<div class="mw-heading mw-heading2"><h2>Xem thêm</h2></div>'
            '<div role="navigation" class="navbox"><table class="navbox-inner"><tbody>'
            '<tr><th class="navbox-title">Các tỉnh Việt Nam</th></tr></tbody></table></div></div>')
    pt = extract(html)
    head, admin = find_admin_section(pt.sections)
    assert "Ba Bích" in admin and "Ba Dinh" in admin and "Xã thuộc huyện Ba Tơ" in admin
    assert "x\n" not in admin and "\nt\n" not in admin   # navbar v/t/e links dropped
    assert all("Các tỉnh Việt Nam" not in s.text for s in pt.sections)   # other navboxes dropped


def test_tidy_section_drops_template_lines():
    from viadmin.wiki.text import tidy_section
    t = "Huyện có 3 xã.\nBản mẫu:Huyện thị Quảng Ngãi\nXã | Diện tích\nNguồn: GSO"
    assert tidy_section(t) == "Huyện có 3 xã.\nXã | Diện tích"
