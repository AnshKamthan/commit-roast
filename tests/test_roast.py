import json
import os
import re
import subprocess
from pathlib import Path

import anyio
import pytest
from mcp import Client

from commit_roast.cli import main
from commit_roast.history import (
    GitError,
    RepoStats,
    compute_stats,
    is_almost_conventional,
    is_conventional,
    is_lazy,
    is_shouty,
    read_commits,
    worst_commits,
)
from commit_roast.roasts import (
    BATTLE,
    BATTLE_FORFEIT,
    BATTLE_NO_CONTEST,
    BATTLE_TIE,
    CLEAN,
    ROASTS,
    SPICES,
    battle_card,
    battle_loser,
    roast_card,
    roast_lines,
)
from commit_roast.server import mcp

# (ISO author date with offset, message, author)
HISTORY = [
    ("2026-01-05T10:00:00+05:30", "Initial commit", "ansh"),
    ("2026-01-06T02:14:00+05:30", "fix", "ansh"),
    ("2026-01-06T02:31:00+05:30", "fix", "ansh"),
    ("2026-01-06T03:05:00+05:30", "fix", "ansh"),
    ("2026-01-07T11:00:00+05:30", "Add paged KV cache with block table", "ansh"),
    ("2026-01-09T18:30:00+05:30", "final version", "ansh"),
    ("2026-01-09T19:00:00+05:30", "FINAL VERSION FOR REAL", "ansh"),
    ("2026-01-10T12:00:00+05:30", "wip", "ansh"),
    ("2026-04-20T09:00:00+05:30", 'Revert "final version"', "ansh"),
    ("2026-04-21T09:00:00+00:00", "Document scheduler preemption", "dhruv"),
]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    def git(*args: str, env: dict[str, str] | None = None) -> None:
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True, env=env)

    git("init", "-q")
    for i, (when, msg, who) in enumerate(HISTORY):
        (tmp_path / "f.txt").write_text(str(i), encoding="utf-8")
        git("add", ".")
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": who,
            "GIT_AUTHOR_EMAIL": f"{who}@example.com",
            "GIT_AUTHOR_DATE": when,
            "GIT_COMMITTER_NAME": who,
            "GIT_COMMITTER_EMAIL": f"{who}@example.com",
            "GIT_COMMITTER_DATE": when,
        }
        git("commit", "-q", "-m", msg, env=env)
    return tmp_path


def test_reads_history_oldest_first_in_author_timezone(repo: Path):
    commits = read_commits(repo)
    assert [c.message for c in commits] == [m for _, m, _ in HISTORY]
    assert commits[1].when.hour == 2  # 02:14 IST stays 02:14, not converted to UTC


def test_stats_capture_the_crimes(repo: Path):
    s = compute_stats(read_commits(repo), "repo")
    assert s.total_commits == 10
    assert s.authors == 2
    assert s.night_owl_pct == 30.0
    assert s.most_repeated_message == "fix"
    assert s.most_repeated_count == 3
    assert s.final_mentions == 3  # includes the revert of a "final"
    assert s.reverts == 1
    assert s.shouty_commits == 1
    assert s.friday_evening_commits == 2
    assert s.longest_gap_days == pytest.approx(99.9, abs=0.1)
    assert s.longest_daily_streak == 3
    assert sum(s.commits_by_hour) == 10


def test_author_filter(repo: Path):
    s = compute_stats(read_commits(repo, author="dhruv"), "repo", "dhruv")
    assert s.total_commits == 1
    assert s.night_owl_pct == 0.0


def test_author_filter_ignores_case(repo: Path):
    assert len(read_commits(repo, author="DHRUV")) == 1
    assert len(read_commits(repo, author="Ansh@Example")) == 9


@pytest.mark.parametrize("msg", ["fix", "Fix!", "wip", "minor fixes", "update", "...", "asdf"])
def test_lazy_messages(msg: str):
    assert is_lazy(msg)


@pytest.mark.parametrize("msg", ["WHY DOES THIS WORK", "fix it!!"])
def test_shouting(msg: str):
    assert is_shouty(msg)


@pytest.mark.parametrize("msg", ["Add HTTP readiness check", "docs: update CONTRIBUTING", "Bump SDK"])
def test_acronyms_are_not_shouting(msg: str):
    assert not is_shouty(msg)


@pytest.mark.parametrize("msg", ["Fix off-by-one in block allocator", "Update README with benchmarks"])
def test_real_messages_are_not_lazy(msg: str):
    assert not is_lazy(msg)


