"""Offline roasts: no LLM, just thresholds, a table of jokes, and a seeded die."""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Literal

from .history import RepoStats, WorstCommit

Spice = Literal["gentle", "medium", "brutal"]
BattleReason = Literal["numbers", "forfeit", "no-contest", "tie"]
SPICES: tuple[Spice, ...] = ("gentle", "medium", "brutal")


def _hour(h: int) -> str:
    return f"{h % 12 or 12}{'am' if h < 12 else 'pm'}"


# (when it applies, {spice: [templates]}). Order here is the order lines appear.
# Templates are str.format strings over the stats fields plus `ex` (an example message) and `hour`.
Roast = tuple[Callable[[RepoStats], bool], dict[Spice, list[str]]]
ROASTS: list[Roast] = [
    (
        lambda s: s.night_owl_pct >= 20,
        {
            "gentle": ["{night_owl_pct}% of commits between midnight and 5am. Please sleep. The bugs will wait."],
            "medium": [
                "{night_owl_pct}% of commits between midnight and 5am. Your code has seen more sunrises than you have.",
                "{night_owl_pct}% of commits between midnight and 5am. Not a developer, a nocturnal animal with a laptop.",
            ],
            "brutal": [
                (
                    "{night_owl_pct}% of commits between midnight and 5am. Nothing good was ever committed at 3am, "
                    "and your history is the proof."
                ),
                "{night_owl_pct}% of commits after midnight. Your sleep schedule has merge conflicts.",
            ],
        },
    ),
    (
        lambda s: 5 <= s.night_owl_pct < 20,
        {
            "gentle": ["{night_owl_pct}% of commits after midnight. A little late-night coding never hurt. Mostly."],
            "medium": ["{night_owl_pct}% of commits after midnight. Not a night owl, just bad at stopping."],
            "brutal": ["{night_owl_pct}% of commits after midnight. 'Just one more commit,' you said. Lying."],
        },
    ),
    (
        lambda s: s.lazy_message_pct >= 30,
        {
            "gentle": [
                "{lazy_message_pct}% of messages are one-word wonders like 'fix'. Future you would love a hint."
            ],
            "medium": [
                "{lazy_message_pct}% of your messages are basically 'fix'. Fix what? Nobody will ever know.",
                "{lazy_message_pct}% of your messages are 'fix'. git blame is going to read like a mystery novel.",
            ],
            "brutal": [
                "{lazy_message_pct}% of your messages are 'fix'. This isn't a commit history, it's a ransom note.",
                "{lazy_message_pct}% of your messages are 'fix'. You write commit messages like you're paying per letter.",
            ],
        },
    ),
    (
        lambda s: 10 <= s.lazy_message_pct < 30,
        {
            "gentle": ["{lazy_message_pct}% of messages are 'update' / 'wip' tier. Room to grow!"],
            "medium": [
                "{lazy_message_pct}% of messages are 'update' / 'wip' tier. Future you is going to be so confused."
            ],
            "brutal": [
                "{lazy_message_pct}% of messages are 'update' / 'wip'. Updated what? WIP on what? Unbelievable."
            ],
        },
    ),
    (
        lambda s: s.most_repeated_count >= 3,
        {
            "gentle": [
                'You wrote "{most_repeated_message}" {most_repeated_count} times. Consistency is a virtue, technically.'
            ],
            "medium": [
                'You wrote "{most_repeated_message}" {most_repeated_count} times. At some point that\'s a mantra.'
            ],
            "brutal": [
                '"{most_repeated_message}" × {most_repeated_count}. Copy-paste isn\'t just for code, apparently.'
            ],
        },
    ),
    (
        lambda s: s.final_mentions >= 2,
        {
            "gentle": ["{final_mentions} commits say 'final'. Optimism is important."],
            "medium": ["{final_mentions} commits say 'final'. Narrator: they were not final."],
            "brutal": ["{final_mentions} commits called 'final'. The word has lost all meaning, and you did that."],
        },
    ),
    (
        lambda s: s.final_mentions == 1,
        {
            "gentle": ["One commit says 'final'. Cute."],
            "medium": ["One commit says 'final'. Adorable."],
            "brutal": ["One commit says 'final'. Sure it was."],
        },
    ),
    (
        lambda s: s.median_message_length < 15,
        {
            "gentle": ["Median message length: {median_message_length:g} characters. Brief! Maybe a little too brief."],
            "medium": ["Median message length: {median_message_length:g} characters. Haiku has more context."],
            "brutal": [
                "Median message length: {median_message_length:g} characters. Error codes have more context than this."
            ],
        },
    ),
    (
        lambda s: s.weekend_pct >= 40,
        {
            "gentle": ["{weekend_pct}% of commits on weekends. Weekends are for rest, allegedly."],
            "medium": ["{weekend_pct}% of commits on weekends. Touch grass (git add grass && git commit -m 'touched')"],
            "brutal": ["{weekend_pct}% of commits on weekends. The repo has seen you more than your friends have."],
        },
    ),
    (
        lambda s: s.friday_evening_commits >= 3,
        {
            "gentle": ["{friday_evening_commits} commits on Friday evenings. Brave."],
            "medium": ["{friday_evening_commits} commits on Friday evenings. You like to live dangerously."],
            "brutal": [
                "{friday_evening_commits} Friday-evening commits. Somewhere, an on-call engineer just felt a chill."
            ],
        },
    ),
    (
        lambda s: s.shouty_commits >= 2,
        {
            "gentle": ["{shouty_commits} messages in ALL CAPS. Deep breaths."],
            "medium": ["{shouty_commits} messages in ALL CAPS. The code can't hear you, but it can feel your pain."],
            "brutal": ["{shouty_commits} ALL CAPS commits. Commit messages, not hostage demands."],
        },
    ),
    (
        lambda s: s.reverts >= 3,
        {
            "gentle": ["{reverts} reverts. Changing your mind is healthy."],
            "medium": ["{reverts} reverts. Ctrl+Z with extra steps."],
            "brutal": ["{reverts} reverts. Your git history has commitment issues. In a version control system."],
        },
    ),
    (
        lambda s: s.longest_gap_days >= 60,
        {
            "gentle": ["Longest break: {longest_gap_days:g} days. Hope it was a nice vacation."],
            "medium": ["Longest silence: {longest_gap_days:g} days. The repo thought you died."],
            "brutal": ["{longest_gap_days:g} days of silence. The repo filed a missing persons report."],
        },
    ),
    (
        lambda s: s.longest_daily_streak >= 7,
        {
            "gentle": ["{longest_daily_streak}-day commit streak. Respect."],
            "medium": ["{longest_daily_streak}-day commit streak. Respect. Also, are you okay?"],
            "brutal": ["{longest_daily_streak} days in a row. Blink twice if the repo is holding you hostage."],
        },
    ),
    (
        lambda s: s.almost_conventional >= 2,
        {
            "gentle": ['{almost_conventional} commits *almost* follow Conventional Commits ("{ex}"). Nearly there!'],
            "medium": [
                (
                    '{almost_conventional} commits *almost* follow Conventional Commits ("{ex}"). '
                    "So close. The spec is one page long."
                )
            ],
            "brutal": [
                '{almost_conventional} commits like "{ex}". You know the convention exists. You chose violence.'
            ],
        },
    ),
    (
        lambda s: s.almost_conventional < 2 and s.conventional_pct >= 80,
        {
            "gentle": ["{conventional_pct}% Conventional Commits. Lovely."],
            "medium": ["{conventional_pct}% Conventional Commits. Disciplined. Slightly scary."],
            "brutal": ["{conventional_pct}% Conventional Commits. Does your linter let you go home at night?"],
        },
    ),
    (
        lambda s: s.apology_commits >= 2,
        {
            "gentle": ["{apology_commits} commits say oops / typo / forgot. Happens to everyone."],
            "medium": ["{apology_commits} commits apologize (oops / typo / forgot). Git is not your therapist."],
            "brutal": ["{apology_commits} apology commits. Git doesn't forgive. Git remembers. Forever."],
        },
    ),
    (
        lambda s: s.novelist_commits >= 3,
        {
            "gentle": ["{novelist_commits} subject lines over 72 characters. The commit body would love to help."],
            "medium": [
                (
                    "{novelist_commits} subject lines over 72 characters. That's not a subject line, "
                    "that's a short story. The commit body exists."
                )
            ],
            "brutal": ["{novelist_commits} subject lines over 72 characters. git log --oneline is in tears."],
        },
    ),
]

