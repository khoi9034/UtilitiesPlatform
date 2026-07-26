from __future__ import annotations

import re
from collections import Counter

INFRASTRUCTURE_TOKENS = {"dbo", "sde", "db", "database", "schema"}


def normalize_package_names(names: list[str]) -> dict[str, dict[str, object]]:
    prefix = repeated_enterprise_prefix(names)
    output: dict[str, dict[str, object]] = {}
    for name in names:
        tokens = split_tokens(name)
        matched = bool(prefix and [token.lower() for token in tokens[: len(prefix)]] == prefix)
        canonical_tokens = tokens[len(prefix) :] if matched else tokens
        output[name] = {
            "canonical_layer_name": "_".join(canonical_tokens) or name,
            "source_prefix_tokens": tokens[: len(prefix)] if matched else [],
            "classification_tokens": [token.lower() for token in canonical_tokens],
            "normalization_rule_version": "enterprise_name_normalization_v1",
        }
    return output


def repeated_enterprise_prefix(names: list[str]) -> list[str]:
    minimum = max(5, (len(names) + 1) // 2)
    counts: Counter[tuple[str, ...]] = Counter()
    for tokens in map(split_tokens, names):
        for length in range(1, min(5, len(tokens)) + 1):
            prefix = tuple(token.lower() for token in tokens[:length])
            if any(token in INFRASTRUCTURE_TOKENS or token.endswith("gis") for token in prefix):
                counts[prefix] += 1
    eligible = [prefix for prefix, count in counts.items() if count >= minimum and prefix[-1] in INFRASTRUCTURE_TOKENS]
    return list(max(eligible, key=len)) if eligible else []


def split_tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[_\-.]+", value.strip()) if token]
