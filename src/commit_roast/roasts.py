"""Offline roasts: no LLM, just thresholds and a bit of attitude."""

from __future__ import annotations

from .history import RepoStats, WorstCommit


def _hour(h: int) -> str:
    return f"{h % 12 or 12}{'am' if h < 12 else 'pm'}"


def roast_lines(s: RepoStats) -> list[str]:
    if s.total_commits == 0:
        return ["Zero commits. Can't roast what doesn't exist. Bold strategy."]

    lines: list[str] = []
    if s.night_owl_pct >= 20:
        lines.append(
            f"{s.night_owl_pct}% of commits between midnight and 5am. Your code has seen more sunrises than you have."
        )
    elif s.night_owl_pct >= 5:
        lines.append(f"{s.night_owl_pct}% of commits after midnight. Not a night owl, just bad at stopping.")

    if s.lazy_message_pct >= 30:
        lines.append(f"{s.lazy_message_pct}% of your messages are basically 'fix'. Fix what? Nobody will ever know.")
    elif s.lazy_message_pct >= 10:
        lines.append(
            f"{s.lazy_message_pct}% of messages are 'update' / 'wip' tier. Future you is going to be so confused."
        )

    if s.most_repeated_message and s.most_repeated_count >= 3:
        lines.append(
            f'You wrote "{s.most_repeated_message}" {s.most_repeated_count} times. At some point that\'s a mantra.'
        )

    if s.final_mentions >= 2:
        lines.append(f"{s.final_mentions} commits say 'final'. Narrator: they were not final.")
    elif s.final_mentions == 1:
        lines.append("One commit says 'final'. Adorable.")

    if s.median_message_length < 15:
        lines.append(f"Median message length: {s.median_message_length:g} characters. Haiku has more context.")

    if s.weekend_pct >= 40:
        lines.append(f"{s.weekend_pct}% of commits on weekends. Touch grass (git add grass && git commit -m 'touched')")

    if s.friday_evening_commits >= 3:
        lines.append(f"{s.friday_evening_commits} commits on Friday evenings. You like to live dangerously.")

    if s.shouty_commits >= 2:
        lines.append(f"{s.shouty_commits} messages in ALL CAPS. The code can't hear you, but it can feel your pain.")

    if s.reverts >= 3:
        lines.append(f"{s.reverts} reverts. Ctrl+Z with extra steps.")

    if s.longest_gap_days >= 60:
        lines.append(f"Longest silence: {s.longest_gap_days:g} days. The repo thought you died.")

    if s.longest_daily_streak >= 7:
        lines.append(f"{s.longest_daily_streak}-day commit streak. Respect. Also, are you okay?")

    if s.busiest_hour is not None and not lines:
        lines.append(
            f"Peak hour {_hour(s.busiest_hour)}, decent messages, sane schedule. Suspiciously well-adjusted. What are you hiding?"
        )
    return lines


def roast_card(s: RepoStats, worst: list[WorstCommit]) -> str:
    who = f" ({s.author_filter})" if s.author_filter else ""
    out = [f"🔥 commit-roast: {s.repo}{who}", ""]
    if s.total_commits:
        span = f"{s.first_commit:%b %Y} → {s.last_commit:%b %Y}"
        out.append(f"{s.total_commits} commits · {s.authors} author(s) · {span}")
        out.append(f"busiest day: {s.busiest_day} · busiest hour: {_hour(s.busiest_hour)}")
        out.append("")
        out.append(_sparkline(s.commits_by_hour))
        out.append("12am  6am   12pm  6pm")
        out.append("")
    out += [f"• {line}" for line in roast_lines(s)]
    if worst:
        out += ["", "Hall of shame:"]
        for w in worst[:5]:
            out.append(f"  {w.sha}  {w.message[:50]!r}  ({', '.join(w.reasons)})")
    return "\n".join(out)


def _sparkline(buckets: list[int]) -> str:
    bars = " ▁▂▃▄▅▆▇█"
    top = max(buckets) or 1
    return "".join(bars[round(b / top * 8)] for b in buckets)
