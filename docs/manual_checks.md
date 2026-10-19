# Manual checks by the authors

**Status: done by the authors, all 53 checks correct (sections A–C).**

The paper states that the authors checked these by hand (benchmark section, Quality control (ii),
and the Ethics and Data Statement). Every box below has been checked by the authors.

**Source:** the 34 ward-level resolutions of the National Assembly Standing Committee, NQ 1654–1687/NQ-UBTVQH15 of
16/6/2025 (Điều 1, the khoản given in each row). Official texts: vanban.chinhphu.vn; readable copies: luatvietnam.vn,
thuvienphapluat.vn. For each row, check (a) that the old ward goes to the new ward shown, and (b) that the full list of
old wards forming that new ward matches `data/processed/ward_mapping.jsonl`.

**Namesakes.** Many names repeat across the country, and a web search for a name often returns a different unit.
Identify each unit by its old district and province (and its code in `ward_mapping.jsonl`), and only by the khoản
cited. Example: the new xã Hùng Sơn of Đà Nẵng (NQ 1659 k.83, formed from Ch'ơm, Gari, Tr'hy and Axan of huyện
Tây Giang, Quảng Nam) is unrelated to the old xã Hùng Sơn of huyện Anh Sơn, Nghệ An (code 17347), which NQ 1678 k.3
merges into xã Nhân Hòa (row 17). Four other old units are also named Hùng Sơn (xã in Kim Bôi and Tràng Định, and two
thị trấn in Lâm Thao and Đại Từ).

## A. 30 random rows (seed 13, one per new province)

Drawn over the mapping before the Hòa Thắng → Hồng Thái pair was added (10,565 rows; see `docs/data_report.md` §7).

| # | resolution (khoản) | old ward (district, old province) | → new ward (new province) | type | ✔ / ✘ and note |
|---|---|---|---|---|---|
| 1 | 1664 (k.122) | Phường Yên Đỗ (TP Pleiku, Gia Lai) | Phường Diên Hồng (Gia Lai) | merged | ✔ |
| 2 | 1686 (k.90) | Xã Lương Ngoại (Bá Thước, Thanh Hóa) | Xã Quý Lương (Thanh Hóa) | merged | ✔ |
| 3 | 1671 (k.105) | Xã ĐamBri (TP Bảo Lộc, Lâm Đồng) | Phường 2 Bảo Lộc (Lâm Đồng) | merged | ✔ |
| 4 | 1662 (k.12) | Xã Bàu Hàm (Trảng Bom, Đồng Nai) | Xã Bàu Hàm (Đồng Nai) | merged | ✔ |
| 5 | 1677 (k.43) | Xã Ba Tô (Ba Tơ, Quảng Ngãi) | Xã Ba Tô (Quảng Ngãi) | merged | ✔ |
| 6 | 1674 (k.101, k.109) | Phường Hoàng Đông (TX Duy Tiên, Hà Nam) | Phường Hà Nam (Ninh Bình) | divided | ✔ |
| 7 | 1655 (k.57) | Xã Hiệp Thành (TP Bạc Liêu) | Phường Hiệp Thành (Cà Mau) | merged | ✔ |
| 8 | 1669 (k.86) | Xã Tân Việt (Bình Giang, Hải Dương) | Xã Bình Giang (Hải Phòng) | merged | ✔ |
| 9 | 1668 (k.15) | Phường Thuận An (Q. Thốt Nốt, Cần Thơ) | Phường Thốt Nốt (Cần Thơ) | merged | ✔ |
| 10 | 1656 (k.112) | Xã Yên Viên (Gia Lâm, Hà Nội) | Xã Phù Đổng (Hà Nội) | merged | ✔ |
| 11 | 1687 (k.104) | Phường 4 (TP Vĩnh Long) | Phường Phước Hậu (Vĩnh Long) | merged | ✔ |
| 12 | 1660 (k.41) | Xã Cư KTy (Krông Bông, Đắk Lắk) | Xã Dang Kang (Đắk Lắk) | merged | ✔ |
| 13 | 1676 (k.43) | Xã Văn Miếu (Thanh Sơn, Phú Thọ) | Xã Văn Miếu (Phú Thọ) | merged | ✔ |
| 14 | 1666 (k.98) | Xã Ngọc Lâm (TX Mỹ Hào, Hưng Yên) | Phường Đường Hào (Hưng Yên) | merged | ✔ |
| 15 | 1680 (k.72) | Xã Quảng Hải (TX Ba Đồn, Quảng Bình) | Phường Ba Đồn (Quảng Trị) | merged | ✔ |
| 16 | 1679 (k.12) | Xã Tân Bình (Đầm Hà, Quảng Ninh) | Xã Đầm Hà (Quảng Ninh) | merged | ✔ |
| 17 | 1678 (k.3) | Xã Tam Đỉnh (huyện Anh Sơn, Nghệ An) | Xã Nhân Hòa (Nghệ An) | merged | ✔ |
| 18 | 1659 (k.17) | Phường Điện Phương (TX Điện Bàn, Quảng Nam) | Phường Điện Bàn (Đà Nẵng) | merged | ✔ |
| 19 | 1663 (k.79) | Xã Tân Tây (Gò Công Đông, Tiền Giang) | Xã Tân Đông (Đồng Tháp) | merged | ✔ |
| 20 | 1670 (k.1) | Xã Pha Mu (Than Uyên, Lai Châu) | Xã Mường Kim (Lai Châu) | merged | ✔ |
| 21 | 1665 (k.37) | Xã Tân Dân (Đức Thọ, Hà Tĩnh) | Xã Đức Thọ (Hà Tĩnh) | merged | ✔ |
| 22 | 1681 (k.39) | Xã Tú Nang (Yên Châu, Sơn La) | Xã Chiềng Hặc (Sơn La) | merged | ✔ |
| 23 | 1683 (k.77) | Xã Huống Thượng (TP Thái Nguyên) | Phường Linh Sơn (Thái Nguyên) | merged | ✔ |
| 24 | 1667 (k.52) | Phường Phước Long (TP Nha Trang) | Phường Nam Nha Trang (Khánh Hòa) | merged | ✔ |
| 25 | 1685 (k.3) | Phường Bến Thành (Quận 1, HCM) | Phường Bến Thành (HCM) | merged | ✔ |
| 26 | 1658 (k.79) | Phường Hà Mãn (TX Thuận Thành, Bắc Ninh) | Phường Song Liễu (Bắc Ninh) | merged | ✔ |
| 27 | 1657 (k.49) | Xã Phong Nặm (Trùng Khánh, Cao Bằng) | Xã Đình Phong (Cao Bằng) | merged | ✔ |
| 28 | 1682 (k.49) | Xã Tân Tập (Cần Giuộc, Long An) | Xã Tân Tập (Tây Ninh) | merged | ✔ |
| 29 | 1673 (k.55) | Xã Khánh Yên Thượng (Văn Bàn, Lào Cai) | Xã Văn Bàn (Lào Cai) | merged | ✔ |
| 30 | 1654 (k.75) | Xã Mỹ Hiệp Sơn (Hòn Đất, Kiên Giang) | Xã Mỹ Thuận (An Giang) | merged | ✔ |

