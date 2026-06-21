#!/usr/bin/env python3
"""Audit source files that need split management."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".next",
    "dist",
    "node_modules",
    "static",
}


@dataclass(frozen=True)
class SourceFile:
    path: Path
    lines: int
    side: str
    module: str
    priority: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan backend/frontend source files for split management."
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=500,
        help="Line count threshold for reporting files. Default: 500.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=120,
        help="Maximum number of files to print. Default: 120.",
    )
    parser.add_argument(
        "--fail-on-over-limit",
        action="store_true",
        help="Exit with status 1 when files exceed the threshold.",
    )
    return parser.parse_args()


def should_skip(path: Path) -> bool:
    parts = set(path.relative_to(ROOT).parts)
    return bool(parts & EXCLUDED_PARTS)


def iter_source_files() -> list[Path]:
    paths: list[Path] = []
    for source_root in (ROOT / "backend", ROOT / "frontend"):
        if not source_root.exists():
            continue
        for path in source_root.rglob("*"):
            if (
                path.is_file()
                and path.suffix in SOURCE_EXTENSIONS
                and not should_skip(path)
            ):
                paths.append(path)
    return paths


def count_lines(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def priority(lines: int) -> str:
    if lines > 2000:
        return "P0"
    if lines > 1000:
        return "P1"
    return "P2"


def has_token(path: Path, *tokens: str) -> bool:
    normalized = (
        path.as_posix().lower().replace("/", "_").replace("-", "_").replace(".", "_")
    )
    wrapped = f"_{normalized}_"
    return any(f"_{token}_" in wrapped for token in tokens)


def backend_module(relative: Path) -> str:
    parts = relative.parts
    if relative.name == "main.py":
        return "api"
    if len(parts) > 1 and parts[1] in {"api", "routes"}:
        return "api"
    if len(parts) > 1 and parts[1] in {"database", "backtest", "repositories"}:
        return "data"
    if has_token(relative, "ai", "hyper_ai", "prompt", "llm"):
        return "ai"
    if has_token(relative, "hyperliquid", "binance", "trading", "trade", "order"):
        return "trade"
    if has_token(relative, "factor", "signal", "market_flow", "regime", "kline"):
        return "factor"
    if (len(parts) > 1 and parts[1] == "program_trader") or has_token(
        relative, "program"
    ):
        return "program"
    if has_token(relative, "asset", "snapshot", "market", "persistence"):
        return "data"
    return "backend"


def frontend_module(relative: Path) -> str:
    parts = relative.parts
    path_text = relative.as_posix().lower()
    if relative.name in {"main.tsx", "main.ts", "app.tsx", "app.ts"}:
        return "app"
    if len(parts) > 3 and parts[2] == "components":
        return parts[3].replace("_", "-")
    if "auth" in path_text:
        return "auth"
    if len(parts) > 2 and parts[2] == "lib":
        return "api"
    return "app"


def classify(path: Path) -> tuple[str, str]:
    relative = path.relative_to(ROOT)
    if relative.parts[0] == "backend":
        return "backend", backend_module(relative)
    if relative.parts[0] == "frontend":
        return "frontend", frontend_module(relative)
    return "other", "other"


def build_report(threshold: int) -> list[SourceFile]:
    files: list[SourceFile] = []
    for path in iter_source_files():
        lines = count_lines(path)
        if lines <= threshold:
            continue
        side, module = classify(path)
        files.append(
            SourceFile(
                path=path.relative_to(ROOT),
                lines=lines,
                side=side,
                module=module,
                priority=priority(lines),
            )
        )
    return sorted(files, key=lambda item: (-item.lines, item.path.as_posix()))


def print_summary(files: list[SourceFile]) -> None:
    by_side: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_module: dict[tuple[str, str], int] = {}
    for item in files:
        by_side[item.side] = by_side.get(item.side, 0) + 1
        by_priority[item.priority] = by_priority.get(item.priority, 0) + 1
        key = (item.side, item.module)
        by_module[key] = by_module.get(key, 0) + 1

    print(f"files_over_threshold: {len(files)}")
    print("by_side:")
    for side in sorted(by_side):
        print(f"  {side}: {by_side[side]}")
    print("by_priority:")
    for label in ("P0", "P1", "P2"):
        print(f"  {label}: {by_priority.get(label, 0)}")
    print("by_module:")
    for (side, module), count in sorted(by_module.items()):
        print(f"  {side}/{module}: {count}")


def print_table(files: list[SourceFile], limit: int) -> None:
    if limit <= 0:
        return
    print()
    print("| Priority | Lines | Side | Module | File |")
    print("| --- | ---: | --- | --- | --- |")
    for item in files[:limit]:
        print(
            f"| {item.priority} | {item.lines} | {item.side} | "
            f"{item.module} | `{item.path.as_posix()}` |"
        )


def main() -> int:
    args = parse_args()
    files = build_report(args.threshold)
    print_summary(files)
    print_table(files, args.limit)
    if args.fail_on_over_limit and files:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
