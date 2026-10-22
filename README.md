# commit-roast 🔥

ok so it's 12:30am, i don't want to study, everything is boring, and i didn't want to watch netflix either. so i built a thing that reads your git history and makes fun of you.

it finds your 3am commits, your four `fix`es in a row, the commit called `final final` and the revert of it two hours later. then it roasts you about it. you get to pick how much it hurts.

is it useful? no. does it have tests? yes, 48 of them. priorities.

```text
$ commit-roast ~/code/tachi-but-worse --spice brutal

🌋 commit-roast: tachi-but-worse

13 commits · 1 author(s) · Mar 2026 → May 2026
busiest day: Tuesday · busiest hour: 1am

 ███      ▄▄▄     ▄▄ ▄ ▄
12am  6am   12pm  6pm

• 46.2% of commits after midnight. Your sleep schedule has merge conflicts.
• 53.8% of your messages are 'fix'. You write commit messages like you're paying per letter.
• "fix" × 4. Copy-paste isn't just for code, apparently.
• 3 commits called 'final'. The word has lost all meaning, and you did that.
• Median message length: 6 characters. Error codes have more context than this.
• 3 Friday-evening commits. Somewhere, an on-call engineer just felt a chill.
• 75.5 days of silence. The repo filed a missing persons report.

Hall of shame:
  f4be034  'wip'  (message says nothing, 3-character message, committed at 01:10)
  b8b2645  'Revert "final final"'  (claims to be final, a revert, Friday evening)
  67484e3  'fix'  (message says nothing, 3-character message, committed at 03:41)
```

(that repo is fake. any resemblance to my real repos is a coincidence. mostly.)

## install

```bash
uv tool install git+https://github.com/AnshKamthan/commit-roast
# or
pipx install git+https://github.com/AnshKamthan/commit-roast
```

## use it

```bash
commit-roast                            # roast the repo you're in
commit-roast path/to/repo               # roast someone else's (with permission. or not.)
commit-roast . --spice gentle           # 🕯️ gentle, 🔥 medium (default), 🌋 brutal
commit-roast . --seed 7                 # same crimes, different jokes
commit-roast . --since "3 months ago"   # only recent crimes (--until works too)
commit-roast . --author ansh            # roast one specific person
commit-roast . --json                   # just the numbers, no feelings involved
```

same repo + same seed = same roast, so the screenshot you post is the one everyone else gets.

## what counts as a crime

- **night owl**: committed between midnight and 5am (your local time, not UTC, i checked)
- **lazy message**: the whole message is `fix`, `wip`, `update`, `...` etc. `fix off-by-one in allocator` is fine, that's a real message
- **shouting**: mostly CAPS or has `!!`. `Add HTTP check` is not shouting, acronyms are innocent
- **final**: any commit with "final" in it. they never are
- **friday evening**: after 5pm on a friday. brave
- **almost conventional**: `feature:`, `fixed:`, `fix :`. you were so close to [conventional commits](https://www.conventionalcommits.org)
- **apology**: `oops`, `typo`, `forgot`, `sorry`. git doesn't forgive
- **novelist**: subject line over 72 characters. that's what the commit body is for

## the mcp bit

turns out you can also plug it into an AI app as an [MCP](https://modelcontextprotocol.io) server, so the AI reads your actual git history and writes the roast itself. funnier than mine, honestly.

```json
{
  "mcpServers": {
    "commit-roast": { "command": "commit-roast", "args": ["serve"] }
  }
}
```

drop that into your MCP client's config (Claude Desktop, Cursor, whatever you use), then ask it to roast a repo, brutal mode.

what the server gives it:

| | name | what |
|---|---|---|
| tool | `commit_stats` | all the numbers above |
| tool | `worst_commits` | the hall of shame, with reasons |
| resource | `commit-roast://signals` | what every number means |
| resource | `commit-roast://jokes/{spice}` | my jokes, as a style guide |
| prompt | `roast` | "roast this repo, cite real commits, don't make stuff up" |

want to poke at it without an AI? `npx @modelcontextprotocol/inspector commit-roast serve`

## LEARNING.md

the actual reason i kept going past 1am: every commit has a note in [LEARNING.md](LEARNING.md) about what i figured out while building it. two of them are real bugs i hit along the way: `git log --since` lying about dates, and a missing comma that quietly glued two jokes together. future me will thank me. probably.

## dev

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## license

MIT. roast responsibly.