CLEAN: dict[Spice, list[str]] = {
    "gentle": ["Clean history, sane hours, real messages. Genuinely nice work."],
    "medium": ["Peak hour {hour}, decent messages, sane schedule. Suspiciously well-adjusted. What are you hiding?"],
    "brutal": ["No crimes found. Either you're very good, or you squash everything. We both know which."],
}


def roast_lines(s: RepoStats, spice: Spice = "medium", seed: int | str | None = None) -> list[str]:
    """Pick one joke per crime. Same stats + same seed always gives the same roast."""
    if s.total_commits == 0:
        return ["Zero commits. Can't roast what doesn't exist. Bold strategy."]

    # A str seed is hashed deterministically by `random` (unlike hash(), which changes every run).
    rng = random.Random(seed if seed is not None else f"{s.repo}:{s.total_commits}")
    ctx = {
        **s.model_dump(),
        "ex": (s.almost_conventional_examples or [""])[0],
        "hour": _hour(s.busiest_hour or 0),
    }
    lines = [rng.choice(templates[spice]).format(**ctx) for applies, templates in ROASTS if applies(s)]
    return lines or [rng.choice(CLEAN[spice]).format(**ctx)]


def roast_card(s: RepoStats, worst: list[WorstCommit], spice: Spice = "medium", seed: int | str | None = None) -> str:
    who = f" ({s.author_filter})" if s.author_filter else ""
    flame = {"gentle": "🕯️", "medium": "🔥", "brutal": "🌋"}[spice]
    out = [f"{flame} commit-roast: {s.repo}{who}", ""]
    if s.total_commits:
        span = f"{s.first_commit:%b %Y} → {s.last_commit:%b %Y}"
        out.append(f"{s.total_commits} commits · {s.authors} author(s) · {span}")
        out.append(f"busiest day: {s.busiest_day} · busiest hour: {_hour(s.busiest_hour)}")
        out.append("")
        out.append(_sparkline(s.commits_by_hour))
        out.append("12am  6am   12pm  6pm")
        out.append("")
    out += [f"• {line}" for line in roast_lines(s, spice, seed)]
    if worst:
        out += ["", "Hall of shame:"]
        for w in worst[:5]:
            out.append(f"  {w.sha}  {w.message[:50]!r}  ({', '.join(w.reasons)})")
    return "\n".join(out)


