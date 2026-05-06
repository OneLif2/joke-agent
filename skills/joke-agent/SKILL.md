---
name: joke-agent
version: 0.2.0
description: Cantonese / Traditional-Chinese joke fetching agent. Auto-picks a forum thread (LIHKG, HKGolden, or Baby Kingdom), extracts jokes via LLM, dedups, classifies tags, presents candidates for review, and atomically saves to jokes.db + markdown. Test mode (review-before-save) is the default safe path.
metadata:
  openclaw:
    emoji: "😆"
    requires:
      bins: ["python3"]
      files:
        - "/home/pi/.openclaw/workspace/state/jokes.db"
        - "/home/pi/Documents/joke_agent_project/joke_agent/__init__.py"
      services:
        - "codex-ollama-bridge"
---

# Joke Agent

Use this skill when the user wants to:

- Fetch new Cantonese / 廣東話 jokes from LIHKG or HKGolden into the local `jokes.db`
- Run **test mode** to review candidates before any DB write
- Inspect or reconcile the joke DB and its markdown exports (`joke.md`, `joke_source.md`)
- Renumber joke IDs to be continuous (close gaps after manual deletes)

The agent is a Python package at
`/home/pi/Documents/joke_agent_project/joke_agent` and is invoked with
`python3 -m joke_agent <subcommand>`.

## Defaults

- Project root: `/home/pi/Documents/joke_agent_project`
- DB: `/home/pi/.openclaw/workspace/state/jokes.db`
- Markdown export: `/home/pi/.openclaw/workspace/joke.md`
- Source audit: `/home/pi/.openclaw/workspace/joke_source.md`
- LLM: `openai-codex/gpt-5.5` via codex-ollama-bridge at `http://127.0.0.1:11540/v1`
- Fallback LLM: `google/gemma-4-31b-it` via nvidia-ollama-bridge at `http://127.0.0.1:11545/v1`
- Cache: `~/.cache/joke_agent/<platform>/<sha-prefix>` (24h TTL)
- Default test-mode target: 5 candidates
- Default `--max-pages`: 10

## Required services

```bash
# LLM bridge — must be running
systemctl --user status codex-ollama-bridge

# Restart if needed
systemctl --user restart codex-ollama-bridge
```

## Pre-flight

```bash
python3 -m joke_agent health
```

