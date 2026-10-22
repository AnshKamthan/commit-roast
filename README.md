# commit-roast 🔥

Your git log knows things. The 3am commits. The four `fix`es in a row. The commit called `final final` and the revert of it two hours later.

> **Why this exists:** I was bored at 12:30am, didn't want to study, and wanted to build something useless. It's a toy, built for fun, and an excuse to poke at how MCP servers, `git log`, and Python packaging actually work. Every commit has a matching entry in [LEARNING.md](LEARNING.md) with the concept behind it.

`commit-roast` digs through a repo's history and roasts it. It works two ways:

- **Offline CLI.** Rule-based roasts, no LLM, no network. Runs anywhere `git` does.
- **MCP server.** Exposes the evidence as tools so Claude (or any MCP client) can write a properly personal roast grounded in your actual commits.

```text
$ commit-roast ~/code/tachi-but-worse

🔥 commit-roast: tachi-but-worse

13 commits · 1 author(s) · Mar 2026 → May 2026
busiest day: Tuesday · busiest hour: 1am

 ███      ▄▄▄     ▄▄ ▄ ▄
12am  6am   12pm  6pm

• 46.2% of commits between midnight and 5am. Your code has seen more sunrises than you have.
• 53.8% of your messages are basically 'fix'. Fix what? Nobody will ever know.
• You wrote "fix" 4 times. At some point that's a mantra.
• 3 commits say 'final'. Narrator: they were not final.
• Median message length: 6 characters. Haiku has more context.
• 3 commits on Friday evenings. You like to live dangerously.
• Longest silence: 75.5 days. The repo thought you died.

Hall of shame:
  f4be034  'wip'  (message says nothing, 3-character message, committed at 01:10)
  b8b2645  'Revert "final final"'  (claims to be final, a revert, Friday evening)
  67484e3  'fix'  (message says nothing, 3-character message, committed at 03:41)
  ...
```

(Demo repo with a fabricated history. Any resemblance to real repos is entirely deserved.)

## Install

```bash
uv tool install git+https://github.com/AnshKamthan/commit-roast
# or
pipx install git+https://github.com/AnshKamthan/commit-roast
```

## CLI

```bash
commit-roast                      # roast the repo you're in
commit-roast path/to/repo         # roast another one
commit-roast . --author ansh      # roast one person (matches name or email)
commit-roast . --json             # raw stats, no jokes
```

## MCP server

`commit-roast serve` runs a stdio MCP server with:

| Kind | Name | What it does |
|---|---|---|
| tool | `commit_stats(repo_path, author?)` | Structured stats: night-owl %, lazy-message %, repeated messages, `final` claims, reverts, gaps, streaks, an hour histogram |
| tool | `worst_commits(repo_path, author?, limit?)` | The most roastable commits, each with the reasons it made the list |
| prompt | `roast(repo_path, author?, intensity?)` | Tells the model to use both tools and roast at `gentle` / `medium` / `brutal`, grounded in real SHAs and messages |

Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "commit-roast": {
      "command": "commit-roast",
      "args": ["serve"]
    }
  }
}
```

Then ask: *"Roast the commit history of ~/code/my-project, brutal mode."*

The split is deliberate. The server only hands over facts, and the model writes the jokes. That keeps the server deterministic and testable, and keeps the roast from being invented. The prompt makes the model cite a number or a SHA for every line.

## What counts as what

All times are the **author's own local time** (from the commit's timezone offset), so a 2am commit from Bengaluru is a 2am commit, not 8:30pm UTC.

| Signal | Definition |
|---|---|
| Night owl | Committed between 00:00 and 04:59 |
| Lazy message | Entire subject is filler: `fix`, `wip`, `update`, `changes`, `...`, `asdf`, `initial commit`, etc. `Fix off-by-one in allocator` is fine. |
| Shouting | Subject is ≥60% uppercase letters (min 6 letters), or contains `!!`. Acronyms in normal sentences (`Add HTTP check`) don't count. |
| Final | Subject contains the word `final` (reverts of finals included, on purpose) |
| Friday evening | Friday, 17:00 or later |
| Streak / gap | Consecutive calendar days with a commit / longest time between commits |

Merge commits are skipped. Only the subject line is judged. Your carefully written commit bodies are safe.

## Development

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Tests build a throwaway repo with backdated commits and check the stats, the CLI, and the MCP tools through an in-memory client.

## License

MIT