def test_worst_commits_ranked_by_number_of_reasons(repo: Path):
    worst = worst_commits(read_commits(repo), limit=4)
    assert [len(w.reasons) for w in worst] == [3, 3, 3, 3]
    assert worst[0].message == "FINAL VERSION FOR REAL"  # ties go to the most recent
    night_fix = worst[1]
    assert night_fix.message == "fix"
    assert "message says nothing" in night_fix.reasons
    assert any(r.startswith("committed at 0") for r in night_fix.reasons)


def test_not_a_repo_raises(tmp_path: Path):
    with pytest.raises(GitError, match="isn't a git repo"):
        read_commits(tmp_path)


def test_missing_directory_raises(tmp_path: Path):
    with pytest.raises(GitError, match="no such directory"):
        read_commits(tmp_path / "path/to/any/personal/repo")


def test_empty_repo_is_zero_commits_not_an_error(tmp_path: Path):
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    assert read_commits(tmp_path) == []
    assert "Zero commits" in roast_card(compute_stats([], "empty"), [])


def test_since_and_until(repo: Path):
    assert len(read_commits(repo, since="2026-04-01")) == 2
    assert len(read_commits(repo, until="2026-01-06T12:00:00+05:30")) == 4
    assert len(read_commits(repo, since="2026-01-07", until="2026-01-10T00:00:00+05:30")) == 3


def test_bare_until_date_includes_the_whole_day(repo: Path):
    # Without pinning, git would cut "2026-01-09" off at the current time of day.
    assert [c.message for c in read_commits(repo, since="2026-01-09", until="2026-01-09")] == [
        "final version",
        "FINAL VERSION FOR REAL",
    ]


def test_cli_prints_a_roast(repo: Path, capsys: pytest.CaptureFixture[str]):
    assert main([str(repo)]) == 0
    out = capsys.readouterr().out
    assert "10 commits" in out
    assert "Narrator: they were not final." in out
    assert "Hall of shame" in out


