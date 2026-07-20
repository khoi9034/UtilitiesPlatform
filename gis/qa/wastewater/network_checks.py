from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from .attribute_checks import safe_asset_id
from .geometry_checks import first_path
from .issue_writer import make_issue


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, item: str) -> None:
        self.parent.setdefault(item, item)

    def find(self, item: str) -> str:
        self.add(item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: str, right: str) -> None:
        self.parent[self.find(right)] = self.find(left)


def analyze_network(
    pipes: list[dict[str, Any]],
    manholes: list[dict[str, Any]],
    rules: dict[str, dict[str, Any]],
    run_id: str,
    created_at: str,
    endpoint_tolerance: float,
    warning_tolerance: float,
    endpoint_tolerance_label: str,
    warning_tolerance_label: str,
    pipe_asset_field: str | None,
    manhole_asset_field: str | None,
    high_endpoint_degree: int = 6,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    endpoints = pipe_endpoints(pipes, pipe_asset_field)
    endpoint_matches = [match_endpoint(endpoint, manholes) for endpoint in endpoints]
    manhole_degree: Counter[str] = Counter()
    for endpoint, nearest, distance in endpoint_matches:
        if nearest and distance <= endpoint_tolerance:
            manhole_degree[str(nearest["objectid"])] += 1

    issues: list[dict[str, Any]] = []
    for endpoint, nearest, distance in endpoint_matches:
        if not nearest or distance > endpoint_tolerance:
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rules["WW_NET_001"],
                    source_layer="wastewater_gravity_main",
                    source_asset_id=endpoint["pipe_asset_id"],
                    source_objectid=endpoint["pipe_objectid"],
                    related_asset_id=safe_asset_id(nearest, manhole_asset_field) if nearest else "",
                    related_objectid=nearest["objectid"] if nearest else "",
                    description=f"Pipe OBJECTID {endpoint['pipe_objectid']} {endpoint['end']} endpoint is {distance_label(distance)} from nearest manhole.",
                    geometry=endpoint["geometry"],
                    threshold_used=endpoint_tolerance_label,
                    confidence="candidate",
                    issue_key=endpoint["end"],
                )
            )
        if not nearest or distance > warning_tolerance:
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rules["WW_NET_003"],
                    source_layer="wastewater_gravity_main",
                    source_asset_id=endpoint["pipe_asset_id"],
                    source_objectid=endpoint["pipe_objectid"],
                    related_asset_id=safe_asset_id(nearest, manhole_asset_field) if nearest else "",
                    related_objectid=nearest["objectid"] if nearest else "",
                    description=f"Pipe OBJECTID {endpoint['pipe_objectid']} {endpoint['end']} endpoint exceeds warning tolerance at {distance_label(distance)}.",
                    geometry=endpoint["geometry"],
                    threshold_used=warning_tolerance_label,
                    confidence="candidate",
                    issue_key=endpoint["end"],
                )
            )

    for manhole in manholes:
        degree = manhole_degree[str(manhole["objectid"])]
        if degree == 0:
            for code in ["WW_NET_002", "WW_NET_007"]:
                issues.append(
                    make_issue(
                        run_id=run_id,
                        created_at=created_at,
                        rule=rules[code],
                        source_layer="wastewater_manhole",
                        source_asset_id=safe_asset_id(manhole, manhole_asset_field),
                        source_objectid=manhole["objectid"],
                        description=f"Manhole OBJECTID {manhole['objectid']} has no matched pipe endpoint within {endpoint_tolerance_label}.",
                        geometry=manhole.get("geometry"),
                        threshold_used=endpoint_tolerance_label,
                        confidence="candidate",
                    )
                )
        if degree > high_endpoint_degree:
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rules["WW_NET_008"],
                    source_layer="wastewater_manhole",
                    source_asset_id=safe_asset_id(manhole, manhole_asset_field),
                    source_objectid=manhole["objectid"],
                    description=f"Manhole OBJECTID {manhole['objectid']} has {degree} matched pipe endpoints.",
                    geometry=manhole.get("geometry"),
                    threshold_used=f">{high_endpoint_degree} endpoints",
                    confidence="candidate",
                )
            )

    summary, components = graph_components(pipes, manholes, endpoint_matches, endpoint_tolerance)
    largest = max((component["pipe_count"] + component["manhole_count"] for component in components), default=0)
    for component in components:
        if component["pipe_count"] + component["manhole_count"] < largest and component["pipe_count"]:
            representative = component.get("representative_geometry") or {}
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rules["WW_NET_005"],
                    source_layer="network",
                    source_asset_id="",
                    source_objectid=component["component_id"],
                    description=f"Component {component['component_id']} is disconnected from the largest proximity component.",
                    geometry=representative,
                    threshold_used=endpoint_tolerance_label,
                    confidence="candidate",
                    issue_key=str(component["component_id"]),
                )
            )
        if component["pipe_count"] == 1:
            for pipe_oid in component["pipe_objectids"].split(";"):
                if pipe_oid:
                    pipe = next((item for item in pipes if str(item["objectid"]) == pipe_oid), None)
                    issues.append(
                        make_issue(
                            run_id=run_id,
                            created_at=created_at,
                            rule=rules["WW_NET_006"],
                            source_layer="wastewater_gravity_main",
                            source_asset_id=safe_asset_id(pipe, pipe_asset_field) if pipe else "",
                            source_objectid=pipe_oid,
                            description=f"Pipe OBJECTID {pipe_oid} is in a one-pipe proximity component.",
                            geometry=(pipe or {}).get("geometry"),
                            threshold_used=endpoint_tolerance_label,
                            confidence="candidate",
                        )
                    )

    issues.extend(crossing_issues(pipes, manholes, rules["WW_NET_004"], run_id, created_at, endpoint_tolerance, endpoint_tolerance_label, pipe_asset_field))
    matched_distances = [distance for _, nearest, distance in endpoint_matches if nearest and distance <= endpoint_tolerance]
    summary.update(
        {
            "matched_pipe_endpoints": len(matched_distances),
            "unmatched_pipe_endpoints": len(endpoints) - len(matched_distances),
            "endpoint_match_rate": round(len(matched_distances) / max(len(endpoints), 1), 4),
            "average_endpoint_to_manhole_distance": round(sum(matched_distances) / max(len(matched_distances), 1), 4),
            "maximum_endpoint_to_manhole_distance": round(max(matched_distances), 4) if matched_distances else 0,
            "high_degree_manholes": sum(1 for count in manhole_degree.values() if count > high_endpoint_degree),
        }
    )
    return summary, components, issues


