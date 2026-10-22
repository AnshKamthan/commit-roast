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
