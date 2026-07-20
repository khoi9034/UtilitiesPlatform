# Wastewater QA Rules

The rule catalog is:

```text
config\qa_rules\wastewater_v1.json
```

Each rule declares its code, category, severity, required semantic fields, parameters, detection method, limitation, and recommended action.

Rule groups:

- Identity: missing and duplicate mapped asset IDs.
- Attributes: missing diameter, material, status, installation year/date, invalid diameter, domains, and status conflicts.
- Geometry: null geometry, invalid geometry, short pipes, duplicate geometry candidates, multipart geometry, and simple anomaly screening.
- Connectivity: endpoint/manhole proximity, endpoint gaps, crossing candidates, components, isolated assets, and high-degree manholes.
- Flow: invert and slope checks where mapped fields are available.

Rules with unavailable required fields are skipped with an explicit reason. Unavailable fields are never counted as failed assets.

Default thresholds:

- Endpoint match tolerance: 3 feet
- Endpoint warning tolerance: 10 feet
- Short pipe threshold: 5 feet

Thresholds are converted to the source spatial reference linear unit before evaluation.
