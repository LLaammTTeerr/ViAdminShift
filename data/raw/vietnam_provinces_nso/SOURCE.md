# VietnamProvinces (sunshine-tech / Nguyễn Hồng Quân) — copy of NSO tables (lineage A, derivative)

- Repo: https://github.com/sunshine-tech/VietnamProvinces (commit in `COMMIT`: 4cc4038d0e89bd8affbda864119c1ab1e0360523)
- Files (raw.githubusercontent.com at that commit):
  - `dev/seed-data/2025-07/BangChuyendoiĐVHCmoi_cu_khong_merge.csv` → `BangChuyendoiDVHCmoi_cu_khong_merge.csv`
    (CSV export of the NSO conversion table sheet "không merge"; identical to `../nso_conversion` except that
    some codes lost their leading zeros in the NSO xlsx)
  - `dev/seed-data/Pre-2025-07/Xa_2025-01-04.csv` (GSO commune list as of 2025-01-04, pre-reform)
  - `vietnam_provinces/data/nested-divisions.json` (post-reform 34 provinces / wards, data_version 2026-09-20;
    NOTE: may include post-1/7/2025 adjustments, see upstream CHANGELOG "Upgrade Quảng Ninh and Bắc Ninh")
- License: GPL-3.0-or-later (per upstream pyproject.toml); data originates from NSO (danhmuchanhchinh.nso.gov.vn).
- Used only as a consistency check of the NSO file; not counted as an independent source.

- **Not redistributed** in this repository (a copy of the NSO table). `scripts/fetch_sources.sh` downloads the
  three files at the commit above and checks their SHA-256.