def pipe_endpoints(pipes: list[dict[str, Any]], pipe_asset_field: str | None) -> list[dict[str, Any]]:
    endpoints = []
    for pipe in pipes:
        points = first_path(pipe.get("geometry") or {})
        if len(points) < 2:
            continue
        for end, point in [("start", points[0]), ("end", points[-1])]:
            endpoints.append(
                {
                    "pipe_objectid": pipe["objectid"],
                    "pipe_asset_id": safe_asset_id(pipe, pipe_asset_field),
                    "end": end,
                    "x": point[0],
                    "y": point[1],
                    "geometry": {"type": "point", "x": point[0], "y": point[1], "spatial_reference_wkid": pipe["geometry"].get("spatial_reference_wkid")},
                }
            )
    return endpoints


def match_endpoint(endpoint: dict[str, Any], manholes: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any] | None, float]:
    nearest = None
    best = math.inf
    for manhole in manholes:
        geometry = manhole.get("geometry") or {}
        if geometry.get("type") != "point":
            continue
        distance = math.hypot(endpoint["x"] - float(geometry["x"]), endpoint["y"] - float(geometry["y"]))
        if distance < best:
            best = distance
            nearest = manhole
    return endpoint, nearest, best


def graph_components(
    pipes: list[dict[str, Any]],
    manholes: list[dict[str, Any]],
    endpoint_matches: list[tuple[dict[str, Any], dict[str, Any] | None, float]],
    endpoint_tolerance: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    uf = UnionFind()
    pipe_nodes: dict[str, list[str]] = defaultdict(list)
    manhole_nodes = {str(manhole["objectid"]): f"mh:{manhole['objectid']}" for manhole in manholes}
    for node in manhole_nodes.values():
        uf.add(node)
    for endpoint, nearest, distance in endpoint_matches:
        pipe_node = f"pipe:{endpoint['pipe_objectid']}:{endpoint['end']}"
        if nearest and distance <= endpoint_tolerance:
            node = manhole_nodes[str(nearest["objectid"])]
        else:
            node = f"ep:{endpoint['pipe_objectid']}:{endpoint['end']}"
        uf.add(pipe_node)
        uf.add(node)
        uf.union(pipe_node, node)
        pipe_nodes[str(endpoint["pipe_objectid"])].append(node)
    for pipe_oid, nodes in pipe_nodes.items():
        if len(nodes) == 2:
            uf.union(nodes[0], nodes[1])
            uf.union(f"pipe:{pipe_oid}:start", f"pipe:{pipe_oid}:end")

    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"pipes": set(), "manholes": set(), "representative_geometry": {}})
    for manhole_oid, node in manhole_nodes.items():
        groups[uf.find(node)]["manholes"].add(manhole_oid)
        groups[uf.find(node)]["representative_geometry"] = next(
            (mh.get("geometry") for mh in manholes if str(mh["objectid"]) == manhole_oid),
            {},
        )
    for pipe in pipes:
        node = f"pipe:{pipe['objectid']}:start"
        groups[uf.find(node)]["pipes"].add(str(pipe["objectid"]))
        groups[uf.find(node)]["representative_geometry"] = pipe_endpoints([pipe], None)[0]["geometry"] if pipe_endpoints([pipe], None) else {}
    components = []
    for index, (_, group) in enumerate(sorted(groups.items(), key=lambda item: (-len(item[1]["pipes"]), -len(item[1]["manholes"]))), start=1):
        components.append(
            {
                "component_id": index,
                "pipe_count": len(group["pipes"]),
                "manhole_count": len(group["manholes"]),
                "pipe_objectids": ";".join(sorted(group["pipes"], key=int)),
                "manhole_objectids": ";".join(sorted(group["manholes"], key=int)),
                "representative_geometry": group.get("representative_geometry") or {},
            }
        )
    summary = {
        "total_connected_components": len(components),
        "largest_component_pipe_count": max((item["pipe_count"] for item in components), default=0),
        "largest_component_manhole_count": max((item["manhole_count"] for item in components), default=0),
        "largest_component_size": max((item["pipe_count"] + item["manhole_count"] for item in components), default=0),
        "isolated_components": sum(1 for item in components if item["pipe_count"] + item["manhole_count"] == 1),
        "isolated_pipes": sum(1 for item in components if item["pipe_count"] == 1),
        "isolated_manholes": sum(1 for item in components if item["pipe_count"] == 0 and item["manhole_count"] == 1),
    }
    return summary, components


