# Changelog

Data versions are named after the date of the administrative structure they describe. Released versions stay
available unchanged. Report errors on the repository's issue tracker; confirmed corrections are listed here.

## Version 2025-07-01 (releases v1.0, v1.0.1, v1.0.2, v1.0.3)

v1.0.3 has the same data. `results/analysis/nosuffix.json` (brevity-suffix control) is rescored with the current
scorer, as printed in the paper (six rates change by 1.25 points), and `scripts/score_nosuffix.py` is added to the
README's rebuild steps.

v1.0.2 has the same data and code as v1.0.1. The datasheet answers the export-controls question (none known), the
upstream source note no longer gives download dates, and `.zenodo.json` files the archive as a dataset.

v1.0.1 has the same data and code as v1.0, with the datasheet's creators, funding, ethical review, distribution and
maintenance sections and the archive DOI in the README, `CITATION.cff` and datasheet.

First release: the structure in force on 1 July 2025 ("old" = the structure on 30 June 2025).

- Canonical tables (rebuilt from the downloaded sources by `scripts/fetch_sources.sh` and
  `uv run python -m viadmin.data.build`), 7,995 benchmark items, 2,281 retrieval passages, model outputs, analysis
  outputs and annotations.
- Corrections made while building the tables (three wrong codes in the NSO table, one pair missing from it and added
  from NQ 1671 k.46, 32 rejected pairs of the second lineage) are listed in `data/processed/crosscheck_issues.jsonl`
  and `docs/data_report.md`.

### Known later changes (not reflected in this version)

- Between 30 April and 20 September 2026, Đồng Nai, Quảng Ninh and Bắc Ninh became centrally-run cities with the same
  name and territory (Resolutions 30, 36 and 39/2026/QH16), and 10 xã of Đồng Nai and 12 of Bắc Ninh became phường
  under the same names (Resolutions 237 and 388/NQ-UBTVQH16). Only four T3 items are affected (`T3-prov-22`,
  `T3-prov-27`, `T3-prov-75`, `T3-dist-256`): they are correct only at the version date. See the README, "Changes
  after 1 July 2025".
