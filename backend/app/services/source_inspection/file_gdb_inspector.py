from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.services.source_inspection.base import InspectionContext
from app.services.source_inspection.models import SourceContainer, SourceLayer
from app.services.source_inspection.normalization import stable_id


class FileGdbInspector:
    def supports(self, source_format: str) -> bool:
        return source_format == "file_geodatabase"

    def capabilities(self) -> dict[str, object]:
        return {
            "source_format": "file_geodatabase",
            "arcpy_full_schema_supported": arcpy_available(),
            "fallback": "synthetic layer-name inventory only when ArcPy is unavailable",
        }

    def inspect(self, context: InspectionContext) -> tuple[SourceContainer, list[SourceLayer]]:
        gdb = find_gdb(context.inspection_dir)
        warnings: list[str] = []
        blockers: list[str] = []
        layers: list[SourceLayer] = []
        if not gdb:
            blockers.append("No file geodatabase folder was found in the inspection copy.")
        elif arcpy_available():
            layers, warnings = inspect_with_arcpy(gdb, context)
        else:
            layers = inspect_without_arcpy(gdb, context)
            warnings.append(
                "ArcPy is unavailable; run the local API from the ArcGIS Pro Python environment for full geodatabase schema metadata."
            )
            if not layers:
                blockers.append("ArcPy is required to enumerate real Esri file geodatabase feature classes.")
        spatial_refs = {layer.spatial_reference_name for layer in layers if layer.spatial_reference_name and layer.spatial_reference_name != "unknown"}
        container = SourceContainer(
            submission_id=str(context.submission["submission_id"]),
            container_id=f"container-{stable_id(context.submission['submission_id'], gdb.name if gdb else 'missing')}",
            container_name=gdb.name if gdb else str(context.submission.get("original_filename", "")),
            source_format="file_geodatabase",
            source_type=str(context.submission.get("source_type", "")),
            package_utility_system=str(context.submission.get("utility_system", "")),
            source_owner=str(context.submission.get("source_owner", "")),
            project_id=str(context.submission.get("project_id", "")),
            sensitivity_level=str(context.submission.get("sensitivity_level", "")),
            inspection_status="blocked" if blockers else "complete",
            spatial_reference_count=len(spatial_refs),
            child_layer_count=sum(1 for layer in layers if layer.object_type == "feature_class"),
            table_count=sum(1 for layer in layers if layer.object_type == "table"),
            relationship_count=sum(len(layer.relationship_profile) for layer in layers),
            domain_count=len({name for layer in layers for name in layer.domain_names}),
            subtype_count=sum(1 for layer in layers if layer.subtype_summary),
            attachment_count=sum(1 for layer in layers if layer.attachment_status == "enabled"),
            inspection_run_id=context.run_id,
            inspected_at=context.inspected_at,
            warnings=warnings,
            blockers=blockers,
        )
        for layer in layers:
            layer.container_id = container.container_id
        return container, layers


def arcpy_available() -> bool:
    try:
        import arcpy  # type: ignore  # noqa: F401

        return True
    except Exception:
        return False


def requires_arcpy(root: Path) -> bool:
    """Return true when a real FileGDB has no safe fallback layer manifests."""
    gdb = find_gdb(root)
    return bool(gdb) and not any(not is_esri_internal_file(path) for path in gdb.rglob("*") if path.is_file())


def find_gdb(root: Path) -> Path | None:
    matches = sorted(path for path in root.rglob("*.gdb") if path.is_dir())
    return matches[0] if matches else None


def inspect_without_arcpy(gdb: Path, context: InspectionContext) -> list[SourceLayer]:
    layers: list[SourceLayer] = []
    for path in sorted(item for item in gdb.rglob("*") if item.is_file()):
        if is_esri_internal_file(path):
            continue
        name = path.stem
        layer_id = f"layer-{stable_id(context.submission['submission_id'], name)}"
        layers.append(
            SourceLayer(
                layer_id=layer_id,
                submission_id=str(context.submission["submission_id"]),
                container_id="pending",
                source_layer_name=name,
                source_layer_alias=name,
                feature_dataset="" if path.parent == gdb else path.parent.name,
                object_type="table" if path.suffix.lower() in {".csv", ".table"} else "feature_class",
                geometry_type=fallback_geometry(name),
                record_count=None,
                spatial_reference_name="unknown",
                field_profile=fallback_fields(path),
                field_count=len(fallback_fields(path)),
                likely_id_fields=likely_fields(fallback_fields(path), {"id", "asset", "facility"}),
                likely_status_fields=likely_fields(fallback_fields(path), {"status", "state"}),
                likely_date_fields=likely_fields(fallback_fields(path), {"date", "year", "yr"}),
                likely_dimension_fields=likely_fields(fallback_fields(path), {"diam", "size", "sz", "length"}),
                likely_owner_fields=likely_fields(fallback_fields(path), {"owner", "jurisdiction", "src"}),
                created_at=context.inspected_at,
                updated_at=context.inspected_at,
            )
        )
    return layers


