# vietnamadminunits (tranngocminhhieu) — lineage B

- Repo: https://github.com/tranngocminhhieu/vietnamadminunits (commit in `COMMIT`: 7fac8c45805aad9916b17237c54baf4502303b93)
- License: MIT (Copyright (c) 2025 Tran Ngoc Minh Hieu)
- Retrieved from raw.githubusercontent.com at the pinned commit; data files only, no code run
- Not redistributed: every file below is an official list, a scrape of a government portal or a table built from
  them. `scripts/fetch_sources.sh` downloads them from the pinned commit and checks the SHA-256 values below (and
  legacy_63-province-10040-ward_with_location.csv 60d648b0856cb7dde7dafc0ce98c5db033dd3b842cde5ba2b30aeca061008880,
  sapnhap.bando.com.vn_province_2025-07-17.csv 92326777b0a8bf8f53c51384cf4287bc8b863f648e37a722e8127353212a2b55,
  converter_2025.json 84f0848bf401b047775cbb49768c181a9271f77e4a4ec706d293b09bcb4faddd)
- Files (paths mirror the repo):
  - `data/processed/convert_legacy_2025_with_location_and_default_ward.csv` — 10,602 old→new ward rows
    (built by the author from sapnhap.bando.com.vn composition texts + GSO lists, with GIS heuristics for
    divided wards; flags isMergedWard/isDividedWard/isDefaultNewWard)
  - `data/processed/2025_34-province-3221-ward_with_location.csv` — 3,321 new wards (despite file name)
  - `data/processed/legacy_63-province-10040-ward_with_location.csv` — 10,040 old wards
  - `data/raw/danhmuchanhchinh.gso.gov.vn_{district,ward}_2025-07-18.csv` — GSO pre-reform lists
    (696 districts, 10,035 communes) scraped 2025-07-18 by the author
  - `data/raw/sapnhap.bando.com.vn_{province,ward}_2025-07-17.csv` — scrape of the Ministry's merger site
    (sapnhap.bando.com.vn) incl. free-text "truocsapnhap" composition descriptions
  - `data/raw/production.cas.so_3221_wards_2025-08-05.json` — 3,321 new communes with resolution ("decree") numbers
  - `vietnamadminunits/data/converter_2025.json` — the package's converter tables
- SHA-256:
  - convert_legacy_2025_with_location_and_default_ward.csv e06d189c9caad0be458e25f541587dcf4db1758326ea5b5ffcbc9448a769c883
  - 2025_34-province-3221-ward_with_location.csv cf103923c0c469201f3b22d78f5b05c90db13986994811a9fc17988de18bf678
  - danhmuchanhchinh.gso.gov.vn_ward_2025-07-18.csv bad8474f99dd8476f07a11117154f1e587741a210f20e33c4b50d9d3fe6954a9
  - danhmuchanhchinh.gso.gov.vn_district_2025-07-18.csv f924f4a38b3cce04ad00670fa3ec3478cbf73a1d157690693c16109a9b3bf4ef
  - production.cas.so_3221_wards_2025-08-05.json 259057818b23ee8d70f706fd8ee68743c1779e4df2d2857270e4b4f8c3d4660f
  - sapnhap.bando.com.vn_ward_2025-07-17.csv 2810278e621aa2dbb08706f2f9ca47f773a1e8779bc41be321a08155db70dc39
