from viadmin.wiki.report import canon, name_in_text


def test_canon_tone_placement_and_dashes():
    assert canon("Định Hoá") == canon("Định Hóa") == "Định Hóa"
    assert canon("Nam Thuỵ Anh") == "Nam Thụy Anh"
    assert canon("Hoàn Kiếm") == "Hoàn Kiếm"          # non-final cluster untouched
    assert canon("Văn Miếu – Quốc Tử Giám") == canon("Văn Miếu - Quốc Tử Giám")


def test_name_in_text():
    txt = "Phường (2)\nAn Tường | 53,44\nXã gồm: Bạch Đích, Bạch Ngọc và Nam Thuỵ Anh."
    assert name_in_text("An Tường", txt)
    assert name_in_text("Bạch Đích", txt) and name_in_text("Bạch Ngọc", txt)
    assert name_in_text("Nam Thụy Anh", txt)
    assert not name_in_text("Tường", txt)              # no partial-word matches
    assert not name_in_text("Bạch", txt)


def test_name_in_text_list_separators():
    assert name_in_text("Ba Cung", "Xã (3)\nBa Bích · Ba Cung · Ba Dinh")
    assert name_in_text("Bưởi", "8 phường:\n- Bưởi\n- Nhật Tân")


from viadmin.wiki.report import listed_commune_names, mentions_reform  # noqa: E402


def test_mentions_reform_wide_vs_strict():
    wide_only = ["Buôn Đôn là một huyện miền núi biên giới cũ thuộc tỉnh Đắk Lắk, Việt Nam.",
                 "Bà Rịa trước đây là thành phố tỉnh lỵ thuộc tỉnh Bà Rịa – Vũng Tàu cũ.",
                 "Cô Tô là một đặc khu thuộc tỉnh Quảng Ninh, Việt Nam."]
    for t in wide_only:
        assert mentions_reform(t) and not mentions_reform(t, wide=False), t
    assert mentions_reform("Bình Dương là một tỉnh cũ thuộc vùng Đông Nam Bộ.", wide=False)
    stale = "Kỳ Anh là một huyện ven biển nằm ở phía đông nam tỉnh Hà Tĩnh, Việt Nam."
    assert not mentions_reform(stale)
    # history in an old-era lead is not a reform mention
    assert not mentions_reform("Thị xã được thành lập năm 2009 trên cơ sở huyện cũ.\nHuyện có 20 xã.")


def test_listed_commune_names():
    t = ("Huyện Triệu Phong có 17 đơn vị hành chính cấp xã trực thuộc, bao gồm thị trấn Ái Tử "
         "(huyện lỵ) và 16 xã: Triệu Ái, Triệu An, Triệu Đại (một phần) và Triệu Vân.\nKhác.")
    assert listed_commune_names(t) == ["Ái Tử", "Triệu Ái", "Triệu An", "Triệu Đại", "Triệu Vân"]
    assert listed_commune_names("Huyện có nhiều xã.") == []


def test_mentions_reform_wide_ignores_history():
    hist = ["Ô Môn là một huyện thuộc tỉnh Cần Thơ cũ, nay là quận của thành phố Cần Thơ.",
            "Mộc Hóa là tỉnh lỵ của tỉnh Kiến Tường cũ.",
            "Huế (trước đây là tỉnh Thừa Thiên Huế) là thành phố trực thuộc trung ương."]
    for t in hist:
        assert not mentions_reform(t), t
    assert mentions_reform("Đăk Hà cũ là một huyện thuộc tỉnh Kon Tum cũ, Việt Nam.")
