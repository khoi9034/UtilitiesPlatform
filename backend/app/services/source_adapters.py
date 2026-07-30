from __future__ import annotations

import re
from typing import Any

from app.services.utility_assets.domain import SOURCE_ROLES, TELECOM_CLASSES

SMART_DS_SOURCE_TYPE = "nrel_smart_ds"
TELECOM_CONTEXT_SOURCE_TYPES = (
    "fcc_broadband_availability",
    "state_broadband_eligibility",
    "grant_project_area",
    "provider_coverage_reference",
)
SMART_DS_ASSET_MAPPINGS = {
    "medium_voltage_line": ("overhead_conductor", "underground_conductor"),
    "low_voltage_line": ("secondary_conductor",),
    "load": ("service_point",),
    "transformer": ("transformer",),
    "capacitor": ("electric_structure",),
    "regulator": ("electric_structure",),
    "fuse": ("fuse",),
    "recloser": ("recloser",),
    "switch": ("switch",),
    "substation": ("substation",),
    "source": ("substation",),
}
SMART_DS_FIELD_MAPPINGS = {
    "phase": "phase",
    "feeder": "feeder_id",
    "nominal_voltage": "nominal_voltage",
}
PHYSICAL_TELECOM_CLASSES = set(TELECOM_CLASSES) - {"service_area", "reference_boundary"}
_ALLOWED_MANIFEST_FIELDS = {
    "source_type", "source_role", "domain", "datasets", "field_mappings",
    "relationship_mappings", "metadata",
}
_FORBIDDEN_FIELDS = {
    "path", "filesystem_path", "source_path", "local_path", "url", "external_url",
    "sql", "query", "python", "shell", "command", "script", "executable",
    "expression", "rule_file", "credentials", "connection_string", "password",
    "token", "secret",
}
_PATH_OR_URL = re.compile(
    r"(?:[a-z]:[\\/]|\\\\|[a-z][a-z0-9+.-]*://|(?:^|[\\/])\.\.?(?:[\\/]|$)|^[~\\/])",
    re.IGNORECASE,
)


def adapter_catalog() -> dict[str, Any]:
    return {
        "items": [
            {
                "source_type": "local_registered_package",
                "domain": "multi_utility",
                "mode": "inspection_metadata_only",
                "creates_assets": False,
            },
            {
                "source_type": SMART_DS_SOURCE_TYPE,
                "domain": "electric_distribution",
                "mode": "dry_run_contract",
                "creates_assets": False,
                "asset_mapping_candidates": {
                    key: list(value) for key, value in SMART_DS_ASSET_MAPPINGS.items()
                },
            },
            *[
                {
                    "source_type": source_type,
                    "domain": "telecom_fiber",
                    "mode": "context_only",
                    "creates_assets": False,
                    "allowed_source_roles": [
                        "planning_context", "service_availability",
                        "funding_area", "reference_boundary",
                    ],
                    "physical_inventory_generation": False,
                }
                for source_type in TELECOM_CONTEXT_SOURCE_TYPES
            ],
        ],
        "source_roles": list(SOURCE_ROLES),
        "message": "Adapters inspect allowlisted manifest metadata only; they do not download, ingest, or publish data.",
    }


def inspect_manifest(source_type: str, manifest: dict[str, Any]) -> dict[str, Any]:
    if source_type not in {SMART_DS_SOURCE_TYPE, *TELECOM_CONTEXT_SOURCE_TYPES}:
        raise ValueError("Unsupported source adapter.")
    if not isinstance(manifest, dict):
        raise ValueError("Import manifest must be a JSON object.")
    _reject_unsafe(manifest)
    unknown = set(manifest) - _ALLOWED_MANIFEST_FIELDS
    if unknown:
        raise ValueError(f"Unsupported import-manifest field: {sorted(unknown)[0]}.")
    if manifest.get("source_type") != source_type:
        raise ValueError("Manifest source_type does not match the selected adapter.")
    role = str(manifest.get("source_role", "unknown"))
    if role not in SOURCE_ROLES:
        raise ValueError("Manifest source_role is not allowlisted.")
    datasets = manifest.get("datasets", [])
    if not isinstance(datasets, list):
        raise ValueError("Manifest datasets must be a list.")

    if source_type == SMART_DS_SOURCE_TYPE:
        if manifest.get("domain") != "electric_distribution":
            raise ValueError("SMART-DS manifests must target electric_distribution.")
        mapped = [
            {
                "source_asset_type": str(item.get("source_asset_type", "")),
                "canonical_asset_candidates": list(
                    SMART_DS_ASSET_MAPPINGS.get(str(item.get("source_asset_type", "")), ())
                ),
                "status": "candidate" if str(item.get("source_asset_type", "")) in SMART_DS_ASSET_MAPPINGS else "unmapped",
            }
            for item in datasets if isinstance(item, dict)
        ]
    else:
        if manifest.get("domain") != "telecom_fiber":
            raise ValueError("Telecom context manifests must target telecom_fiber.")
        if role not in {"planning_context", "service_availability", "funding_area", "reference_boundary"}:
            raise ValueError("Public telecom context sources cannot be operational inventory.")
        requested = {
            str(item.get("canonical_asset_class", ""))
            for item in datasets if isinstance(item, dict)
        }
        if requested & PHYSICAL_TELECOM_CLASSES:
            raise ValueError("Contextual telecom sources cannot generate physical OSP inventory.")
        mapped = [
            {
                "source_asset_type": str(item.get("source_asset_type", "context_area")),
                "canonical_asset_candidates": ["service_area", "reference_boundary"],
                "status": "context_only",
            }
            for item in datasets if isinstance(item, dict)
        ]

    return {
        "source_type": source_type,
        "source_role": role,
        "domain": manifest.get("domain"),
        "status": "dry_run_complete",
        "dataset_count": len(datasets),
        "asset_mappings": mapped,
        "field_mapping_contract": SMART_DS_FIELD_MAPPINGS if source_type == SMART_DS_SOURCE_TYPE else {},
        "relationship_mapping_contract": ["connects_to", "feeds", "belongs_to_feeder"]
        if source_type == SMART_DS_SOURCE_TYPE else ["reference_for"],
        "approved_for_import": False,
        "records_read": 0,
        "records_written": 0,
        "message": "Manifest validated without reading source records or creating canonical assets.",
    }


def _reject_unsafe(value: Any) -> None:
    if isinstance(value, dict):
        if _FORBIDDEN_FIELDS & {str(key).casefold() for key in value}:
            raise ValueError("Filesystem, executable, credential, and external URL inputs are not accepted.")
        for item in value.values():
            _reject_unsafe(item)
    elif isinstance(value, list):
        for item in value:
            _reject_unsafe(item)
    elif isinstance(value, str) and _PATH_OR_URL.search(value):
        raise ValueError("Filesystem, executable, credential, and external URL inputs are not accepted.")