def inspect_with_arcpy(gdb: Path, context: InspectionContext) -> tuple[list[SourceLayer], list[str]]:
    import arcpy  # type: ignore

    layers: list[SourceLayer] = []
    warnings: list[str] = []
    domains = {domain.name: domain for domain in arcpy.da.ListDomains(str(gdb))}

    def add_dataset(dataset: str, feature_dataset: str = "", object_type: str = "feature_class") -> None:
        try:
            desc = arcpy.Describe(dataset)
            fields = field_profiles(arcpy, dataset)
            layer = SourceLayer(
                layer_id=f"layer-{stable_id(context.submission['submission_id'], getattr(desc, 'name', Path(dataset).name), feature_dataset)}",
                submission_id=str(context.submission["submission_id"]),
                container_id="pending",
                source_layer_name=str(getattr(desc, "name", Path(dataset).name)),
                source_layer_alias=str(getattr(desc, "aliasName", "") or getattr(desc, "name", Path(dataset).name)),
                feature_dataset=feature_dataset,
                object_type=object_type,
                geometry_type=str(getattr(desc, "shapeType", "table" if object_type == "table" else "unknown")).lower(),
                record_count=count_rows(arcpy, dataset),
                spatial_reference_name=spatial_reference_name(desc),
                spatial_reference_wkid=spatial_reference_wkid(desc),
                linear_unit=str(getattr(getattr(desc, "spatialReference", None), "linearUnitName", "") or ""),
                angular_unit=str(getattr(getattr(desc, "spatialReference", None), "angularUnitName", "") or ""),
                has_z=bool(getattr(desc, "hasZ", False)),
                has_m=bool(getattr(desc, "hasM", False)),
                extent_summary=extent_summary(desc),
                field_profile=fields,
                field_count=len(fields),
                domain_profile=safe_domain_profile(domains, fields),
                subtype_profile=safe_subtype_profile(arcpy, dataset),
                likely_id_fields=likely_fields(fields, {"id", "asset", "facility", "globalid"}),
                likely_status_fields=likely_fields(fields, {"status", "state"}),
                likely_date_fields=likely_fields(fields, {"date", "year", "yr"}),
                likely_dimension_fields=likely_fields(fields, {"diam", "size", "sz", "length"}),
                likely_owner_fields=likely_fields(fields, {"owner", "jurisdiction", "src"}),
                domain_names=sorted({str(field.get("domain")) for field in fields if field.get("domain")}),
                subtype_summary="present" if safe_subtype_profile(arcpy, dataset) else "",
                attachment_status="enabled" if bool(getattr(desc, "hasAttachments", False)) else "not_enabled",
                editor_tracking_status="enabled" if bool(getattr(desc, "editorTrackingEnabled", False)) else "not_enabled",
                created_at=context.inspected_at,
                updated_at=context.inspected_at,
            )
            apply_safe_aggregates(arcpy, dataset, layer)
            layers.append(layer)
        except Exception as exc:  # pragma: no cover - ArcPy error details vary by install.
            warnings.append(f"Skipped one geodatabase object due to ArcPy inspection error: {type(exc).__name__}.")

    arcpy.env.workspace = str(gdb)
    for feature_class in arcpy.ListFeatureClasses() or []:
        add_dataset(str(gdb / feature_class))
    for feature_dataset in arcpy.ListDatasets(feature_type="feature") or []:
        arcpy.env.workspace = str(gdb / feature_dataset)
        for feature_class in arcpy.ListFeatureClasses() or []:
            add_dataset(str(gdb / feature_dataset / feature_class), feature_dataset)
    arcpy.env.workspace = str(gdb)
    for table in arcpy.ListTables() or []:
        add_dataset(str(gdb / table), object_type="table")
    return layers, warnings


def field_profiles(arcpy: Any, dataset: str) -> list[dict[str, Any]]:
    return [
        {
            "name": field.name,
            "alias": field.aliasName,
            "type": field.type,
            "length": field.length,
            "nullable": field.isNullable,
            "required": field.required,
            "domain": field.domain,
        }
        for field in arcpy.ListFields(dataset)
    ]


