"""MCP server: hands the evidence to the model and lets it do the roasting."""

from __future__ import annotations

from pathlib import Path

from mcp.server import MCPServer

from .history import NOVEL_LENGTH, RepoStats, WorstCommit, compute_stats, read_commits
from .history import worst_commits as rank_worst
from .roasts import ROASTS, SPICES

mcp = MCPServer("commit-roast")


def _name(repo_path: str) -> str:
    return Path(repo_path).expanduser().resolve().name


@mcp.tool()
def commit_stats(
    repo_path: str, author: str | None = None, since: str | None = None, until: str | None = None
) -> RepoStats:
    """Habits mined from a git repo's history: late-night commits, lazy messages, repeated
    messages, 'final' claims, gaps and streaks. Times are in each author's own timezone.

    Args:
        repo_path: Path to a local git repository.
        author: Optional substring of author name or email, to roast one person only.
        since: Optional start, anything git understands ("2026-01-01", "3 months ago").
        until: Optional end, same formats.
    """
    path = str(Path(repo_path).expanduser())
    return compute_stats(read_commits(path, author, since=since, until=until), _name(path), author)


@mcp.tool()
def worst_commits(
    repo_path: str, author: str | None = None, limit: int = 10, since: str | None = None, until: str | None = None
) -> list[WorstCommit]:
    """The most roastable individual commits, each with the reasons it made the list.

    Args:
        repo_path: Path to a local git repository.
        author: Optional substring of author name or email.
        limit: How many to return.
        since: Optional start, anything git understands.
        until: Optional end.
    """
    path = str(Path(repo_path).expanduser())
    return rank_worst(read_commits(path, author, since=since, until=until), limit)


SIGNALS_MD = f"""# What commit-roast measures

All times are the author's own local time, from each commit's timezone offset. Merge commits are skipped.
Only the subject line (first line of the message) is judged.

| Signal | Definition |
|---|---|
| night_owl_pct | % of commits between 00:00 and 04:59 |
| weekend_pct | % of commits on Saturday or Sunday |
| friday_evening_commits | Friday, 17:00 or later |
| lazy_message_pct | Whole subject is filler: fix, wip, update, changes, ..., asdf, initial commit |
| most_repeated_message | Most common subject, if it appears more than once |
| final_mentions | Subject contains the word "final" |
| reverts | Subject starts with "Revert" |
| shouty_commits | Subject is >=60% uppercase letters (min 6 letters), or contains "!!" |
| longest_gap_days | Longest time between consecutive commits |
| longest_daily_streak | Most consecutive calendar days with a commit |
| conventional_pct | % of subjects matching Conventional Commits exactly: type(scope)!: description |
| almost_conventional | Subjects clearly trying to be Conventional Commits and missing (feature:, fixed:, fix :, feat(api) no colon) |
| apology_commits | Subject contains oops, whoops, sorry, my bad, typo, forgot, actually |
| novelist_commits | Subject longer than {NOVEL_LENGTH} characters |
"""


@mcp.resource("commit-roast://signals", mime_type="text/markdown")
def signals() -> str:
    """Definitions of every stat commit_stats returns, so a roast can cite them precisely."""
    return SIGNALS_MD


@mcp.resource("commit-roast://jokes/{spice}", mime_type="text/markdown")
def jokes(spice: str) -> str:
    """The offline CLI's joke templates for one spice level (gentle, medium, brutal), as a house style guide."""
    if spice not in SPICES:
        raise ValueError(f"spice must be one of {', '.join(SPICES)}")
    lines = [f"# {spice} jokes (placeholders in braces are filled from commit_stats)", ""]
    lines += [f"- {t}" for _, templates in ROASTS for t in templates[spice]]
    return "\n".join(lines)


@mcp.prompt()
def roast(repo_path: str, author: str = "", intensity: str = "medium") -> str:
    """Roast a repo's commit history.

    Args:
        repo_path: Path to a local git repository.
        author: Optional author to focus on.
        intensity: gentle, medium, or brutal.
    """
    who = f" for author '{author}'" if author else ""
    return (
        f"Call commit_stats and worst_commits on {repo_path}{who}. The resource commit-roast://signals defines "
        f"every stat, and commit-roast://jokes/{intensity} shows the house style if it helps. Then roast this "
        "developer's commit "
        f"history at '{intensity}' intensity, like a friend at a comedy roast who has actually read the git log. "
        "Every joke must be grounded in a specific number or commit from the tools. Quote real commit "
        "messages and SHAs. Keep it to 8-12 lines, then end with one genuinely useful piece of advice "
        "about their git habits. Punch at habits, never at the person."
    )


def main() -> None:
    mcp.run()
