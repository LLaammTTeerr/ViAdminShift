# vietaddr WordPress plugin data — lineage A, DERIVATIVE (provinces.open-api.vn ← NSO)

- URL: https://plugins.svn.wordpress.org/vietaddr/trunk/data/ (SVN revision 3743090)
- Files: legacy-map.json, vn-units.json; upstream data/SOURCE.md saved as UPSTREAM_SOURCE.md; readme.txt; LICENSE
- Not redistributed: legacy-map.json and vn-units.json are generated from the NSO conversion table (through
  provinces.open-api.vn), so this repository ships only SOURCE.md, UPSTREAM_SOURCE.md, readme.txt and LICENSE.
  `scripts/fetch_sources.sh` downloads both files from SVN revision 3743090 and checks them
  (SHA-256 vn-units.json: 9b8f8753f7d37c271e307a1d16167235f9cb25a0e8d11a19c9496fbc458d10a3).
- License: GPL-3.0-or-later
- SHA-256 legacy-map.json: 2c3d729efabbcadcc8afaf3a5666f682234afe2d6aaf5692b8c86f47d429277e
- Provenance (per UPSTREAM_SOURCE.md): old→new ward map built from provinces.open-api.vn API v2
  `/api/v2/w/<code>/to-legacies/` (data_version 2026-09-20), which itself is generated from the NSO conversion
  table. Contains 9,583 1:1 old→new entries + 440 "split" old wards. Not an independent vote.
  Caveat: open-api data_version 2026-09-20 may reflect post-1/7/2025 adjustments.
