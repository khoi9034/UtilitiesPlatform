from __future__ import annotations

from dataclasses import dataclass, field

RULE_VERSION = "source_review_automation_v1"
POLICY_MODES = {"conservative"}


@dataclass
class StageResult:
    stage_name: str
    records_read: int = 0
    records_updated: int = 0
    warnings: list[str] = field(default_factory=list)
