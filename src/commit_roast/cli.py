"""`commit-roast [PATH]` prints a roast card. `commit-roast serve` runs the MCP server."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .history import GitError, compute_stats, read_commits, worst_commits
from .roasts import roast_card


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["serve"]:
        from .server import main as serve

        serve()
        return 0

    p = argparse.ArgumentParser(prog="commit-roast", description="Roast a git repo's commit history.")
    p.add_argument("path", nargs="?", default=".", help="git repo to roast (default: current directory)")
    p.add_argument("-a", "--author", help="only commits whose author name/email contains this")
    p.add_argument("--since", help='only commits after this, e.g. "2026-01-01" or "3 months ago"')
    p.add_argument("--until", help='only commits before this, e.g. "last friday"')
    p.add_argument("--json", action="store_true", help="print raw stats as JSON instead of a roast")
    args = p.parse_args(argv)

    try:
        commits = read_commits(args.path, args.author, since=args.since, until=args.until)
    except GitError as e:
        print(f"commit-roast: {e}", file=sys.stderr)
        return 1

    stats = compute_stats(commits, Path(args.path).resolve().name, args.author)
    if args.json:
        print(stats.model_dump_json(indent=2))
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(roast_card(stats, worst_commits(commits)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
