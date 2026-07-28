"""Terminal source-layer harness."""

from __future__ import annotations
import argparse
from resolvestock.cache import ResponseCache
from resolvestock.config import Config
from resolvestock.sources.base import CachedHttp, SearchQuery
from resolvestock.sources.registry import SearchOutcome, build_registry


def format_results(outcome: SearchOutcome) -> str:
    lines = [f"{len(outcome.results)} result(s)"] if outcome.results else ["no results"]
    for index, result in enumerate(outcome.results, 1):
        size = (
            f"{result.width}x{result.height}"
            if result.width and result.height
            else "size unknown"
        )
        lines.append(
            f"{index:>3}. [{result.source}] {result.title}\n"
            f"     {size}  license={result.license_id}  "
            f"alpha={result.has_alpha}\n"
            f"     {result.download_url}"
        )
    lines.extend(
        f"! {name} failed: {message}" for name, message in outcome.errors.items()
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="resolvestock")
    parser.add_argument("query")
    parser.add_argument("--transparent", action="store_true")
    parser.add_argument("--vectors", action="store_true")
    parser.add_argument("--include-restricted", action="store_true")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--per-page", type=int, default=20)
    args = parser.parse_args(argv)
    config = Config.load()
    registry = build_registry(
        CachedHttp(ResponseCache(config.library_dir / ".cache" / "responses.db")),
        config,
    )
    outcome = registry.search(
        SearchQuery(
            args.query,
            args.page,
            args.per_page,
            args.transparent,
            args.vectors,
            not args.include_restricted,
        )
    )
    print(format_results(outcome))
    return 0 if outcome.results else 1


if __name__ == "__main__":
    raise SystemExit(main())
