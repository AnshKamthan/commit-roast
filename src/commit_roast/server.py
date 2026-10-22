"""MCP server: hands the evidence to the model and lets it do the roasting."""

from __future__ import annotations

from pathlib import Path

from mcp.server import MCPServer

from .history import RepoStats, WorstCommit, compute_stats, read_commits
from .history import worst_commits as rank_worst

mcp = MCPServer("commit-roast")


def _name(repo_path: str) -> str:
    return Path(repo_path).expanduser().resolve().name


@mcp.tool()
def commit_stats(repo_path: str, author: str | None = None) -> RepoStats:
    """Habits mined from a git repo's history: late-night commits, lazy messages, repeated
    messages, 'final' claims, gaps and streaks. Times are in each author's own timezone.

    Args:
        repo_path: Path to a local git repository.
        author: Optional substring of author name or email, to roast one person only.
    """
    path = str(Path(repo_path).expanduser())
    return compute_stats(read_commits(path, author), _name(path), author)


@mcp.tool()
def worst_commits(repo_path: str, author: str | None = None, limit: int = 10) -> list[WorstCommit]:
    """The most roastable individual commits, each with the reasons it made the list.

    Args:
        repo_path: Path to a local git repository.
        author: Optional substring of author name or email.
        limit: How many to return.
    """
    path = str(Path(repo_path).expanduser())
    return rank_worst(read_commits(path, author), limit)


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
        f"Call commit_stats and worst_commits on {repo_path}{who}. Then roast this developer's commit "
        f"history at '{intensity}' intensity, like a friend at a comedy roast who has actually read the git log. "
        "Every joke must be grounded in a specific number or commit from the tools. Quote real commit "
        "messages and SHAs. Keep it to 8-12 lines, then end with one genuinely useful piece of advice "
        "about their git habits. Punch at habits, never at the person."
    )


def main() -> None:
    mcp.run()