def apply_safe_aggregates(arcpy: Any, dataset: str, layer: SourceLayer) -> None:
    fields = [field for field in layer.field_profile if field.get("type") not in {"Geometry", "OID", "Blob", "Raster"}][:50]
    if not fields or (layer.record_count or 0) > 250000:
        return
    names = [str(field["name"]) for field in fields]
    null_counts = {name: 0 for name in names}
    distinct: dict[str, set[str]] = {name: set() for name in names}
    try:
        with arcpy.da.SearchCursor(dataset, names) as cursor:
            for row in cursor:
                for name, value in zip(names, row):
                    if value is None or value == "":
                        null_counts[name] += 1
                    elif len(distinct[name]) <= 100:
                        distinct[name].add(value_pattern(value))
    except Exception:
        return
    total = layer.record_count or 0
    for field in layer.field_profile:
        name = str(field.get("name", ""))
        if name in null_counts:
            field["null_count"] = null_counts[name]
            field["null_percentage"] = round(null_counts[name] / total, 4) if total else None
            field["distinct_pattern_count"] = len(distinct[name])
            field["value_format_patterns"] = sorted(distinct[name])[:10]


def count_rows(arcpy: Any, dataset: str) -> int:
    try:
        return int(arcpy.management.GetCount(dataset)[0])
    except Exception:
        return 0


def spatial_reference_name(desc: Any) -> str:
    sr = getattr(desc, "spatialReference", None)
    return str(getattr(sr, "name", "") or "unknown")


def spatial_reference_wkid(desc: Any) -> int | None:
    sr = getattr(desc, "spatialReference", None)
    code = getattr(sr, "factoryCode", None)
    return int(code) if code not in {None, 0, ""} else None


def extent_summary(desc: Any) -> dict[str, float] | dict[str, str]:
    extent = getattr(desc, "extent", None)
    if not extent:
        return {}
    return {
        "xmin": round(float(extent.XMin), 3),
        "ymin": round(float(extent.YMin), 3),
        "xmax": round(float(extent.XMax), 3),
        "ymax": round(float(extent.YMax), 3),
    }


def safe_domain_profile(domains: dict[str, Any], fields: list[dict[str, Any]]) -> dict[str, Any]:
    profile: dict[str, Any] = {}
    for field in fields:
        domain_name = str(field.get("domain") or "")
        domain = domains.get(domain_name)
        if domain:
            profile[domain_name] = {
                "type": getattr(domain, "domainType", ""),
                "field_type": getattr(domain, "type", ""),
                "coded_value_count": len(getattr(domain, "codedValues", {}) or {}),
                "range_present": bool(getattr(domain, "range", None)),
            }
    return profile


def safe_subtype_profile(arcpy: Any, dataset: str) -> dict[str, Any]:
    try:
        subtypes = arcpy.da.ListSubtypes(dataset)
    except Exception:
        return {}
    return {"subtype_count": len(subtypes), "default_subtype": next((str(item.get("Name", "")) for item in subtypes.values() if item.get("Default")), "")}


def fallback_fields(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() != ".csv":
        return []
    try:
        header = path.read_text(encoding="utf-8", errors="ignore").splitlines()[0].split(",")
    except IndexError:
        return []
    return [{"name": item.strip()[:64], "alias": item.strip()[:64], "type": "String", "nullable": True, "required": False, "domain": ""} for item in header if item.strip()]


def likely_fields(fields: list[dict[str, Any]], tokens: set[str]) -> list[str]:
    output = []
    for field in fields:
        name = str(field.get("name", "")).lower()
        alias = str(field.get("alias", "")).lower()
        if any(token in name or token in alias for token in tokens):
            output.append(str(field.get("name", "")))
    return output[:12]


def value_pattern(value: Any) -> str:
    text = str(value)
    text = re.sub(r"[A-Za-z]", "A", text)
    text = re.sub(r"\d", "9", text)
    return text[:32]


def fallback_geometry(name: str) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ["poly", "area", "watershed", "district"]):
        return "polygon"
    if any(token in lowered for token in ["line", "main", "pipe", "sewer"]):
        return "polyline"
    if any(token in lowered for token in ["point", "well", "tank", "manhole", "mh", "church"]):
        return "point"
    return "unknown"


def is_esri_internal_file(path: Path) -> bool:
    name = path.name.lower()
    return bool(re.match(r"a\d+", name)) or name in {"gdb", "timestamps", "freelist"} or path.suffix.lower() in {".gdbtable", ".gdbtablx", ".atx", ".spx", ".lock"}