def test_cli_on_non_repo_fails_cleanly(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert main([str(tmp_path)]) == 1
    assert "isn't a git repo" in capsys.readouterr().err


def test_cli_since_flag(repo: Path, capsys: pytest.CaptureFixture[str]):
    assert main([str(repo), "--since", "2026-04-01"]) == 0
    assert "2 commits" in capsys.readouterr().out


def test_mcp_tools_and_prompt(repo: Path):
    async def run():
        async with Client(mcp) as client:
            tools = {t.name for t in (await client.list_tools()).tools}
            assert tools == {"commit_stats", "worst_commits", "roast_battle"}

            stats = await client.call_tool("commit_stats", {"repo_path": str(repo)})
            assert not stats.is_error
            assert stats.structured_content["total_commits"] == 10

            prompt = await client.get_prompt("roast", {"repo_path": str(repo), "intensity": "brutal"})
            assert "brutal" in prompt.messages[0].content.text

    anyio.run(run)


@pytest.mark.parametrize("msg", ["fix: handle empty block table", "feat(scheduler)!: preempt on OOM", "Docs: typo"])
def test_conventional(msg: str):
    assert is_conventional(msg)
    assert not is_almost_conventional(msg)


@pytest.mark.parametrize(
    "msg",
    [
        "feature: add sampling",  # not a real type
        "fixed: race in allocator",  # past tense
        "fix : spacing before colon",
        "feat:no space",
        "feat - dash instead of colon",
        "feat(api) forgot the colon",
    ],
)
def test_almost_conventional(msg: str):
    assert is_almost_conventional(msg)


@pytest.mark.parametrize("msg", ["Fix off-by-one in block allocator", "Feature flags for tachi", "fix"])
def test_plain_messages_are_not_almost_conventional(msg: str):
    assert not is_almost_conventional(msg)


def test_new_signals_in_stats():
    from datetime import datetime

    from commit_roast.history import Commit

    when = datetime.fromisoformat("2026-02-03T12:00:00+05:30")
    msgs = [
        "fix: real conventional",
        "feature: almost",
        "fixed: also almost",
        "oops, forgot the file",
        "typo",
        "Refactor the entire scheduler so it handles preemption, swapping, and prefix caching in one pass",
    ]
    commits = [Commit(sha=f"{i:040x}", author="a", email="a@x", when=when, message=m) for i, m in enumerate(msgs)]
    s = compute_stats(commits, "r")
    assert s.conventional_pct == pytest.approx(16.7)
    assert s.almost_conventional == 2
    assert s.almost_conventional_examples == ["feature: almost", "fixed: also almost"]
    assert s.apology_commits == 2
    assert s.novelist_commits == 1
    assert "*almost* follow Conventional Commits" in "\n".join(roast_lines(s))


def _everything_stats() -> RepoStats:
    """Stats that trip every roast at once, so every template gets exercised."""
    return RepoStats(
        repo="r",
        author_filter=None,
        total_commits=50,
        authors=1,
        first_commit=None,
        last_commit=None,
        night_owl_pct=40.0,
        weekend_pct=50.0,
        friday_evening_commits=5,
        busiest_hour=3,
        busiest_day="Friday",
        commits_by_hour=[1] * 24,
        lazy_message_pct=60.0,
        median_message_length=4.0,
        shortest_messages=["."],
        most_repeated_message="fix",
        most_repeated_count=9,
        final_mentions=4,
        reverts=5,
        shouty_commits=3,
        longest_gap_days=120.5,
        longest_daily_streak=12,
        conventional_pct=10.0,
        almost_conventional=3,
        almost_conventional_examples=["feature: x"],
        apology_commits=4,
        novelist_commits=6,
    )


@pytest.mark.parametrize("spice", SPICES)
def test_every_template_formats(spice: str):
    s = _everything_stats()
    ctx = {**s.model_dump(), "ex": "feature: x", "hour": "3am"}
    for _, templates in ROASTS:
        for t in templates[spice]:
            assert "{" not in t.format(**ctx)
    for t in CLEAN[spice]:
        t.format(**ctx)


def test_same_seed_same_roast_different_spice_different_roast():
    s = _everything_stats()
    assert roast_lines(s, "medium", seed=1) == roast_lines(s, "medium", seed=1)
    assert roast_lines(s, "gentle") != roast_lines(s, "brutal")
    assert any("ransom note" in line or "paying per letter" in line for line in roast_lines(s, "brutal"))


def test_cli_spice(repo: Path, capsys: pytest.CaptureFixture[str]):
    assert main([str(repo), "--spice", "brutal"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("🌋")
    assert "The word has lost all meaning" in out


def test_no_template_swallowed_another():
    """Guards against a missing comma silently gluing two jokes into one string."""
    for _, templates in ROASTS:
        for spice_templates in templates.values():
            for t in spice_templates:
                # Two glued jokes repeat their number ("{night_owl_pct}% ... {night_owl_pct}% ...").
                fields = re.findall(r"\{(\w+)", t)
                assert len(fields) == len(set(fields)), f"looks like two jokes merged: {t}"


def test_mcp_resources():
    from mcp.types import TextResourceContents

    async def run():
        async with Client(mcp) as client:
            uris = [str(r.uri) for r in (await client.list_resources()).resources]
            assert uris == ["commit-roast://signals"]
            templates = [t.uri_template for t in (await client.list_resource_templates()).resource_templates]
            assert templates == ["commit-roast://jokes/{spice}"]

            signals = (await client.read_resource("commit-roast://signals")).contents[0]
            assert isinstance(signals, TextResourceContents)
            assert "novelist_commits" in signals.text

            brutal = (await client.read_resource("commit-roast://jokes/brutal")).contents[0]
            assert isinstance(brutal, TextResourceContents)
            assert "ransom note" in brutal.text

    anyio.run(run)


def test_signals_resource_documents_every_stat():
    """If you add a stat to RepoStats, this fails until the resource explains it."""
    from commit_roast.server import SIGNALS_MD

    undocumented = {
        "repo",
        "author_filter",
        "total_commits",
        "authors",
        "first_commit",
        "last_commit",
        "busiest_hour",
        "busiest_day",
        "commits_by_hour",
        "median_message_length",
        "shortest_messages",
        "most_repeated_count",
        "almost_conventional_examples",
    }
    for field in RepoStats.model_fields:
        if field not in undocumented:
            assert f"| {field} |" in SIGNALS_MD, f"{field} is missing from commit-roast://signals"


def test_battle_loser_is_the_bigger_criminal():
    guilty = _everything_stats().model_copy(update={"author_filter": "guilty"})
    clean = guilty.model_copy(update={"author_filter": "clean", "night_owl_pct": 0.0, "lazy_message_pct": 0.0})
    assert battle_loser(guilty, clean) is guilty
    assert battle_loser(clean, guilty) is guilty
    assert battle_loser(clean, clean) is None
    assert "loser: nobody (tie)" in battle_card(clean, clean, [], [])


def test_battle_too_few_commits_is_a_forfeit_not_a_verdict(repo: Path):
    ansh = compute_stats(read_commits(repo, author="ansh"), "repo", "ansh")
    dhruv = compute_stats(read_commits(repo, author="dhruv"), "repo", "dhruv")
    # ansh is the bigger criminal, but dhruv's 1 clean commit is a sample size of one.
    assert battle_loser(ansh, dhruv) is dhruv
    card = battle_card(ansh, dhruv, [], [], "medium")
    verdict = card.splitlines()[-1]
    assert "loser: dhruv" in card
    assert "forfeit" in verdict
    assert "1 commit" in verdict and "1 commits" not in verdict


def test_battle_both_small_is_no_contest(repo: Path):
    dhruv = compute_stats(read_commits(repo, author="dhruv"), "repo", "dhruv")
    ghost = compute_stats([], "repo", "ghost")
    assert battle_loser(dhruv, ghost) is None
    assert "loser: nobody (not enough commits)" in battle_card(dhruv, ghost, [], [])


def test_cli_battle(repo: Path, capsys: pytest.CaptureFixture[str]):
    assert main([str(repo), "--vs", "ansh", "dhruv", "--spice", "brutal"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("🌋 roast battle")
    rows = {line.split("  ")[0]: line.split() for line in out.splitlines() if "  " in line}
    assert rows["commits"][-2:] == ["9", "1"]
    assert rows["night owl"][-2:] == ["33.3%", "0.0%"]
    assert rows["lazy messages"][-2:] == ["55.6%", "0.0%"]
    assert "'FINAL VERSION FOR RE…'" in out  # ansh's worst, truncated to fit the column
    assert "(none)" in out  # dhruv has nothing to be ashamed of
    assert "loser: dhruv" in out  # 1 commit is a forfeit
    assert out.strip().splitlines()[-1].startswith("• dhruv has 1 commit.")  # brutal forfeit joke


def test_cli_battle_matches_like_author(repo: Path, capsys: pytest.CaptureFixture[str]):
    # Same case-insensitive substring match on name/email as --author.
    assert main([str(repo), "--vs", "ANSH@example", "Dhr", "--json"]) == 0
    stats = json.loads(capsys.readouterr().out)
    assert stats["ANSH@example"]["total_commits"] == 9
    assert stats["Dhr"]["total_commits"] == 1


def test_cli_battle_rejects_author(repo: Path):
    with pytest.raises(SystemExit):
        main([str(repo), "--vs", "ansh", "dhruv", "--author", "ansh"])


@pytest.mark.parametrize("spice", SPICES)
def test_every_battle_template_formats(spice: str):
    s = _everything_stats()
    for table in (BATTLE, BATTLE_FORFEIT, BATTLE_NO_CONTEST, BATTLE_TIE):
        for t in table[spice]:
            line = t.format(**s.model_dump(), loser="alice", winner="bob", commits="3 commits")
            assert "{" not in line and "alice" in line
            fields = re.findall(r"\{(\w+)", t)
            assert len(fields) == len(set(fields)), f"looks like two jokes merged: {t}"


def test_mcp_roast_battle(repo: Path):
    async def battle(a: str, b: str, **kw: str) -> dict:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "roast_battle", {"repo_path": str(repo), "author_a": a, "author_b": b, **kw}
            )
            assert not result.is_error
            return result.structured_content

    async def run():
        # ansh (9 commits, 88.9) vs everyone (10 commits, 80.0): a real verdict on the numbers.
        r = await battle("ansh", "example.com")
        assert (r["loser"], r["reason"]) == ("ansh", "numbers")
        assert r["author_a"]["total_commits"] == 9
        assert r["author_b"]["total_commits"] == 10
        assert r["crime_score_a"] == pytest.approx(88.9)
        assert r["crime_score_b"] == pytest.approx(80.0)

        r = await battle("ANSH", "Dhruv")  # case-insensitive, like --vs
        assert (r["loser"], r["reason"]) == ("Dhruv", "forfeit")

        r = await battle("ansh", "ansh")
        assert (r["loser"], r["reason"]) == (None, "tie")

        r = await battle("ansh", "dhruv", since="2026-04-01")  # 1 commit each
        assert (r["loser"], r["reason"]) == (None, "no-contest")

    anyio.run(run)


def test_mcp_roast_battle_bad_repo_is_a_tool_error(tmp_path: Path):
    async def run():
        async with Client(mcp) as client:
            result = await client.call_tool(
                "roast_battle", {"repo_path": str(tmp_path), "author_a": "a", "author_b": "b"}
            )
            assert result.is_error

    anyio.run(run)


def test_mcp_battle_prompt():
    async def run():
        async with Client(mcp) as client:
            prompts = {p.name for p in (await client.list_prompts()).prompts}
            assert prompts == {"roast", "battle"}
            prompt = await client.get_prompt(
                "battle", {"repo_path": "/r", "author_a": "ansh", "author_b": "dhruv", "intensity": "brutal"}
            )
            text = prompt.messages[0].content.text
            assert "roast_battle" in text and "'brutal'" in text
            assert "author_a='ansh'" in text and "author_b='dhruv'" in text

    anyio.run(run)


def test_signals_resource_documents_every_battle_reason():
    from typing import get_args

    from commit_roast.roasts import BattleReason
    from commit_roast.server import SIGNALS_MD

    for reason in get_args(BattleReason):
        assert f"| {reason} |" in SIGNALS_MD, f"battle reason {reason} is missing from commit-roast://signals"
