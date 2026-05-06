# 😆 Joke Agent

Autonomous Cantonese / Traditional-Chinese joke pipeline for Hong Kong forums.
Discovers, extracts, deduplicates, classifies, and stores jokes from LIHKG and
HKGolden — preserving every joke verbatim, with a human-in-the-loop **test
mode** for review before any DB write.

> Full spec: [`goal.md`](goal.md). Architecture document:
> [`Joke_Agent_Architecture.docx`](Joke_Agent_Architecture.docx) (regenerate
> with `node generate_arch_doc.js`).

---

## What it does

```
[Auto-pick source] → [Fetch forum page] → [LLM boundary detection]
                       ↓
                   [Dedup vs jokes.fingerprint]
                       ↓
                   [LLM tag classification]
                       ↓
                   [Terminal review prompt]   (test mode)
                       ↓
                   [Atomic save: jokes + joke_sources + markdown + reviewed_pages]
```

- **LIHKG** is fetched via the JSON `/api_v2` endpoint (the SPA HTML doesn't carry the posts).
- **HKGolden** is fetched via `md.hkgolden.com` (the desktop site is JS-rendered).
- **Baby Kingdom** is fetched via `forum.php?mod=viewthread&tid=...` (Discuz-based, plain HTML).
- **Boundary detection** asks the LLM to identify self-contained jokes and skip reactions / commentary; output is verified to be a verbatim substring of the page text — anything the LLM rewrites is silently dropped.
- **Tag classification** queries `tag_taxonomy` at runtime (never hardcoded) and validates returned tags against the registry.
- **Atomic save** uses one DB transaction covering `jokes` INSERT, `joke_sources` INSERT, and `source_threads.reviewed_pages` bump; markdown files are appended only after COMMIT.

---

## Prerequisites

| Component | Why |
|---|---|
| **Python 3.8+** | runtime |
| **`requests`** + **`beautifulsoup4`** | forum HTML/JSON fetching |
| **codex-ollama-bridge** running on `127.0.0.1:11540` | LLM access via OpenClaw OAuth |
| **`openai-codex/gpt-5.5`** model accessible through the bridge | boundary detection + tagging |
| **SQLite DB** under your OpenClaw workspace (default: `~/.openclaw/workspace/state/jokes.db`) | persistence |

### Environment overrides

Every default is overridable via env var — see [`joke_agent/__init__.py`](joke_agent/__init__.py):

| Variable | Default | Purpose |
|---|---|---|
| `OPENCLAW_WORKSPACE` | `~/.openclaw/workspace` | base for DB + markdown |
| `JOKE_AGENT_DB` | `<workspace>/state/jokes.db` | SQLite path |
| `JOKE_AGENT_JOKE_MD` | `<workspace>/joke.md` | export markdown |
| `JOKE_AGENT_SOURCE_MD` | `<workspace>/joke_source.md` | source audit markdown |
| `JOKE_AGENT_LLM_BASE_URL` | `http://127.0.0.1:11540/v1` | LLM endpoint |
| `JOKE_AGENT_LLM_MODEL` | `openai-codex/gpt-5.5` | LLM model id |
| `JOKE_AGENT_LLM_FALLBACK_BASE_URL` | `http://127.0.0.1:11545/v1` | nvidia bridge fallback |
| `JOKE_AGENT_LLM_FALLBACK_MODEL` | `google/gemma-4-31b-it` | fallback model id |
| `JOKE_AGENT_CACHE_DIR` | `~/.cache/joke_agent` | forum-fetch cache root |
| `JOKE_AGENT_CACHE_TTL` | `86400` | cache TTL in seconds |
| `JOKE_AGENT_USER_AGENT` | Chrome-on-Android | UA for forum fetches |
| `JOKE_AGENT_FETCH_DELAY` | `1.5` | seconds between live fetches |
| `JOKE_AGENT_MODE` | `live` | set to `test` for review-before-save |

The agent gracefully falls back to the **nvidia-ollama-bridge** on port 11545
(`google/gemma-4-31b-it`) for documentation purposes — not currently auto-used,
but `LLM_FALLBACK_*` constants are already wired in
[`joke_agent/__init__.py`](joke_agent/__init__.py).

```bash
pip3 install --user requests beautifulsoup4
```

The bridge is expected to be running as a systemd user service:

```bash
systemctl --user status codex-ollama-bridge
# if down:
systemctl --user restart codex-ollama-bridge
```

---

## Quick start

```bash
cd /home/pi/Documents/joke_agent_project

# 1. Verify everything is wired up
python3 -m joke_agent health

# 2. See which forum thread the agent will auto-pick next
python3 -m joke_agent sources

# 3. Run test mode — auto-pick, fetch, review, save (or abandon)
python3 -m joke_agent test 5
```

The `test` prompt waits for one of:

| Key | Effect |
|---|---|
| `a` | Save all candidates (atomic — DB + both markdown files) |
| `n` | Abandon all (zero side effects; `reviewed_pages` not advanced) |
| `p` | Per-joke `y/n`; saves only those you keep |
| `q` | Same as abandon — safe quit |

---

## Commands

| Command | Purpose |
|---|---|
| `python3 -m joke_agent health` | DB schema check + bridge round-trip ping |
| `python3 -m joke_agent verify-db` | DB schema only |
| `python3 -m joke_agent stats` | Joke / source / thread / tag counts |
| `python3 -m joke_agent chat "<prompt>"` | One-shot LLM call (smoke-test the bridge) |
| `python3 -m joke_agent sources` | List active `source_threads`; show what `test` will pick |
| `python3 -m joke_agent fetch <url>` | Fetch one forum page; print posts (no LLM, no DB) |
| `python3 -m joke_agent fetch-jokes 5 --review --url <url>` | Explicit-URL test mode |
| `python3 -m joke_agent fetch-jokes 5 --url <url>` | **Live mode** — auto-saves; use only when confident |
| `python3 -m joke_agent test [N]` | Shortcut: `fetch-jokes N --review` with auto-pick |
| `python3 -m joke_agent rebuild-md` | Rebuild `joke.md` + `joke_source.md` from DB (with backup) |
| `python3 -m joke_agent renumber [--dry-run] [--yes]` | Close gaps in joke IDs; backs up DB + markdown |

### Useful flags

| Flag | Effect |
|---|---|
| `--review` | Test mode (review-before-save) |
| `--platform lihkg` / `hkgolden` / `babykingdom` | Restrict auto-pick to one platform; ignored when `--url` is given |
| `--no-cache` | Force a fresh forum fetch (bypasses 24h local cache) |
| `--max-pages N` | Cap how many pages the pipeline crawls in one run (default 10) |
| `--base-url <url>` | Override LLM bridge URL |
| `--model <id>` | Override LLM model (e.g. switch to `openai-codex/gpt-5.4-mini`) |

```bash
# only crawl LIHKG threads
python3 -m joke_agent test --platform lihkg

# only HKGolden
python3 -m joke_agent test --platform hkgolden

# only Baby Kingdom (Discuz-based)
python3 -m joke_agent test --platform babykingdom

# preview which thread the filter would pick first
python3 -m joke_agent sources --platform lihkg
```

Or via environment variable:

```bash
JOKE_AGENT_MODE=test python3 -m joke_agent fetch-jokes 5 --url ...
```

---

## File layout

```
joke_agent_project/
├── README.md                       ← this file
├── goal.md                         ← full spec (sections 1–12)
├── Joke_Agent_Architecture.docx    ← architecture doc
├── generate_arch_doc.js            ← regenerates the .docx
├── skills/joke-agent/              ← OpenClaw skill bundle
│   ├── skill.json
│   ├── _meta.json
│   └── SKILL.md
└── joke_agent/                     ← Python package (run as `python3 -m joke_agent`)
    ├── __init__.py                 ← constants (DB path, bridge URL, model)
    ├── __main__.py
    ├── cli.py                      ← argparse dispatcher
    ├── db.py                       ← SQLite layer + schema verify + transaction helper
    ├── llm.py                      ← stdlib OpenAI-protocol client (urllib)
    ├── health.py                   ← pre-flight checks
    ├── mode.py                     ← Live | Test mode resolver
    ├── cache.py                    ← 24h on-disk cache for forum fetches
    ├── http_fetch.py               ← polite UA / rate-limited / cached HTTP wrapper
    ├── canonicalize.py             ← whitespace + line-break normalisation
    ├── fingerprint.py              ← SHA-256 of canonical_text
    ├── extract.py                  ← LLM boundary detector (verbatim verified)
    ├── tagging.py                  ← LLM tag classifier
    ├── writer.py                   ← atomic save: DB + markdown + reviewed_pages
    ├── pipeline.py                 ← fetch → extract → dedup → tag orchestrator
    ├── review.py                   ← terminal review UI
    ├── sources.py                  ← auto-pick from source_threads, seed defaults
    ├── rebuild_md.py               ← DB → markdown rebuild
    ├── renumber.py                 ← close ID gaps (J0000NN continuous)
    └── forums/
        ├── base.py                 ← Post, ForumPage dataclasses
        ├── lihkg.py                ← LIHKG api_v2 JSON client
        ├── hkgolden.py             ← md.hkgolden.com HTML scraper
        ├── babykingdom.py          ← Baby Kingdom (Discuz) HTML scraper
        └── router.py               ← URL → platform dispatch
```

---

## Database

Source of truth: `/home/pi/.openclaw/workspace/state/jokes.db`.

Five active tables (per [goal.md §5](goal.md)):

| Table | Purpose |
|---|---|
| `jokes` | one row per unique joke (id, canonical_text, display_text, fingerprint, tags, status, timestamps) |
| `joke_sources` | verbatim raw_text audit log per import |
| `source_threads` | per-thread crawl progress (`reviewed_pages` / `total_pages`, `status`) |
| `tag_taxonomy` | the only valid tag list — LLM queries this at runtime |
| `meta` | key-value agent state (`schema_version`, etc.) |

> **Legacy:** `groups` and `joke_sends` still exist in the live DB but are out
> of scope per the current spec. They get flagged by `verify-db`. Drop them
> only on explicit instruction.

---

## Operating modes

| | Live mode (default) | Test mode (`--review` or `JOKE_AGENT_MODE=test`) |
|---|---|---|
| Discover & fetch | yes | yes |
| LLM boundary detection | yes | yes |
| Fingerprint dedup | yes | yes |
| LLM tagging | yes | yes (pre-review, so user sees proposed tags) |
| INSERT into `jokes` / `joke_sources` | automatic | only after user approval |
| Append to `joke.md` / `joke_source.md` | automatic | only after user approval |
| `source_threads.reviewed_pages` increment | automatic | only on save; no-op on abandon |

**Critical rule:** in test mode, NO row is inserted, updated, or appended
without explicit user approval (`a` or `p`-with-y answers). `n` and `q` are
identical zero-side-effect exits.

---

## Maintenance recipes

### After manual SQL edits or restored backups, the markdown drifted

```bash
python3 -m joke_agent rebuild-md
```

Backs up `joke.md` and `joke_source.md` with timestamp, regenerates from DB.

### Joke IDs got holes (deletes, retired entries)

```bash
python3 -m joke_agent renumber --dry-run    # preview the plan
python3 -m joke_agent renumber              # interactive y/N
python3 -m joke_agent renumber --yes        # automated (CI / scripts)
```

Backs up the SQLite file (`.bak-renumber-<timestamp>`), runs a 2-pass
rename through a `TMP_` namespace to avoid PK collisions, verifies
`PRAGMA foreign_key_check`, then rebuilds the markdown.

### Cache got stale during dev

```bash
rm -rf ~/.cache/joke_agent/
```

Or pass `--no-cache` to a single command.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `health` says `bridge.reachable: FAIL` | Bridge service stopped | `systemctl --user restart codex-ollama-bridge` |
| `health` flags `legacy tables still present` | `groups` / `joke_sends` left over | Out of scope; ignore unless you've decided to drop them |
| `LLMError ... 401` | OpenClaw OAuth profile expired | Re-authenticate in OpenClaw or set `CODEX_BRIDGE_OAUTH_PROFILE` to a live profile |
| `boundary detection failed: ...` | Transient empty LLM response | Auto-retried twice; if still failing, check `journalctl --user -u codex-ollama-bridge -n 50` |
| `LIHKG api 403` | LIHKG bot detection tripped | Confirm `User-Agent` and `X-LI-DEVICE: android` headers (set by [`forums/lihkg.py`](joke_agent/forums/lihkg.py)) |
| `0 candidates` after a run | All jokes on that page are duplicates of DB rows | Check `python3 -m joke_agent sources` and try a different thread |
| Markdown drift after a power loss | `source_threads.reviewed_pages` advanced but markdown append failed | `rebuild-md` |

---

## License

Personal project — no license declared. Adapt freely for your own setup.
