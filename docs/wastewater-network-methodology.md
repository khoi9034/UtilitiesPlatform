# Wastewater Network Methodology

Wastewater Data Health V1 builds a proximity graph from:

- Manhole points
- Gravity main start and end points
- Endpoint-to-manhole matches within the configured tolerance
- Pipes as graph edges

The graph is calculated with a simple union-find structure. NetworkX is not used because V1 only needs connected components and degree counts.

Reported metrics include:

- Connected component count
- Largest component size
- Component pipe and manhole counts
- Isolated pipes
- Isolated manholes
- Matched and unmatched pipe endpoints
- Endpoint match rate
- Average and maximum endpoint-to-manhole distance
- High-degree manholes

## Limitations

This is proximity-based connectivity, not authoritative topology. Crossings do not automatically mean connectivity. Source geometry may not be snapped. Force mains, lift stations, service laterals, treatment facilities, inspections, and project records are not included yet. Flow direction depends on mapped invert fields and is not inferred from digitized geometry.
