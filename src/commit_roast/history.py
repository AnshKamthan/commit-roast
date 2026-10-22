"""Read a repo's commit history and turn it into roastable evidence."""

from __future__ import annotations

import os
import re
import subprocess
from collections import Counter
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from statistics import median

from pydantic import BaseModel, Field

FIELD = "\x1f"
RECORD = "\x1e"

# Messages that say nothing. Matched against the whole lowercased, stripped message.
LAZY_PATTERNS = [
    r"\.+",
    r"(minor )?(fix|fixes|fixed|fixing)( stuff| things| bug| bugs| it)?",
    r"(small |minor )?(update|updates|updated|changes|change|edit|edits)",
    r"wip",
    r"(asdf|qwerty|test|testing|temp|tmp|stuff|misc|idk|ok|done|commit)",
    r"(initial commit|first commit)",
]
FINAL_RE = re.compile(r"\bfinal\b", re.IGNORECASE)
REVERT_RE = re.compile(r"^revert\b", re.IGNORECASE)
# Conventional Commits (conventionalcommits.org): "type(scope)!: description". Types are case-insensitive per the spec.
CC_TYPES = "feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert"
CONVENTIONAL_RE = re.compile(rf"^({CC_TYPES})(\([^)]+\))?!?: \S", re.IGNORECASE)
# Clearly *trying* to be conventional and missing: wrong type word, no space, space before colon, dash, no colon.
ALMOST_TYPES = CC_TYPES + "|feature|features|fixed|fixes|bugfix|doc|tests|chores"
ALMOST_CONVENTIONAL_RE = re.compile(
    rf"^({ALMOST_TYPES})(\([^)]*\))?!?\s*[:\-]\s*\S|^({ALMOST_TYPES})\([^)]*\)\s+\S", re.IGNORECASE
)
APOLOGY_RE = re.compile(r"\b(oops+|whoops|sorry|my bad|typo|forgot|actually)\b", re.IGNORECASE)
NOVEL_LENGTH = 72  # git's long-standing convention for subject lines
BARE_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class Commit(BaseModel):
    sha: str
    author: str
    email: str
    when: datetime = Field(description="Author time, in the author's own timezone")
    message: str


class RepoStats(BaseModel):
    """Everything a roaster needs, and nothing it doesn't."""

    repo: str
    author_filter: str | None
    total_commits: int
    authors: int
    first_commit: datetime | None
    last_commit: datetime | None
    night_owl_pct: float = Field(description="% of commits made between midnight and 5am, author's local time")
    weekend_pct: float
    friday_evening_commits: int = Field(description="Commits on Friday after 5pm")
    busiest_hour: int | None
    busiest_day: str | None
    commits_by_hour: list[int] = Field(description="24 buckets, author's local time")
    lazy_message_pct: float = Field(description="% of commits whose entire message is something like 'fix' or 'wip'")
    median_message_length: float
    shortest_messages: list[str]
    most_repeated_message: str | None
    most_repeated_count: int
    final_mentions: int = Field(description="Commits whose message contains the word 'final'")
    reverts: int
    shouty_commits: int = Field(description="Messages that are mostly uppercase or contain '!!'")
    longest_gap_days: float = Field(description="Longest silence between consecutive commits")
    longest_daily_streak: int = Field(description="Most consecutive calendar days with at least one commit")
    conventional_pct: float = Field(description="% of commits that follow Conventional Commits exactly")
    almost_conventional: int = Field(description="Commits that try to be Conventional Commits and miss")
    almost_conventional_examples: list[str]
    apology_commits: int = Field(description="Messages with oops / sorry / typo / forgot / actually")
    novelist_commits: int = Field(description=f"Subject lines longer than {NOVEL_LENGTH} characters")


class WorstCommit(BaseModel):
    sha: str
    when: datetime
    message: str
    reasons: list[str]


class GitError(RuntimeError):
    """Raised when the path isn't a git repo or git itself fails."""


def read_commits(
    repo_path: str | Path,
    author: str | None = None,
    limit: int | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[Commit]:
    """Return non-merge commits, oldest first. A repo with no commits yet returns [].

    `since` / `until` take anything `git log` understands: "2026-01-01", "3 months ago", "last friday".

    Raises:
        GitError: if `repo_path` doesn't exist, isn't a git repository, or `git log` fails.
    """
    path = Path(repo_path).expanduser()
    if not path.is_dir():
        raise GitError(f"no such directory: {path}")
    cmd = [
        "git",
        "-C",
        str(path),
        "log",
        "--no-merges",
        f"--format=%H{FIELD}%an{FIELD}%ae{FIELD}%aI{FIELD}%B{RECORD}",
    ]
    if author:
        cmd.append(f"--author={author}")
    if limit:
        cmd.append(f"-n{limit}")
    if since:
        cmd.append(f"--since={_day_bound(since, '00:00:00')}")
    if until:
        cmd.append(f"--until={_day_bound(until, '23:59:59')}")
    try:
        # LC_ALL=C keeps git's error messages in English so the checks below work on any locale.
        env = {**os.environ, "LC_ALL": "C"}
        out = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True, env=env
        ).stdout
    except FileNotFoundError as e:
        raise GitError("git is not installed") from e
    except subprocess.CalledProcessError as e:
        err = e.stderr.strip()
        if "does not have any commits yet" in err:
            return []
        if "not a git repository" in err:
            raise GitError(f"{path} isn't a git repo (no .git here or in any parent folder)") from e
        raise GitError(err or f"git log failed in {path}") from e

    commits = []
    for rec in out.split(RECORD):
        rec = rec.strip("\n")
        if not rec:
            continue
        sha, name, email, when, msg = rec.split(FIELD, 4)
        commits.append(
            Commit(sha=sha, author=name, email=email, when=datetime.fromisoformat(when), message=msg.strip())
        )
    commits.reverse()
    return commits


