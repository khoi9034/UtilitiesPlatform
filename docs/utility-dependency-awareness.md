# Utility Dependency Awareness

Missing utility layers can change how a QA finding should be interpreted. A disconnected wastewater component may be a data defect, but it may also reflect missing force mains, lift stations, service laterals, private networks, external jurisdiction networks, or treatment facility context.

Phase 2 adds:

- `config\utility_dependencies\wastewater.json`
- dependency-aware issue metadata
- `possible_missing_dependency`
- dependency explanations on network findings

Connectivity issues are not dismissed automatically. Missing dependencies are review context, not proof that a finding is false.

The same catalog pattern can be reused for water, stormwater, telecom, electric, and gas.
