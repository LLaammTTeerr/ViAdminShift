# NSO official old→new commune conversion table (lineage A, PRIMARY)

- Publisher: Cục Thống kê (National Statistics Office, Bộ Tài chính), "Danh mục hành chính" site.
- Page: https://danhmuchanhchinh.nso.gov.vn/ (link "Bảng chuyển đổi ĐVHC mới - cũ" on the home page)
- File URL: https://danhmuchanhchinh.nso.gov.vn/TAPTIN/BangChuyendoi%C4%90VHCmoi_cu_final.xlsx
  (original file name `BangChuyendoiĐVHCmoi_cu_final.xlsx`, saved here without the `Đ`)
- HTTP Last-Modified: Thu, 23 Oct 2025 01:28:19 GMT; Content-Length 1146952
- SHA-256: 213966723785859dedd7c88965d6f12f8c3c508c91796e003804cf60a1054fc2
- License: official government statistical classification; no explicit license stated. Used for research.
- Contents: two sheets ("Tổng hợp_có merge", "Tổng hợp_không merge "), 10,571 data rows
  (new province, new commune name + 5-digit code, old commune name + code, note
  "Nhập toàn bộ"/"Nhập một phần"/"Giữ nguyên"/..., old district, old province).
- Parsed with the stdlib reader in `src/viadmin/data/xlsx.py` (values only; nothing executed).
- `headers.txt`: HTTP response headers of the download.

- **Not redistributed** in this repository (no explicit licence). `scripts/fetch_sources.sh` downloads the file
  from the URL above and checks the SHA-256.
