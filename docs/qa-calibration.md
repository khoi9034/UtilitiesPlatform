# QA Calibration

QA findings are candidates, not automatic truth. A rule can produce a confirmed defect, a likely defect, a false positive, an expected condition, or a source-data limitation.

Wastewater Phase 2 tracks calibration by rule code and version:

- total findings
- reviewed findings
- confirmed and likely defects
- false positives
- source limitations
- expected conditions
- confirmation rate
- false-positive rate
- review coverage
- current and proposed severity or threshold

Small samples do not automatically change rule thresholds. A rule can move through `not_reviewed`, `sampling`, `needs_adjustment`, `accepted`, `deprecated`, or `awaiting_data_owner_confirmation`.

Generated reports:

- `C:\UtilitiesPlatform_Data\05_qa\reports\wastewater_rule_calibration.json`
- `C:\UtilitiesPlatform_Data\05_qa\reports\wastewater_rule_calibration.csv`
- `C:\UtilitiesPlatform_Data\05_qa\reports\wastewater_rule_calibration.md`
