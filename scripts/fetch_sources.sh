#!/bin/bash
# Download the source files that the repository does not redistribute, and verify them.
#   - the NSO old-to-new conversion table (official; redistribution terms not stated), the build's backbone
#   - the VietnamProvinces copy of that table (consistency check only; not read by the build)
#   - every other source file that contains NSO data or data from a government portal: the vietnamadminunits data
#     files (GSO commune and district lists, the scrape of the Ministry's sapnhap.bando.com.vn, the cas.so commune
#     list and the tables built from them), its copy in undertheseanlp/address, and vietaddr's ward map and unit list
#     (built from provinces.open-api.vn, itself generated from the NSO table)
#   - the 34 hoatieu.vn HTML reproductions of the ward-level resolutions NQ 1654-1687/NQ-UBTVQH15. The pages change
#     byte-wise between downloads (ads, timestamps), so they are checked on the text the build parses (Điều 1 of each)
# Then rebuild the canonical tables (data/processed/) from them:
#   bash scripts/fetch_sources.sh && uv run python -m viadmin.data.build
# The checksums are those of the files used for the paper. If the publisher replaces a file,
# the check fails; the build then still runs on the new file, but results may differ from the paper.
set -u
cd "$(dirname "$0")/.."
fail=0
get() {  # url dest sha256
  mkdir -p "$(dirname "$2")"
  if [ ! -f "$2" ]; then
    curl -sSfL -m 300 -o "$2" "$1" || { echo "download failed: $1"; fail=1; return; }
  fi
  if echo "$3  $2" | sha256sum -c --quiet - 2>/dev/null; then echo "ok        $2"
  else echo "MISMATCH  $2 (the source changed since the version used for the paper)"; fail=1; fi
}
get "https://danhmuchanhchinh.nso.gov.vn/TAPTIN/BangChuyendoi%C4%90VHCmoi_cu_final.xlsx" \
    data/raw/nso_conversion/BangChuyendoiDVHCmoi_cu_final.xlsx \
    213966723785859dedd7c88965d6f12f8c3c508c91796e003804cf60a1054fc2
VP=https://raw.githubusercontent.com/sunshine-tech/VietnamProvinces/4cc4038d0e89bd8affbda864119c1ab1e0360523
get "$VP/dev/seed-data/2025-07/BangChuyendoi%C4%90VHCmoi_cu_khong_merge.csv" \
    data/raw/vietnam_provinces_nso/BangChuyendoiDVHCmoi_cu_khong_merge.csv \
    21da94f59a498d03deda1f0882e71f65cd3b7c855bbd6c760ba72f6b6a94ee46
get "$VP/dev/seed-data/Pre-2025-07/Xa_2025-01-04.csv" data/raw/vietnam_provinces_nso/Xa_2025-01-04.csv \
    026361a37fd47ad469ec6d5cc6dbcf2f0ae8a5d4219d10482fbbc8689864a2a4
get "$VP/vietnam_provinces/data/nested-divisions.json" data/raw/vietnam_provinces_nso/nested-divisions.json \
    e997eb9dcbbbafbbae00496965572f8ccd6e192cbb1024e8fe6b5513c162dc9b
VNAU=https://raw.githubusercontent.com/tranngocminhhieu/vietnamadminunits/7fac8c45805aad9916b17237c54baf4502303b93
while read -r sha f; do get "$VNAU/$f" "data/raw/vietnamadminunits/$f" "$sha"; done <<'LIST'
bad8474f99dd8476f07a11117154f1e587741a210f20e33c4b50d9d3fe6954a9 data/raw/danhmuchanhchinh.gso.gov.vn_ward_2025-07-18.csv
f924f4a38b3cce04ad00670fa3ec3478cbf73a1d157690693c16109a9b3bf4ef data/raw/danhmuchanhchinh.gso.gov.vn_district_2025-07-18.csv
259057818b23ee8d70f706fd8ee68743c1779e4df2d2857270e4b4f8c3d4660f data/raw/production.cas.so_3221_wards_2025-08-05.json
92326777b0a8bf8f53c51384cf4287bc8b863f648e37a722e8127353212a2b55 data/raw/sapnhap.bando.com.vn_province_2025-07-17.csv
2810278e621aa2dbb08706f2f9ca47f773a1e8779bc41be321a08155db70dc39 data/raw/sapnhap.bando.com.vn_ward_2025-07-17.csv
cf103923c0c469201f3b22d78f5b05c90db13986994811a9fc17988de18bf678 data/processed/2025_34-province-3221-ward_with_location.csv
e06d189c9caad0be458e25f541587dcf4db1758326ea5b5ffcbc9448a769c883 data/processed/convert_legacy_2025_with_location_and_default_ward.csv
60d648b0856cb7dde7dafc0ce98c5db033dd3b842cde5ba2b30aeca061008880 data/processed/legacy_63-province-10040-ward_with_location.csv
84f0848bf401b047775cbb49768c181a9271f77e4a4ec706d293b09bcb4faddd vietnamadminunits/data/converter_2025.json
LIST
get https://huggingface.co/undertheseanlp/address/resolve/e6b7d02493457f8310bbd98038ff8d10b470484c/data/mapping.json \
    data/raw/undertheseanlp_address/mapping.json 172d282a8043202a05eb3b452af51aafe3ead9debbff40854c5467c0c8c1b8e7
VA='https://plugins.svn.wordpress.org/!svn/bc/3743090/vietaddr/trunk/data'  # SVN revision 3743090
get "$VA/legacy-map.json" data/raw/vietaddr/legacy-map.json \
    2c3d729efabbcadcc8afaf3a5666f682234afe2d6aaf5692b8c86f47d429277e
get "$VA/vn-units.json" data/raw/vietaddr/vn-units.json \
    9b8f8753f7d37c271e307a1d16167235f9cb25a0e8d11a19c9496fbc458d10a3
RES=data/raw/ubtvqh_resolutions_hoatieu
mkdir -p "$RES/html"
grep -o '^  - 1[0-9]*: https[^ ]*' "$RES/SOURCE.md" | while read -r _ n url; do
  n=${n%:}
  [ -f "$RES/html/$n.html" ] && continue
  curl -sSfL -m 60 -A "Mozilla/5.0" -o "$RES/html/$n.html" "$url" || echo "download failed: $url"
  sleep 1
done
if uv run python - <<'PY'
import hashlib, json
from viadmin.data.resolutions import article1_clauses
t = {n: article1_clauses(str(n)) for n in range(1654, 1688)}
h = hashlib.sha256(json.dumps(t, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
raise SystemExit(h != "229578da189cacd899ce2dcd8fbe1937f2a6d9512d694486e96c83614673f4af")
PY
then echo "ok        $RES/html (Điều 1 text of all 34 resolutions)"
else echo "MISMATCH  $RES/html (the parsed resolution text changed since the version used for the paper)"; fail=1; fi
exit $fail
