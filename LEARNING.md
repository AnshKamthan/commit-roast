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

---

## 4. Spice levels: `--spice gentle | medium | brutal`

**What changed.** Every roast now has gentle, medium and brutal versions, some with several variants. `--seed` picks a different set of jokes. 🕯️ / 🔥 / 🌋 in the header tells you which mode you're in.

**Concepts**

- **Data over code.** Before, every joke was an `if` + `append`. Now `ROASTS` is a *table*: (condition, {spice: [templates]}). Adding a joke means adding data, not logic, and a test can loop over the whole table (`test_every_template_formats`) to check that every template renders for every spice. You couldn't do that with 40 hand-written `if`s.
- **Deterministic randomness.** Randomness and tests don't mix unless you control the seed. `random.Random(seed)` gives an isolated generator: same seed, same jokes, every run, every machine. With no `--seed`, we seed from `"{repo}:{total_commits}"`, so a repo gets a stable roast until you commit more. Gotcha: Python's built-in `hash()` of a string changes on every run (hash randomization, a security feature), but `random.Random("some string")` is stable, because `random` hashes strings with SHA-512 internally.
- **The missing-comma bug (this really happened while writing this commit).** In Python, `["a" "b"]` is *one* string, `"ab"`, because adjacent string literals get glued together silently. A dropped comma in the joke table merged two jokes into one long line. No error, no crash. Ruff's `ISC004` rule flagged it ("implicit string concatenation in a collection"), and `test_no_template_swallowed_another` now guards it: two glued jokes each repeat their number placeholder, so a template with a duplicate `{field}` fails. The test was checked by deliberately dropping a comma and watching it fail.
- **When you *want* concatenation**, wrap it in parentheses so it's obviously intentional: `("long joke part one " "part two")`.

**Where to look:** `ROASTS`, `roast_lines()` in `roasts.py`. `test_every_template_formats`, `test_no_template_swallowed_another`.

**Try this:** add a brutal joke for `reverts`, run `commit-roast . --spice brutal --seed 1` and `--seed 2` until you see it. Then delete one comma in the table and run `uv run pytest`.

---

## 5. MCP resources: the third primitive

**What changed.** The server now exposes two **resources**:
- `commit-roast://signals`: a markdown table defining every stat.
- `commit-roast://jokes/{spice}`: the offline joke templates for a spice level, as a style guide for the model.

The `roast` prompt points the model at both.

**Concepts**

- **The three MCP primitives and who's in charge of each.**
  - **Tools** are *model-controlled*: the model decides to call `commit_stats`. They *do* something (run git) and take arguments.
  - **Resources** are *application-controlled*: data the client can list, read, and attach as context. Think "files the model can be shown", addressed by URI. No side effects.
  - **Prompts** are *user-controlled*: templates the user picks from a menu (`/roast` in some clients).

  The question for any new feature: who should decide when it's used? The model (tool), the app or user attaching context (resource), or the user starting a workflow (prompt)?
- **Static vs templated resources.** `commit-roast://signals` is one fixed URI and shows up in `list_resources()`. `commit-roast://jokes/{spice}` is a *template*, which shows up in `list_resource_templates()`, and the client fills in `{spice}`. Same idea as a REST route with a path parameter.
- **Docs that can't drift.** `test_signals_resource_documents_every_stat` walks `RepoStats.model_fields` and fails if a stat isn't explained in the resource. Add a field and forget the docs, and CI goes red. Cheap trick, very effective.

**Where to look:** `signals()`, `jokes()`, `SIGNALS_MD` in `server.py`. `test_mcp_resources` in the tests.

**Try this:** run `npx @modelcontextprotocol/inspector commit-roast serve` (the official MCP Inspector) and click through Tools, Resources and Prompts. That is exactly what any MCP client sees.

---

## 6. Roast battle: `--vs alice bob`

**What changed.** `commit-roast . --vs alice bob` puts two authors side by side (commits, night-owl %, lazy-message %, worst commit) and names a loser, with a joke at the current `--spice`. Authors are matched exactly like `--author`.

**Concepts**