def _day_bound(when: str, clock: str) -> str:
    """git reads a bare date like "2026-01-07" as that date at the *current time of day*.
    Pin bare dates to the start (or end) of the day so --since/--until mean whole days."""
    return f"{when} {clock}" if BARE_DATE_RE.fullmatch(when.strip()) else when


def is_shouty(subject_line: str) -> bool:
    """Mostly-uppercase or '!!'. Acronyms like HTTP in a normal sentence don't count."""
    letters = [ch for ch in subject_line if ch.isalpha()]
    caps = sum(ch.isupper() for ch in letters)
    return "!!" in subject_line or (len(letters) >= 6 and caps / len(letters) >= 0.6)


def subject(message: str) -> str:
    return message.splitlines()[0].strip() if message else ""


def is_conventional(subject_line: str) -> bool:
    return bool(CONVENTIONAL_RE.match(subject_line))


def is_almost_conventional(subject_line: str) -> bool:
    return not is_conventional(subject_line) and bool(ALMOST_CONVENTIONAL_RE.match(subject_line))


def is_lazy(message: str) -> bool:
    s = subject(message).lower().strip(" !?")
    return any(re.fullmatch(p, s) for p in LAZY_PATTERNS)


def _pct(n: int, total: int) -> float:
    return round(100 * n / total, 1) if total else 0.0


def _longest_streak(commits: list[Commit]) -> int:
    days = sorted({c.when.date() for c in commits})
    best = run = 1 if days else 0
    for a, b in pairwise(days):
        run = run + 1 if (b - a).days == 1 else 1
        best = max(best, run)
    return best


def compute_stats(commits: list[Commit], repo: str, author_filter: str | None = None) -> RepoStats:
    n = len(commits)
    by_hour = [0] * 24
    by_day = Counter()
    for c in commits:
        by_hour[c.when.hour] += 1
        by_day[c.when.weekday()] += 1

    subjects = [subject(c.message) for c in commits]
    repeated = Counter(s for s in subjects if s).most_common(1)
    gaps = [(b.when - a.when).total_seconds() / 86400 for a, b in pairwise(commits)]

    return RepoStats(
        repo=repo,
        author_filter=author_filter,
        total_commits=n,
        authors=len({c.email.lower() for c in commits}),
        first_commit=commits[0].when if commits else None,
        last_commit=commits[-1].when if commits else None,
        night_owl_pct=_pct(sum(by_hour[0:5]), n),
        weekend_pct=_pct(by_day[5] + by_day[6], n),
        friday_evening_commits=sum(1 for c in commits if c.when.weekday() == 4 and c.when.hour >= 17),
        busiest_hour=max(range(24), key=by_hour.__getitem__) if n else None,
        busiest_day=DAYS[by_day.most_common(1)[0][0]] if n else None,
        commits_by_hour=by_hour,
        lazy_message_pct=_pct(sum(is_lazy(c.message) for c in commits), n),
        median_message_length=float(median(len(s) for s in subjects)) if n else 0.0,
        shortest_messages=sorted(set(subjects), key=len)[:5],
        most_repeated_message=repeated[0][0] if repeated and repeated[0][1] > 1 else None,
        most_repeated_count=repeated[0][1] if repeated and repeated[0][1] > 1 else 0,
        final_mentions=sum(bool(FINAL_RE.search(s)) for s in subjects),
        reverts=sum(bool(REVERT_RE.search(s)) for s in subjects),
        shouty_commits=sum(is_shouty(s) for s in subjects),
        longest_gap_days=round(max(gaps), 1) if gaps else 0.0,
        longest_daily_streak=_longest_streak(commits),
        conventional_pct=_pct(sum(is_conventional(s) for s in subjects), n),
        almost_conventional=len(almost := [s for s in subjects if is_almost_conventional(s)]),
        almost_conventional_examples=almost[:3],
        apology_commits=sum(bool(APOLOGY_RE.search(s)) for s in subjects),
        novelist_commits=sum(len(s) > NOVEL_LENGTH for s in subjects),
    )


def worst_commits(commits: list[Commit], limit: int = 10) -> list[WorstCommit]:
    """Rank commits by how much a reviewer would sigh at them."""
    scored = []
    for c in commits:
        s = subject(c.message)
        reasons = []
        if is_lazy(c.message):
            reasons.append("message says nothing")
        if len(s) <= 3:
            reasons.append(f"{len(s)}-character message")
        if 0 <= c.when.hour < 5:
            reasons.append(f"committed at {c.when:%H:%M}")
        if FINAL_RE.search(s):
            reasons.append("claims to be final")
        if is_shouty(s):
            reasons.append("shouting")
        if REVERT_RE.search(s):
            reasons.append("a revert")
        if c.when.weekday() == 4 and c.when.hour >= 17:
            reasons.append("Friday evening")
        if is_almost_conventional(s):
            reasons.append("almost a Conventional Commit")
        if APOLOGY_RE.search(s):
            reasons.append("apologizing to git")
        if len(s) > NOVEL_LENGTH:
            reasons.append(f"{len(s)}-character subject line")
        if reasons:
            scored.append((len(reasons), c.when, WorstCommit(sha=c.sha[:7], when=c.when, message=s, reasons=reasons)))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [w for _, _, w in scored[:limit]]