Expects:
- `db.path: OK`, `db.schema: OK` (legacy `groups` / `joke_sends` warnings are
  out-of-scope per goal.md; ignore unless you've explicitly decided to drop)
- `bridge.reachable: OK`, `bridge.model: openai-codex/gpt-5.5 advertised`,
  `bridge.chat: round-trip OK`

## Run test mode (the safe default)

```bash
cd /home/pi/Documents/joke_agent_project
python3 -m joke_agent test 5
```

Pipeline:

1. Auto-pick the next non-exhausted thread from `source_threads`
   (fallback: seed three default threads from goal.md if none usable).
2. Fetch page `reviewed_pages + 1`.
3. Run LLM boundary detection → verbatim-substring verification.
4. Dedup via `jokes.fingerprint` (and against the in-batch buffer).
5. LLM tag classification using `tag_taxonomy`.
6. Print numbered candidate blocks with source / tags / fingerprint preview / verbatim text.
7. Wait for keystroke at the prompt:

   ```
   Decision for N candidate(s)? [a]ll save / [n]one (abandon) / [p]er-joke / [q]uit:
   ```

8. On `a` or per-joke `y`: atomic save (jokes + joke_sources INSERT, joke.md / joke_source.md append, `reviewed_pages` bump, `last_fetched_at` UPDATE — all in one DB transaction).
9. On `n` / `q`: zero side effects, `reviewed_pages` not advanced.

## Subcommand reference

| Command | Purpose |
|---|---|
| `health` | DB + bridge pre-flight |
| `verify-db` | DB schema check only |
| `stats` | Joke / source / thread / tag counts |
| `chat "<prompt>"` | One-shot LLM round-trip |
| `sources` | List active threads, show what `test` will pick next |
| `fetch <url>` | Print posts from one forum page (no LLM, no DB) |
| `fetch-jokes [N] --url <url> [--review]` | Explicit-URL pipeline run |
| `test [N]` | Auto-pick + review-before-save shortcut for `fetch-jokes` |
| `rebuild-md` | DB → joke.md / joke_source.md (with backup) |
| `renumber [--dry-run] [--yes]` | Close gaps in joke IDs (DB-backed-up first) |

## Useful flags

| Flag | Effect |
|---|---|
| `--review` | Force test mode |
| `--platform lihkg` / `hkgolden` / `babykingdom` | Restrict auto-pick to one platform |
| `--no-cache` | Bypass 24h fetch cache |
| `--max-pages N` | Cap pages crawled in one run (default 10) |
| `--base-url <url>` | Override LLM bridge URL |
| `--model <id>` | Override LLM model id |

Examples:

```bash
python3 -m joke_agent test --platform lihkg          # crawl LIHKG only
python3 -m joke_agent sources --platform hkgolden    # see HKGolden picks
```

Or via env:

```bash
JOKE_AGENT_MODE=test python3 -m joke_agent fetch-jokes 5 --url <url>
```

## Forum URL acceptance

Inputs to `--url` are normalised internally:

- LIHKG: `https://lihkg.com/thread/{id}/page/{N}`
  → fetched via `https://lihkg.com/api_v2/thread/{id}/page/{N}` with
  `X-LI-DEVICE: android` (the SPA URL only returns a 4 KB shell).
- HKGolden: any of `forum.hkgolden.com/thread/{id}/page/{N}`,
  `forum.hkgolden.com/amp/{id}`, `md.hkgolden.com/view.aspx?message={id}&page={N}`,
  `md.hkgolden.com/view_amp.aspx?...`
  → fetched via `md.hkgolden.com/view.aspx?message={id}&page={N}` (the
  desktop site is JS-rendered).
- Baby Kingdom: `baby-kingdom.com/forum.php?mod=viewthread&tid={id}&page={N}`
  or the rewrite form `baby-kingdom.com/thread-{id}-{page}-1.html`
  → fetched via the canonical `forum.php` URL. Discuz-based, plain HTML.

`source_ref` is stored as the canonical fetched URL.

## Markdown alignment recipes

### Drift between DB and joke.md

```bash
python3 -m joke_agent rebuild-md
```

Backs up the existing `.md` files with a timestamp, regenerates from DB rows.
The legacy "missing joke_sources rows" gap (jokes that pre-date the audit
log) is surfaced at the top of `joke_source.md`.

### Joke IDs have gaps

```bash
python3 -m joke_agent renumber --dry-run    # preview
python3 -m joke_agent renumber --yes        # apply + auto-rebuild markdown
```

Backs up the SQLite file (`.bak-renumber-<timestamp>`), runs a 2-pass rename
through a `TMP_` namespace to avoid PK collisions, verifies
`PRAGMA foreign_key_check` passes, then rebuilds the markdown.

## Operating modes

| Step | Live mode | Test mode |
|---|---|---|
| Discover, fetch, extract, dedup, tag | yes | yes |
| INSERT into jokes / joke_sources | automatic | only after user approval |
| Append to joke.md / joke_source.md | automatic | only after user approval |
| `reviewed_pages` increment | automatic | only on save; no-op on abandon |

**Critical rule:** test mode performs **no** row writes without explicit
user approval. `n` and `q` are zero-side-effect exits.

## Tag taxonomy

15 valid tags live in `tag_taxonomy`. The LLM is given the list at runtime —
never hardcode. Returned tags are validated against the table; anything
unknown is dropped. Empty result defaults to `其他笑話`.

## Troubleshooting

- **`bridge.reachable: FAIL`** — bridge service is down. Restart with
  `systemctl --user restart codex-ollama-bridge` and re-run `health`.
- **`LLMError 401`** — OpenClaw OAuth profile expired. Re-auth in OpenClaw,
  or set `CODEX_BRIDGE_OAUTH_PROFILE` in `~/.config/codex-ollama-bridge/env`.
- **`boundary detection failed`** — usually transient (bridge returned an
  empty completion). Auto-retried twice; if persistent, check
  `journalctl --user -u codex-ollama-bridge -n 50`.
- **`LIHKG api 403`** — bot detection tripped. The agent already sets the
  required headers; if it still 403s, the upstream may be rate-limiting —
  wait a few minutes.
- **`0 candidates`** — every joke on the fetched page is already in
  `jokes.fingerprint`. Try `python3 -m joke_agent sources` to switch
  threads, or pass `--max-pages 5` to crawl deeper.
- **Markdown drift after a crash** — run `python3 -m joke_agent rebuild-md`.
  The DB is the source of truth; markdown is regenerable.

## Out of scope (do not invoke this skill for)

- WhatsApp delivery / sending jokes to groups (removed from goal.md).
- Auto-discovery via Google Search (Phase 2.1 deferred — paste URLs or use
  auto-pick instead).
- Mainland Simplified Chinese jokes, image-only memes, political satire
  without joke structure (per goal.md §11).
