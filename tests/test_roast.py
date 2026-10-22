import os
import subprocess
from pathlib import Path

import anyio
import pytest
from mcp import Client

from commit_roast.cli import main
from commit_roast.history import GitError, compute_stats, is_lazy, is_shouty, read_commits, worst_commits
from commit_roast.roasts import roast_card
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
            assert tools == {"commit_stats", "worst_commits"}

            stats = await client.call_tool("commit_stats", {"repo_path": str(repo)})
            assert not stats.is_error
            assert stats.structured_content["total_commits"] == 10

            prompt = await client.get_prompt("roast", {"repo_path": str(repo), "intensity": "brutal"})
            assert "brutal" in prompt.messages[0].content.text

    anyio.run(run)
