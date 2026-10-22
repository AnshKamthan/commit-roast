# LEARNING.md

One entry per commit: what changed, the idea behind it, where to look, and one small thing to try. Read them in order; each one builds on the last.

---

## 0. The first version: CLI + MCP server

**What it does.** `history.py` runs `git log`, parses it, and computes stats. `roasts.py` turns stats into jokes with plain `if` thresholds. `server.py` exposes the same stats over MCP. `cli.py` glues it together.

**Concepts**

- **Parsing `git log` safely.** Commit messages can contain anything: newlines, tabs, `|`, quotes. So the format string separates fields with `\x1f` (ASCII *unit separator*) and records with `\x1e` (*record separator*). These control characters exist for exactly this and basically never show up in real text. That's sturdier than splitting on `|` and praying.
- **`%aI` vs `%cI`.** Git stores two timestamps: *author* date (when the change was written) and *committer* date (when it was applied, e.g. after a rebase). We use author date, in strict ISO format, and keep its timezone offset. That's why a 2am commit from Bengaluru shows as 2am rather than 8:30pm UTC.
- **MCP tools vs prompts.** A *tool* is a function the model can call (`commit_stats`). A *prompt* is a reusable instruction template the user picks (`roast`). The server never writes jokes. It hands over facts, and the model does the comedy. That keeps the server deterministic and testable.
- **Testing against git without a real repo.** The test fixture builds a throwaway repo and fakes the timestamps with `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE`. Real `git`, fully controlled history.

**Where to look:** `read_commits()` in `history.py`, the `repo` fixture in `tests/test_roast.py`.

**Try this:** run `git log -3 --format='%an|%aI|%s'` in any repo, then the same with `%cI`. Find a rebased commit where they differ.

---

## 1. "Why this exists" + this file

No code, just honesty about what the project is. A README that says *why* is a better signal than one that pretends a weekend toy is enterprise software.

---

## 2. Friendlier errors + `--since` / `--until`

**What changed.** A missing folder now says `no such directory`, a non-repo says `isn't a git repo`, and an empty repo is "zero commits" rather than a crash. You can roast a time window: `commit-roast . --since "3 months ago"`.

**Concepts**

- **Translate errors at the boundary.** `git` speaks in `fatal: cannot change to ...`. The user shouldn't have to. `read_commits()` is the one place that talks to git, so it's the one place that turns git's errors into ours (`GitError`). Everything above it gets one clean exception type.
- **Locale is part of your input.** We match on git's English error text. On a machine with a non-English locale, git would translate those messages and the checks would silently fail. So the subprocess runs with `LC_ALL=C`. If you ever parse another program's output, pin its locale.
- **The bare-date gotcha (found while writing the tests).** `git log --since=2026-01-07` does **not** mean midnight. Git fills in the *current time of day*, so at 7:27pm it means "Jan 7, 7:27pm" and quietly drops anything earlier that day. No error, just wrong results. `_day_bound()` pins bare `YYYY-MM-DD` dates to `00:00:00` (since) / `23:59:59` (until). Relative dates like "3 months ago" pass through untouched.
- **Write the test you think is obvious.** The date bug only surfaced because a "trivially correct" test failed. That's the whole argument for testing boring code.

**Where to look:** `read_commits()` and `_day_bound()` in `history.py`, `test_since_and_until` and `test_bare_until_date_includes_the_whole_day`.

**Try this:** in any repo, compare `git log --since=YESTERDAY_DATE --oneline | wc -l` with `git log --since="YESTERDAY_DATE 00:00" --oneline | wc -l` (put in yesterday's real date) in the evening. Watch the numbers differ.

---

## 3. New crimes: almost-conventional, apologies, novelists

**What changed.** Three new signals:
- **Almost-conventional**: `feature: x`, `fixed: y`, `fix : z`, `feat(api) no colon`. People clearly *trying* to follow [Conventional Commits](https://www.conventionalcommits.org) and missing.
- **Apologies**: `oops`, `typo`, `forgot`, `sorry`, `actually`.
- **Novelists**: subject lines over 72 characters.

**Concepts**

- **Conventional Commits** is a tiny spec: `type(scope)!: description`, where `type` is one of a fixed set (`feat`, `fix`, `docs`, `chore`, …). Tools like semantic-release read it to auto-generate changelogs and bump versions: `feat` → minor, `fix` → patch, `!` → major. That's why teams care, not aesthetics.
- **Types are case-insensitive** per the spec, so `Docs: typo` is valid. Read specs before writing validators; the "obvious" rule is often wrong.
- **Defining "almost" is the hard part.** A naive "starts with fix" rule would flag `Fix off-by-one in allocator`, which is a perfectly good imperative message. So "almost" requires a signal of *intent*: a separator (`:`, `-`), a scope in parens, or a non-standard type word next to punctuation. The negative tests (`test_plain_messages_are_not_almost_conventional`) matter as much as the positive ones. They pin down what you *don't* want to catch.
- **Why 72 characters?** Git's tools (and GitHub's UI) truncate or wrap around there, and `git log --oneline` gets unreadable past it. The convention: a short subject, a blank line, then as much detail as you like in the body.

**Where to look:** `CONVENTIONAL_RE`, `ALMOST_CONVENTIONAL_RE`, `is_almost_conventional()` in `history.py`. The parametrized tests at the bottom of `tests/test_roast.py`.

**Try this:** paste `ALMOST_CONVENTIONAL_RE` into regex101.com (Python flavor) and find a message that's *almost* conventional but slips through. Then add it as a test case.
