# Duplicate Layer Review

Duplicate detection is a review aid. It never selects an authoritative source automatically.

V1 compares normalized names, geometry type, record counts, and available safe metadata. Examples include underscore differences, compact names, legacy copies, simplified representations, and database views.

Possible review outcomes include retaining both, selecting an authoritative source, marking a legacy copy, marking a simplified representation, marking a view, excluding from staging, deferring, or requiring data-owner confirmation.

Potential duplicate status blocks staging until the reviewer records a decision.