def crossing_issues(
    pipes: list[dict[str, Any]],
    manholes: list[dict[str, Any]],
    rule: dict[str, Any],
    run_id: str,
    created_at: str,
    endpoint_tolerance: float,
    endpoint_tolerance_label: str,
    pipe_asset_field: str | None,
) -> list[dict[str, Any]]:
    issues = []
    for left_index, left in enumerate(pipes):
        left_points = first_path(left.get("geometry") or {})
        if len(left_points) < 2:
            continue
        for right in pipes[left_index + 1 :]:
            right_points = first_path(right.get("geometry") or {})
            if len(right_points) < 2:
                continue
            point = first_intersection(left_points, right_points)
            if not point or point_is_endpoint(point, left_points + right_points):
                continue
            if any(distance_to_manhole(point, manhole) <= endpoint_tolerance for manhole in manholes):
                continue
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer="wastewater_gravity_main",
                    source_asset_id=safe_asset_id(left, pipe_asset_field),
                    source_objectid=left["objectid"],
                    related_asset_id=safe_asset_id(right, pipe_asset_field),
                    related_objectid=right["objectid"],
                    description=f"Pipe OBJECTID {left['objectid']} crosses pipe OBJECTID {right['objectid']} without a nearby manhole candidate.",
                    geometry={"type": "point", "x": point[0], "y": point[1], "spatial_reference_wkid": left["geometry"].get("spatial_reference_wkid")},
                    threshold_used=endpoint_tolerance_label,
                    confidence="candidate",
                    issue_key=f"{right['objectid']}:{round(point[0], 3)}:{round(point[1], 3)}",
                )
            )
    return issues


def first_intersection(left: list[tuple[float, float]], right: list[tuple[float, float]]) -> tuple[float, float] | None:
    for a, b in zip(left, left[1:]):
        for c, d in zip(right, right[1:]):
            point = segment_intersection(a, b, c, d)
            if point:
                return point
    return None


def segment_intersection(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], d: tuple[float, float]) -> tuple[float, float] | None:
    den = (a[0] - b[0]) * (c[1] - d[1]) - (a[1] - b[1]) * (c[0] - d[0])
    if abs(den) < 1e-9:
        return None
    t = ((a[0] - c[0]) * (c[1] - d[1]) - (a[1] - c[1]) * (c[0] - d[0])) / den
    u = -((a[0] - b[0]) * (a[1] - c[1]) - (a[1] - b[1]) * (a[0] - c[0])) / den
    if 0 <= t <= 1 and 0 <= u <= 1:
        return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
    return None


def point_is_endpoint(point: tuple[float, float], endpoints: list[tuple[float, float]]) -> bool:
    return any(math.hypot(point[0] - x, point[1] - y) <= 0.001 for x, y in endpoints)


def distance_to_manhole(point: tuple[float, float], manhole: dict[str, Any]) -> float:
    geometry = manhole.get("geometry") or {}
    if geometry.get("type") != "point":
        return math.inf
    return math.hypot(point[0] - float(geometry["x"]), point[1] - float(geometry["y"]))


def distance_label(distance: float) -> str:
    return "no manhole found" if math.isinf(distance) else f"{distance:.2f} source units"
