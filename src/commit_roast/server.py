"""MCP server: hands the evidence to the model and lets it do the roasting."""

from __future__ import annotations

from pathlib import Path

from mcp.server import MCPServer
from pydantic import BaseModel, Field

from .history import NOVEL_LENGTH, RepoStats, WorstCommit, compute_stats, read_commits
from .history import worst_commits as rank_worst
from .roasts import MIN_BATTLE_COMMITS, ROASTS, SPICES, BattleReason, battle_loser, battle_reason, crime_score

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


class RoastBattle(BaseModel):
    author_a: RepoStats
    author_b: RepoStats
    crime_score_a: float = Field(description="night_owl_pct + lazy_message_pct for author_a; higher is worse")
    crime_score_b: float
    loser: str | None = Field(description="The losing author, as passed in; null for a tie or no contest")
    reason: BattleReason


@mcp.tool()
def roast_battle(
    repo_path: str, author_a: str, author_b: str, since: str | None = None, until: str | None = None
) -> RoastBattle:
    """Two authors' commit habits side by side, plus who loses the roast battle and why.

    The higher crime score (night_owl_pct + lazy_message_pct) loses ("numbers"). An author with fewer
    than 5 commits loses by "forfeit"; if both have fewer than 5 it's a "no-contest". Equal scores are a "tie".

    Args:
        repo_path: Path to a local git repository.
        author_a: Substring of the first author's name or email (case-insensitive).
        author_b: Substring of the second author's name or email (case-insensitive).
        since: Optional start, anything git understands.
        until: Optional end.
    """
    path = str(Path(repo_path).expanduser())
    a, b = (
        compute_stats(read_commits(path, who, since=since, until=until), _name(path), who)
        for who in (author_a, author_b)
    )
    loser = battle_loser(a, b)
    return RoastBattle(
        author_a=a,
        author_b=b,
        crime_score_a=crime_score(a),
        crime_score_b=crime_score(b),
        loser=loser.author_filter if loser else None,
        reason=battle_reason(a, b),
    )


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

## Roast battles (roast_battle)

crime score = night_owl_pct + lazy_message_pct. Authors are matched case-insensitively by name or email substring.

| reason | Meaning |
|---|---|
| numbers | Both have at least {MIN_BATTLE_COMMITS} commits; the higher crime score loses |
| forfeit | One author has fewer than {MIN_BATTLE_COMMITS} commits and loses, whatever the numbers say |
| no-contest | Both have fewer than {MIN_BATTLE_COMMITS} commits; no loser |
| tie | Both have at least {MIN_BATTLE_COMMITS} commits and equal crime scores; no loser |
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


@mcp.prompt()
def battle(repo_path: str, author_a: str, author_b: str, intensity: str = "medium") -> str:
    """Roast battle between two authors in a repo.

    Args:
        repo_path: Path to a local git repository.
        author_a: First author (name or email substring).
        author_b: Second author.
        intensity: gentle, medium, or brutal.
    """
    return (
        f"Call roast_battle on {repo_path} with author_a='{author_a}' and author_b='{author_b}'. You may also call "
        "worst_commits for each author to quote their worst commit. The resource commit-roast://signals explains "
        "every stat and every verdict reason. Then host a roast battle at "
        f"'{intensity}' intensity: a few lines on each author, comparing their real numbers, then announce the "
        "loser exactly as the tool decided. Don't pick a different one. If the reason is 'forfeit', 'no-contest' "
        "or 'tie', say so and explain why. Every joke must cite a specific number or commit from the tools; "
        "never invent stats. Punch at habits, never at the person."
    )


def main() -> None:
    mcp.run()