## B. 11 targeted rows (divided, conflicting and corrected units)

See `docs/data_report.md` §6.1 for what each one is about. Tick when the mapping matches the resolution.

- ✔ Văn Khê
- ✔ Kỳ Lợi
- ✔ Đặng Xá / Cổ Bi
- ✔ Mỹ Hưng / Hồng Quang
- ✔ Phú Thịnh / Công Đa
- ✔ the 5 Đồng Tháp same-name collisions
- ✔ the Cần Thơ same-name collisions
- ✔ Xá Nhè (stale registry name)
- ✔ Tiên Sơn (stale registry type)
- ✔ Hòa Tân Đông
- ✔ Hòa Thắng → Hồng Thái / Hòa Thắng (NQ 1671 k.46, k.51)

## C. The 12 T0 headline items (`data/benchmark/items.jsonl`)

Check each gold answer against Nghị quyết 202/2025/QH15 (12/6/2025) and the official totals (34 provinces, 3,321 communes).

1. ✔ Chính quyền địa phương ở Việt Nam hiện nay gồm những cấp nào?  
   gold: **A**; old: C
2. ✔ Cả nước hiện có tổng cộng bao nhiêu tỉnh và thành phố trực thuộc trung ương?  
   gold: **34**; old: 63
3. ✔ Đơn vị hành chính cấp xã ở Việt Nam hiện nay gồm những loại nào?  
   gold: **C**; old: A
4. ✔ Việt Nam hiện có bao nhiêu đơn vị hành chính cấp tỉnh (tỉnh và thành phố trực thuộc trung ương)?  
   gold: **34**; old: 63
5. ✔ Ở Việt Nam hiện nay, cấp huyện (quận, huyện, thị xã, thành phố thuộc tỉnh) có còn là một cấp đơn vị hành chính không?  
   gold: **B**; old: D
6. ✔ Chính quyền địa phương ở Việt Nam hiện được tổ chức theo mô hình mấy cấp?  
   gold: **2**; old: 3
7. ✔ Ở Việt Nam hiện nay, thị trấn có còn là một loại đơn vị hành chính không?  
   gold: **D**; old: B
8. ✔ Hiện nay Việt Nam có bao nhiêu đơn vị hành chính cấp huyện?  
   gold: **B**; old: A
9. ✔ Hiện nay cả nước có bao nhiêu đơn vị hành chính cấp xã?  
   gold: **C**; old: D
10. ✔ Việt Nam hiện có bao nhiêu đặc khu (đơn vị hành chính cấp xã ở hải đảo)?  
   gold: **13**; old: 0
11. ✔ Hiện nay cả nước Việt Nam có bao nhiêu tỉnh, thành phố trực thuộc trung ương?  
   gold: **D**; old: C
12. ✔ Việt Nam hiện có bao nhiêu đơn vị hành chính cấp xã (gồm xã, phường và đặc khu)?  
   gold: **3321**; old: ['10035', '10.035', '10,035']

If an error is found later, fix the canonical table; the gold answers, the affected items and the results tables
are regenerated from `data/processed`.