- **Reuse the pipeline, don't fork it.** A battle is just the normal pipeline run twice: `read_commits(path, author)` → `compute_stats` → `worst_commits`, once per side. No new git code, no new stats. The only new logic is `battle_loser()` (higher night-owl % + lazy % loses) and a table of verdict jokes.
- **Edge cases are part of the rules.** What if it's a dead tie? Those get their own small tables (`BATTLE_FORFEIT`, `BATTLE_NO_CONTEST`, `BATTLE_TIE`) rather than `if`s buried inside a joke, so the same "every template formats" test covers them too.
- **Sample size matters, even in a joke.** One commit at 2am is "100% night owl". Percentages over tiny samples are noise, so below `MIN_BATTLE_COMMITS` (5) there's no verdict on the numbers: the small side forfeits, and if both are small it's no contest.
- **git defaults to case-sensitive, so we pass `-i`.** Git matches `--author` as a case-sensitive regex against `Name <email>`, so `--author ANSH` found nothing when the commits said `ansh` (found while writing the tests). `read_commits()` adds `--regexp-ignore-case` whenever an author is set, so `--author` and `--vs` both get it.
- **Flags that contradict each other should fail loudly.** `--vs` with `--author` has no sensible meaning, so `p.error()` rejects it with a message instead of quietly picking one.

**Where to look:** `battle_loser()`, `battle_card()`, `BATTLE`, `MIN_BATTLE_COMMITS` in `roasts.py`, `read_commits()` in `history.py`, `battle()` in `cli.py`, the `test_*battle*` tests.

**Try this:** run `commit-roast . --vs you a-coworker --json` on a shared repo, then change `crime_score()` to also count `final_mentions` and see whether the loser changes.


---

## 7. Roast battles over MCP