def _sparkline(buckets: list[int]) -> str:
    bars = " ▁▂▃▄▅▆▇█"
    top = max(buckets) or 1
    return "".join(bars[round(b / top * 8)] for b in buckets)


# Roast battle: `--vs alice bob`. Crime score is night-owl % + lazy-message %; higher score loses.
# Fewer than MIN_BATTLE_COMMITS is a forfeit: one 2am commit is 100% night owl, and that's not evidence.
# Templates are str.format strings over the loser's stats fields plus `loser` and `winner` (author names)
# and `commits` ("1 commit", "3 commits").
MIN_BATTLE_COMMITS = 5
BATTLE: dict[Spice, list[str]] = {
    "gentle": [
        "{loser} loses, but gently. {lazy_message_pct}% lazy messages is a habit, not a personality. Yet.",
        "{winner} takes it. {loser}, {night_owl_pct}% of your commits were after midnight. Go to bed, friend.",
    ],
    "medium": [
        "{loser} loses. {lazy_message_pct}% lazy messages. {winner} didn't even have to try.",
        "{loser} loses. {night_owl_pct}% after midnight and it still wasn't enough to beat {winner}.",
    ],
    "brutal": [
        "{loser} loses. {lazy_message_pct}% lazy messages. {winner} should invoice you for code review.",
        "{loser} loses. {night_owl_pct}% of commits after midnight. {winner} was asleep and still won.",
    ],
}
# One side has fewer than MIN_BATTLE_COMMITS. `loser` is the one who barely showed up.
BATTLE_FORFEIT: dict[Spice, list[str]] = {
    "gentle": ["{loser} has {commits}. Not enough to judge, so {winner} wins by forfeit."],
    "medium": [
        "{loser} has {commits}. That's not a record, that's an alibi. {winner} wins by forfeit.",
        "{loser} barely showed up ({commits}). {winner} wins by forfeit, which still counts.",
    ],
    "brutal": ["{loser} has {commits}. Can't lose a roast battle if you never write code. Loses anyway."],
}
# Both sides have fewer than MIN_BATTLE_COMMITS (but not both zero).
BATTLE_NO_CONTEST: dict[Spice, list[str]] = {
    "gentle": ["{winner} and {loser} don't have enough commits between them to call it. Come back later."],
    "medium": ["{winner} and {loser}: not enough commits for a verdict. A roast battle needs evidence."],
    "brutal": ["{winner} and {loser} brought a handful of commits to a roast battle. No contest. Both lose."],
}
BATTLE_TIE: dict[Spice, list[str]] = {
    "gentle": ["{winner} and {loser} are perfectly tied. Friendship wins."],
    "medium": ["{winner} and {loser} are dead even. Equally guilty. Pair-program your way out of it."],
    "brutal": ["{winner} and {loser} are tied. Not a battle, a matching set of bad habits."],
}


