from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROUTES = [
    "index.html",
    "asset-inventory/index.html",
    "data-health/index.html",
    "network-intelligence/index.html",
    "cad-intake/index.html",
    "trust-pipeline/index.html",
    "data-sources/index.html",
    "data-sources/inventory/index.html",
    "projects/index.html",
    "maintenance/index.html",
    "methodology/index.html",
]

SUPPORTED_MODULES = [
    "command-center",
    "asset-inventory",
    "data-health",
    "network-intelligence",
    "cad-intake",
    "trust-pipeline",
    "data-sources",
    "projects",
    "maintenance",
    "methodology",
]

PROHIBITED = re.compile(
    r"UtilitiesPlatform_Data|https?://(?:localhost|127\.0\.0\.1)|[A-Za-z]:\\[A-Za-z0-9_. -]+\\|\.gdb|\.sde|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|"
    r"access[_-]?token|api[_-]?key\s*[:=]|connection[_-]?string\s*[:=]",
    re.IGNORECASE,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local/demo feature parity for the static portfolio demo.")
    parser.add_argument("--frontend-root", default="frontend", type=Path)
    args = parser.parse_args()

    frontend = args.frontend_root.resolve()
    errors: list[str] = []

    manifest_path = frontend / "demo-data" / "manifest.json"
    manifest = read_json(manifest_path, errors)
    fixture_files = manifest.get("files", []) if isinstance(manifest, dict) else []
    modules = manifest.get("supported_modules", []) if isinstance(manifest, dict) else []

    for route in ROUTES:
        require(frontend / "out" / route, errors)
    for fixture in fixture_files:
        require(frontend / "demo-data" / fixture, errors)
    for module in SUPPORTED_MODULES:
        if module not in modules:
            errors.append(f"manifest missing supported module: {module}")

    for path in [frontend / "lib/data-provider/types.ts", frontend / "lib/data-provider/api-provider.ts", frontend / "lib/data-provider/demo-provider.ts"]:
        text = read_text(path, errors)
        if path.name != "types.ts" and "implements PlatformDataProvider" not in text:
            errors.append(f"{path} does not implement PlatformDataProvider")

    scan_tree(frontend / "demo-data", errors)
    scan_tree(frontend / "out", errors, ignore_password_literals=True)

    if errors:
        print("Feature parity check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Feature parity check passed.")
    return 0


def require(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing {path}")


def read_json(path: Path, errors: list[str]) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"cannot read {path}: {exc}")
        return {}


def read_text(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        errors.append(f"cannot read {path}: {exc}")
        return ""


def scan_tree(root: Path, errors: list[str], *, ignore_password_literals: bool = False) -> None:
    if not root.exists():
        errors.append(f"missing {root}")
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix != ".map":
            text = path.read_text(encoding="utf-8", errors="ignore")
            pattern = PROHIBITED if ignore_password_literals else re.compile(PROHIBITED.pattern + r"|password\s*[:=]|secret\s*[:=]", re.IGNORECASE)
            if pattern.search(text):
                errors.append(f"prohibited demo content in {path}")


if __name__ == "__main__":
    raise SystemExit(main())