**What changed.** The server has a `roast_battle` tool (both authors' stats, their crime scores, the loser, and a `reason`: `numbers`, `forfeit`, `no-contest` or `tie`) and a `battle` prompt that tells the model to call it and roast at a given intensity. `commit-roast://signals` now explains crime scores and every verdict reason.

**Concepts**

- **The server decides, the model performs.** The verdict comes from the same `battle_loser()` the CLI uses, and the prompt tells the model to announce that loser rather than pick its own. Otherwise ask twice and you might get two different losers. Deterministic rules on the server, comedy in the model: same split as #0.
- **Return the *why*, not just the *what*.** A bare `loser: "dhruv"` invites the model to invent a reason ("dhruv's messages are terrible!") when the real one is "dhruv has 1 commit". `reason` plus the crime scores give it the true story to tell. Structured output is also a way of steering what the model says.
- **One source of truth for the rules.** `battle_reason()` lives next to `battle_loser()` in `roasts.py`, and both the CLI card and the MCP tool use it. The `BattleReason` `Literal` becomes an enum in the tool's output schema, so clients know the four possible values up front.
- **Docs that can't drift, again.** `test_signals_resource_documents_every_battle_reason` loops over `get_args(BattleReason)`. Add a fifth reason and forget the docs, and CI goes red, same trick as in #5.

**Where to look:** `roast_battle()`, `RoastBattle`, `battle()` in `server.py`, `battle_reason()` in `roasts.py`, `test_mcp_roast_battle`.

**Try this:** in the MCP Inspector (`npx @modelcontextprotocol/inspector commit-roast serve`), call `roast_battle` on a repo of yours and look at the output schema: `reason` shows up as an enum of four strings.


---

## 8. `--format markdown`: roasts that paste into GitHub

**What changed.** `--format markdown` prints a GitHub-friendly version of the roast card and the battle card: a heading, a stats table, bullet roasts, and the hall of shame as a table with SHAs in backticks. `--format text` (the default) is unchanged. Works with `--vs` too.

**Concepts**

- **Same data, second renderer.** The stats, jokes and verdict don't change at all. `roast_card_markdown()` and `battle_card_markdown()` take exactly the same arguments as the text versions, and the CLI just picks one. Keeping "what to say" (`roast_lines`, `battle_line`, `_verdict`) apart from "how to lay it out" is what makes a second format cheap.
- **Commit messages are untrusted input.** Anyone can write a commit message, and markdown will happily render it. `fix @dhruv's bug` would ping dhruv, `<details>` would swallow half the comment, and `a | b` would add a column to the table. So in tables, messages go inside code spans (no markup, no mentions), and in roast lines markup characters get a backslash (`_md()`). One gap left on purpose: `_md()` doesn't touch `@`, so a roast line quoting a repeated `@someone` message could still ping them.
- **The pipe gotcha.** In a GitHub table, `|` ends the cell *even inside backticks*. You have to write `\\|`, which GitHub renders as a plain `|`. A message containing a backtick needs a longer fence: ``` `` use `x` `` ```.
- **Test the shape, not just the strings.** `_assert_tables_are_well_formed` counts the unescaped pipes in every table row and checks they match the header. That catches every way a hostile message could break a table, not just the ones I thought of.

**Where to look:** `roast_card_markdown()`, `battle_card_markdown()`, `_md()`, `_md_code()` in `roasts.py`, `test_markdown_survives_hostile_commit_messages`.

**Try this:** run `commit-roast . --format markdown | pbcopy` (macOS) and paste it into a GitHub comment's Preview tab. Then make a commit with a `|` in its message and paste again.
\n

---

## 9. A GitHub Action that roasts every PR

**What changed.** `action.yml` at the repo root makes commit-roast a reusable GitHub Action: `uses: AnshKamthan/commit-roast@main` posts a markdown roast of a PR's commits as a comment. `.github/workflows/roast-pr.yml` runs it on this repo's own PRs.

**Concepts**

- **Composite actions.** There are three kinds of action: JavaScript, Docker, and *composite*, which is just a list of steps, like a mini workflow you can `uses:`. Ours is `using: composite`. Gotchas: every `run:` step must say `shell: bash` (there's no default), a step can `uses:` other actions (we pull in `setup-uv`), and `$GITHUB_ACTION_PATH` points at the action's own files. That's how it runs *this* commit-roast, not whatever is on PyPI.
- **PR events check out a commit that doesn't exist in your branch.** On `pull_request`, `actions/checkout` checks out `refs/pull/N/merge`, a test merge of the PR into its base. Walk back from there and you also reach every newer commit on `main`, so the roast would blame the PR author for other people's commits. The action reads `pull_request.base.sha` and `head.sha` from the event and roasts a `git worktree` at the real head, which leaves the user's checkout alone. Checking out with the default `fetch-depth: 1` gives you a single commit, so `git merge-base` can't find where the branch started. Hence `fetch-depth: 0` in the example.
- **`--since` is inclusive (found while testing this).** `--since <base commit's time>` also includes the base commit itself, which isn't part of the PR. The action passes the base's timestamp plus one second, as `@<unix seconds>`, a format git accepts directly. It's a time filter, not a commit range, so it's approximate: if `main` was merged *into* the PR branch, those `main` commits are newer than the base and get roasted too.
- **`GITHUB_TOKEN` permissions.** Every run gets a short-lived token, and the `permissions:` block says what it may do. Ask for the least you need: `contents: read` to check out, `pull-requests: write` to comment. On PRs from *forks* the token is read-only no matter what you ask for, because otherwise anyone could open a PR that rewrites your workflow to abuse a write token. So the workflow skips fork PRs (`if: head.repo.full_name == github.repository`). The usual way around this, `pull_request_target`, runs with a write token *and* untrusted PR code. That's a well-known way to get a repo owned, so we don't use it.
- **Never paste `${{ }}` into a script.** `${{ inputs.spice }}` inside `run:` is pasted in as text *before* bash runs, so a crafted value becomes shell code. Pass it through `env:` and use `"$SPICE"`, and it's just a string.
- **uvx caches builds (found while testing this).** `uvx --from <path>` reused an old build of commit-roast, because uv decides when to rebuild a local project from `pyproject.toml`, and only `src/` had changed. The action uses `uv run --project "$GITHUB_ACTION_PATH"` instead, which installs the project in editable mode (always the current source) with dependencies from `uv.lock`.

**Where to look:** `action.yml`, `.github/workflows/roast-pr.yml`.

**Try this:** open a PR against this repo with a commit called `fix`. Then look at the run's "Set up job" log, which lists exactly which permissions the `GITHUB_TOKEN` got.