def crime_score(s: RepoStats) -> float:
    return s.night_owl_pct + s.lazy_message_pct


def battle_loser(a: RepoStats, b: RepoStats) -> RepoStats | None:
    """Who loses the roast battle. Too few commits loses by forfeit; None means a tie or no contest."""
    small_a, small_b = a.total_commits < MIN_BATTLE_COMMITS, b.total_commits < MIN_BATTLE_COMMITS
    if small_a != small_b:
        return a if small_a else b
    if small_a or crime_score(a) == crime_score(b):
        return None
    return a if crime_score(a) > crime_score(b) else b


def battle_reason(a: RepoStats, b: RepoStats) -> BattleReason:
    """Why battle_loser() decided what it did."""
    loser = battle_loser(a, b)
    if loser is None:
        return "no-contest" if a.total_commits < MIN_BATTLE_COMMITS else "tie"
    return "forfeit" if loser.total_commits < MIN_BATTLE_COMMITS else "numbers"


def battle_line(a: RepoStats, b: RepoStats, spice: Spice = "medium", seed: int | str | None = None) -> str:
    """The verdict joke. Same stats + same seed always gives the same line."""
    rng = random.Random(seed if seed is not None else f"{a.repo}:{a.total_commits}:{b.total_commits}")
    if not a.total_commits and not b.total_commits:
        return "Zero commits from both of you. A roast battle between nobodies. Bold strategy."
    loser = battle_loser(a, b) or b
    winner = b if loser is a else a
    table = {"numbers": BATTLE, "forfeit": BATTLE_FORFEIT, "no-contest": BATTLE_NO_CONTEST, "tie": BATTLE_TIE}[
        battle_reason(a, b)
    ]
    n = loser.total_commits
    return rng.choice(table[spice]).format(
        **loser.model_dump(),
        loser=loser.author_filter,
        winner=winner.author_filter,
        commits=f"{n} commit{'' if n == 1 else 's'}",
    )


def battle_card(
    a: RepoStats,
    b: RepoStats,
    worst_a: list[WorstCommit],
    worst_b: list[WorstCommit],
    spice: Spice = "medium",
    seed: int | str | None = None,
) -> str:
    def worst(ws: list[WorstCommit]) -> str:
        if not ws:
            return "(none)"
        msg = ws[0].message
        return f"{ws[0].sha} '{msg[:20]}…'" if len(msg) > 20 else f"{ws[0].sha} {msg!r}"

    flame = {"gentle": "🕯️", "medium": "🔥", "brutal": "🌋"}[spice]
    rows = [
        ("", a.author_filter or "", b.author_filter or ""),
        ("commits", str(a.total_commits), str(b.total_commits)),
        ("night owl", f"{a.night_owl_pct}%", f"{b.night_owl_pct}%"),
        ("lazy messages", f"{a.lazy_message_pct}%", f"{b.lazy_message_pct}%"),
        ("worst commit", worst(worst_a), worst(worst_b)),
    ]
    w0, w1, w2 = (max(len(r[i]) for r in rows) for i in range(3))
    out = [f"{flame} roast battle: {a.repo}", ""]
    out += [f"{label:<{w0}}  {x:<{w1}}  {y:<{w2}}".rstrip() for label, x, y in rows]
    loser = battle_loser(a, b)
    verdict = (
        loser.author_filter
        if loser
        else {"no-contest": "nobody (not enough commits)", "tie": "nobody (tie)"}[battle_reason(a, b)]
    )
    out += ["", f"loser: {verdict}"]
    out.append(f"• {battle_line(a, b, spice, seed)}")
    return "\n".join(out)
