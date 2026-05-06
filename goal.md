# Project Goal: Cantonese Joke Fetching Agent

## 1. Core Objective

Build an autonomous agent that discovers, extracts, deduplicates, tags, and stores Cantonese/Chinese jokes from Hong Kong online forums and web sources. The agent preserves every joke in its full original text — no summarisation, no rewriting — so that humour is never lost in translation.

---

## 2. Success Definition

The agent is considered successful when it can:

1. **Discover** new joke source URLs automatically via Google search and forum exploration.
2. **Extract** only the joke content (not replies or commentary) in its exact original form.
3. **Deduplicate** via fingerprint check against `jokes.db` before saving anything new.
4. **Tag** each joke using the LLM, drawing valid tags from the `tag_taxonomy` table.
5. **Persist** each unique joke across `jokes`, `joke_sources`, and the Markdown export.
6. **Track** crawl progress per thread in `source_threads` (`reviewed_pages` / `total_pages`).

---

## 3. Target Sources

### Primary Forums
| Source | Search Strategy |
|---|---|
| LIHKG | `lihkg 笑話`, `lihkg 黃色笑話`, `lihkg 冷笑話` |
| HKGolden | `hkgolden 笑話`, `hkgolden 搞笑`, `hkgolden 爆笑` |
| Baby Kingdom | `baby kingdom 笑話` |
| Other HK forums | `討論區 廣東話笑話`, `香港論壇 搞笑` |

### Source URL Examples

Real thread URLs verified against the live agent's fetcher.

**LIHKG** — agent uses the JSON API (`/api_v2/thread/{id}/page/{N}`); direct GET on the SPA URL returns only a 4 KB shell.
- `https://lihkg.com/thread/596076/page/1` — **36 pages** (verified)
- `https://lihkg.com/thread/34189/page/1` — **31 pages** (verified)

**HKGolden** — agent uses the **mobile site** (`md.hkgolden.com/view.aspx?message=...&page=N`); the desktop `forum.hkgolden.com` is JS-rendered and effectively unscrapeable. Page counts on mobile differ from desktop because the mobile site fits more posts per page.
- `https://md.hkgolden.com/view.aspx?message=5191089&page=1` — **8 mobile pages** (was 29 on desktop)

**Baby Kingdom** — Discuz-based forum. Plain HTML, no SPA blocker. Both URL forms are accepted; agent normalises to `forum.php?mod=viewthread`.
- `https://www.baby-kingdom.com/forum.php?mod=viewthread&tid=662629` — single-page joke thread (verified)
- Inputs in the rewrite form `https://www.baby-kingdom.com/thread-{tid}-{page}-1.html` are also accepted.

URL pattern notes:
- LIHKG: `https://lihkg.com/thread/{thread_id}/page/{N}` — used for both `source_ref` and the SPA URL the user pastes
- HKGolden: `https://md.hkgolden.com/view.aspx?message={thread_id}&page={N}` — used for `source_ref` (matches what we actually fetch). Inputs in the form `https://forum.hkgolden.com/thread/{id}/page/{N}` are accepted and rewritten internally.
- Baby Kingdom: `https://www.baby-kingdom.com/forum.php?mod=viewthread&tid={thread_id}&page={N}` — canonical Discuz URL; rewrite form accepted on input.
- Strip the `&page=N` (HKGolden, Baby Kingdom) or `/page/N` (LIHKG) segment before storing into `source_threads.thread_url`.

### Google Search Keyword Rotation Pool
- `lihkg 笑話 site:lihkg.com`
- `hkgolden 笑話 site:forum.hkgolden.com`
- `廣東話笑話 討論區`
- `香港 搞笑 笑話 論壇`
- `冷笑話 廣東話`
- `黃色笑話 香港論壇`

### Source Discovery Rule
When a new thread is found, `INSERT OR IGNORE` it into `source_threads` (status=`pending`) before the run ends.

---

## 4. Critical Rules (Non-Negotiable)

| Rule | Detail |
|---|---|
| **No summarising** | Store the joke exactly as posted. Never rewrite or condense. |
| **No punchline alteration** | The original punchline must be preserved character-for-character. |
| **No duplicates** | Check `jokes.fingerprint` before every save. Reject any match. |
| **Original text only** | If the original text cannot be extracted cleanly, skip that joke. |
| **Source always recorded** | Every stored joke must have its source URL in `joke_sources`. |

---

## 5. Database Schema & Column Usage

All data lives in `/home/pi/.openclaw/workspace/state/jokes.db`.

---

### 5a. `jokes` — Master Joke Store

```sql
CREATE TABLE jokes (
    id             TEXT PRIMARY KEY,      -- J000001, J000002, ...
    canonical_text TEXT NOT NULL,         -- normalised text used for fingerprinting
    display_text   TEXT NOT NULL,         -- original text preserved verbatim
    fingerprint    TEXT NOT NULL UNIQUE,  -- SHA-256 of canonical_text; dedup key
    source_type    TEXT NOT NULL,         -- platform: lihkg | hkgolden | other
    source_ref     TEXT NOT NULL,         -- full page URL where joke was found
    source_date    TEXT,                  -- ISO date the page was fetched
    tags           TEXT NOT NULL DEFAULT '', -- comma-separated tags from tag_taxonomy
    status         TEXT NOT NULL DEFAULT 'active', -- active | retired
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
```

**How the agent uses each column:**

| Column | Agent Action |
|---|---|
| `id` | Auto-assigned as `J` + zero-padded integer, incrementing from the highest existing ID |
| `canonical_text` | Normalised joke text (trim whitespace, normalise line breaks) — used only for fingerprinting |
| `display_text` | Verbatim text as extracted from source — preserved exactly for downstream consumers |
| `fingerprint` | `sha256(canonical_text)` — run `SELECT 1 FROM jokes WHERE fingerprint=?` before every INSERT |
| `source_type` | Set to the platform name: `lihkg`, `hkgolden`, or `other` |
| `source_ref` | Full URL of the specific page (e.g. `https://lihkg.com/thread/34189/page/28`) |
| `source_date` | ISO date of the fetch run (e.g. `2026-05-05`) |
| `tags` | Comma-separated tags chosen by LLM from `tag_taxonomy`; empty until LLM pass runs |
| `status` | Default `active`; set to `retired` if joke is withdrawn or found to be a duplicate after import |
| `created_at` | ISO 8601 timestamp set on INSERT — this is the **date the joke was added to the DB**; never updated after |
| `updated_at` | ISO 8601 timestamp; refreshed whenever any column on this row changes (tags, status, etc.) |

---

### 5b. `joke_sources` — Raw Extraction Log

One row per import event. Provides a forensic record of what the agent saw before any processing.

```sql
CREATE TABLE joke_sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    joke_id     TEXT NOT NULL,   -- FK → jokes.id
    source_type TEXT NOT NULL,   -- mirrors jokes.source_type
    source_ref  TEXT NOT NULL,   -- mirrors jokes.source_ref (full URL)
    raw_text    TEXT NOT NULL,   -- verbatim extracted text before canonicalisation
    source_date TEXT,
    imported_at TEXT NOT NULL,
    FOREIGN KEY (joke_id) REFERENCES jokes(id)
);
```

**How the agent uses each column:**

| Column | Agent Action |
|---|---|
| `joke_id` | Link to the jokes table row just inserted |
| `source_type` / `source_ref` | Copy from the `jokes` row — denormalised for audit queries |
| `raw_text` | The unprocessed text block as the LLM received it, before normalisation — preserves exact whitespace and punctuation |
| `imported_at` | Timestamp of the INSERT — distinct from `source_date` which is the page fetch date |

---

### 5c. `source_threads` — Crawl Progress Tracker

One row per forum thread. Tells the agent exactly where it left off.

```sql
CREATE TABLE source_threads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_url      TEXT    NOT NULL UNIQUE,  -- base URL, no /page/N suffix
    platform        TEXT    NOT NULL,         -- lihkg | hkgolden | other
    discovered_via  TEXT    NOT NULL DEFAULT 'unknown',
    total_pages     INTEGER,                  -- NULL until first page fetch detects it
    reviewed_pages  INTEGER NOT NULL DEFAULT 0,
    status          TEXT    NOT NULL DEFAULT 'pending', -- pending | in_progress | exhausted
    last_fetched_at TEXT,
    notes           TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

**How the agent uses each column:**

| Column | Agent Action |
|---|---|
| `thread_url` | Strip `/page/N` from any discovered URL before inserting |
| `total_pages` | Detect from pagination HTML on first page fetch; UPDATE immediately |
| `reviewed_pages` | Increment by 1 after each page is fully processed |
| `status` | `pending` → `in_progress` on first fetch; → `exhausted` when `reviewed_pages >= total_pages` |
| `last_fetched_at` | UPDATE to `now()` after each page fetch |

**Progress query:**
```sql
SELECT platform,
       substr(thread_url, 1, 55) AS thread,
       reviewed_pages || ' / ' || COALESCE(CAST(total_pages AS TEXT), '?') AS progress,
       status
FROM source_threads
ORDER BY status != 'exhausted', platform;
```

**Agent rules:**
1. New thread found → `INSERT OR IGNORE` with `status='pending'`, `reviewed_pages=0`.
2. Next page to fetch = `reviewed_pages + 1`.
3. On first page → detect `total_pages`, UPDATE immediately.
4. After each page → `reviewed_pages += 1`, `last_fetched_at = now()`.
5. `reviewed_pages >= total_pages` → set `status = 'exhausted'`.
6. Skip all threads where `status = 'exhausted'`.

---

### 5d. `tag_taxonomy` — Valid Tag Registry

The single source of truth for allowed tags. The LLM must query this table and only use tags found here.

```sql
CREATE TABLE tag_taxonomy (
    tag         TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Current tags (15 rows):**

| Tag | Description |
|---|---|
| `黃色笑話` | Adult/dirty jokes — sexual innuendo or explicit content |
| `老少皆宜` | Clean, family-friendly — safe for all ages |
| `攪笑IQ題` | Riddle or brain-teaser format with a funny answer |
| `冷笑話` | Dry/deadpan humour — the punchline lands quietly |
| `小明笑話` | Classic 小明 joke series |
| `諧音笑話` | Wordplay or homophone-based puns |
| `黑色幽默` | Dark humour — morbid or absurdist punchlines |
| `動物笑話` | Animals as main characters or subject |
| `學校笑話` | School / teacher-student setting |
| `職場笑話` | Workplace or boss-employee setting |
| `夫妻笑話` | Marriage, couple, or relationship jokes |
| `爸爸笑話` | Classic dad-joke style (groan-worthy puns) |
| `自我貶低` | Self-deprecating humour |
| `鬼馬笑話` | Witty, playful, or clever jokes (廣東話 鬼馬 style) |
| `其他笑話` | Fallback — does not fit any category above |

**LLM tagging rules:**
- A joke may carry **multiple tags** stored as a comma-separated string, e.g. `攪笑IQ題,動物笑話`.
- The LLM must load the valid tag list from `SELECT tag FROM tag_taxonomy` — never hardcode.
- Use `其他笑話` only when no other tag applies.
- Tag is based on **joke content only**, not the thread title.

**LLM prompt template:**
```
You are a joke classifier for a Cantonese/Chinese joke database.
Valid tags (from DB): {comma-separated result of SELECT tag FROM tag_taxonomy}

Assign one or more tags to the joke below.
Return ONLY the comma-separated tags. No explanation.

Joke:
{display_text}
```

**Backfill — existing English tags:**
20 jokes currently have English tags (`wordplay`, `animal`, `school`, `iq`). Migrate via:

| English | Chinese |
|---|---|
| `wordplay` | `諧音笑話` |
| `animal` | `動物笑話` |
| `school` | `學校笑話` |
| `iq` | `攪笑IQ題` |

Then re-run the LLM tagging pass over all jokes where `tags = ''` or tags contain ASCII-only values.

---

### 5e. `meta` — Agent State Store

```sql
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Current keys: `schema_version`, `created_at`, `source_files`.
The agent may add: `last_fetch_run`, `last_tag_pass`, `total_jokes_added`.

---

## 6. LLM Configuration & Roles

### 6.1 LLM Access — codex-ollama-bridge (OpenAI protocol)

The agent reaches the LLM through the locally-running **codex-ollama-bridge**, which exposes OpenClaw's OAuth-authenticated `openai-codex` provider as a standard OpenAI-compatible HTTP endpoint. No API key needed — the bridge reuses the OpenClaw OAuth profile (`openai-codex:<your-openclaw-account>`) and refreshes tokens automatically.

| Setting | Value |
|---|---|
| Bridge service | `codex-ollama-bridge.service` (user systemd, already running on port 11540) |
| Base URL | `http://127.0.0.1:11540/v1` |
| Protocol | OpenAI Chat Completions (`POST /v1/chat/completions`) |
| Model ID | `openai-codex/gpt-5.5` |
| API key | Any non-empty string (ignored by the bridge) |
| Streaming | Supported (`"stream": true` → SSE) |
| Auth | Inherited from OpenClaw OAuth — auto-refresh, no per-call setup |

**Why this route (vs OpenClaw's native CLI):**
- `openclaw capability model run` currently fails for `openai-codex/gpt-5.5` ("No text output returned").
- The bridge succeeds in ~7–8s with both OpenAI and Ollama protocols.
- Standard HTTP means the joke agent can use the OpenAI Python SDK directly — no shelling out, no CLI parsing.
- Swap-friendly: changing `base_url` is the only edit needed if the LLM provider ever changes.

**Python usage (reference for the joke agent):**

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:11540/v1",
    api_key="codex-bridge",  # any non-empty string
)

resp = client.chat.completions.create(
    model="openai-codex/gpt-5.5",
    messages=[
        {"role": "system", "content": "You are a Cantonese joke classifier..."},
        {"role": "user", "content": prompt_text},
    ],
    stream=False,
)
print(resp.choices[0].message.content)
```

**Health check before each agent run:**

```bash
python3 -c "import urllib.request,json; \
  req=urllib.request.Request('http://127.0.0.1:11540/v1/models'); \
  print(json.loads(urllib.request.urlopen(req,timeout=5).read())['data'][0]['id'])"
```

If the bridge is down, restart it:
```bash
systemctl --user restart codex-ollama-bridge
journalctl --user -u codex-ollama-bridge -n 20
```

**Fallback option:** the nvidia-ollama-bridge (port 11545, `google/gemma-4-31b-it`, also already running) can serve as a backup if the codex bridge auth expires or the upstream is unavailable. Same OpenAI protocol — only the URL and model id change.

### 6.2 Role: Joke Boundary Detection

The LLM identifies which lines in a raw forum page are the joke versus user replies.

### Rules:
- Read the raw thread post block.
- Mark the exact start and end of each self-contained joke.
- Discard everything after the joke: reaction emotes, reply commentary, off-topic lines.

### Example (LIHKG thread 34189, page 28):

```
學校中文口試
老師：時間夠 同學汁埋啲野可以走
學生：（呼），老師咁我走啦，thank you
老師：中文口試你講咩英文
學生：啊係喎，sorry
```
→ **Extract these lines** (complete joke).

```
汁你老母:o) :o) :o)
汁唔係5p都屌:-( :-(
點會唔係:o)
執拾 定 汁拾呀:o)
```
→ **Discard these lines** (user replies).

### Decision checklist:
- Does this block have a setup and a punchline?
- Is it self-contained without the surrounding replies?
- Are the remaining lines reactions rather than part of the joke?

---

## 7. Agent Workflow

```
[START]
    |
    v
[Google Search] — rotate keywords from pool
    |
    v
[Discover thread URLs]
    |   new URL found → strip /page/N → INSERT OR IGNORE into source_threads (pending)
    v
[For each thread in source_threads WHERE status != 'exhausted']
    |   next_page = reviewed_pages + 1
    v
[Fetch page {next_page}]
    |   first page → detect total_pages → UPDATE source_threads.total_pages
    v
[LLM: identify joke boundaries] — extract raw joke blocks
    |
    v
[For each extracted joke block]
    |
    +--> [Compute fingerprint = sha256(canonical_text)]
    |
    +--> [SELECT 1 FROM jokes WHERE fingerprint = ?]
    |           |
    |     FOUND → skip (duplicate)
    |           |
    |   NOT FOUND
    |           |
    |           +--> [SELECT tag FROM tag_taxonomy] → LLM assigns tags
    |           |
    |           +--> [INSERT INTO jokes]
    |           |      id, canonical_text, display_text, fingerprint,
    |           |      source_type, source_ref, source_date, tags, status
    |           |
    |           +--> [INSERT INTO joke_sources]
    |           |      joke_id, source_type, source_ref, raw_text, imported_at
    |           |
    |           +--> [Export row to joke.md]
    |
    v
[UPDATE source_threads]
    |   reviewed_pages += 1, last_fetched_at = now()
    |   if reviewed_pages >= total_pages → status = 'exhausted'
    v
[END]
```

---

## 8. Test Mode (Review Before Save)

Test mode lets the user manually approve candidate jokes before they hit the database. Used for spot-checking extraction quality and tag accuracy without polluting `jokes.db`.

### 8.1 Invocation

```
fetch <N> jokes --review
```
- `N` = number of candidate jokes to gather (default 5)
- Equivalent env flag: `JOKE_AGENT_MODE=test`

### 8.2 Flow

```
[User invokes test mode with target count N]
    |
    v
[Run normal pipeline: Discover → Extract → Dedup → Tag]
    |   - source_threads pages are FETCHED but reviewed_pages is NOT yet incremented
    |   - dedup against jokes.fingerprint runs as usual (no test-mode duplicates either)
    |   - LLM tagging runs so the user sees proposed tags
    |   - Candidates are held in memory only — no INSERT into jokes / joke_sources
    v
[Continue crawling until N unique candidates are gathered]
    |
    v
[Print all N candidates to terminal in review format]
    |
    v
[Prompt user for decision: save all | abandon all | per-joke y/n]
    |
    +-- SAVE (all or selected) ──> [Atomic commit]
    |                                  - INSERT INTO jokes
    |                                  - INSERT INTO joke_sources
    |                                  - Append to joke.md and joke_source.md
    |                                  - UPDATE source_threads.reviewed_pages for fully-processed pages
    |                                  - UPDATE source_threads.last_fetched_at = now()
    |
    +-- ABANDON ────────────────────> [Discard candidates]
                                       - No DB writes
                                       - reviewed_pages NOT incremented (same pages refetched next run)
                                       - Wasted fetch+LLM cost is the acceptable trade-off
```

### 8.3 Terminal Review Format

Each candidate is printed as a self-contained block:

```
═════════════════════════════════════════════════
  Candidate 1 of 5
═════════════════════════════════════════════════
  Source     : https://lihkg.com/thread/596076/page/14
  Platform   : lihkg
  Tags (LLM) : 諧音笑話, 鬼馬笑話
  Fingerprint: 3a9f...e21c  (not yet in DB)
─────────────────────────────────────────────────
  學校中文口試
  老師：時間夠 同學汁埋啲野可以走
  學生：（呼），老師咁我走啦，thank you
  老師：中文口試你講咩英文
  學生：啊係喎，sorry
═════════════════════════════════════════════════
```

After all N candidates are displayed:

```
Decision? [a]ll save / [n]one (abandon) / [p]er-joke / [q]uit:
```

If `p` (per-joke):
```
Candidate 1: save? [y/n]:
Candidate 2: save? [y/n]:
...
```

### 8.4 Test Mode Rules

| Rule | Detail |
|---|---|
| **No silent writes** | In test mode, NO row is inserted, updated, or appended without explicit user approval |
| **Same dedup logic** | Test mode still checks `jokes.fingerprint` — already-saved jokes are skipped during candidate gathering, never shown to the user |
| **Tagging happens pre-review** | LLM tagging runs before display so the user can verify the proposed tags |
| **Atomic commit on save** | DB INSERTs, markdown appends, and `reviewed_pages` updates all happen in one transaction — partial-save failures roll back |
| **Source thread integrity** | `last_fetched_at` is updated on save; on abandon, nothing changes — same pages will be re-crawled next run |
| **Quit is safe** | `q` at the prompt = same as abandon: zero side effects |

### 8.5 Difference from Live Mode

| Step | Live Mode | Test Mode |
|---|---|---|
| Discover & fetch | Yes | Yes |
| LLM boundary detection | Yes | Yes |
| Fingerprint dedup | Yes | Yes |
| LLM tagging | Yes | Yes |
| INSERT into jokes | Auto | **Only after user approval** |
| INSERT into joke_sources | Auto | **Only after user approval** |
| Append to joke.md | Auto | **Only after user approval** |
| `reviewed_pages` increment | Auto | **Only on save**; no-op on abandon |

---

## 9. Data Paths

| Asset | Path |
|---|---|
| SQLite Joke DB | `/home/pi/.openclaw/workspace/state/jokes.db` |
| Markdown Export | `/home/pi/.openclaw/workspace/joke.md` |
| Source Registry (mirror) | `/home/pi/.openclaw/workspace/joke_source.md` |

---

## 10. Joke ID Convention

Format: `J` + 6-digit zero-padded integer. Auto-increment from the highest existing ID:
```sql
SELECT MAX(CAST(SUBSTR(id,2) AS INTEGER)) FROM jokes;
```

---

## 11. Full DB Table Summary

| Table | Purpose |
|---|---|
| `jokes` | Master store — one row per unique joke |
| `joke_sources` | Raw extraction log — verbatim text before canonicalisation |
| `source_threads` | Forum crawl progress: `reviewed_pages` / `total_pages` per thread |
| `tag_taxonomy` | Valid tag registry — LLM must read from here, never hardcode |
| `meta` | Key-value agent state store |

---

## 12. Scope Boundaries

- **In scope:** Cantonese jokes, Traditional Chinese jokes, Hong Kong vernacular (廣東話).
- **Out of scope:** Mainland Simplified Chinese jokes, memes without text, image-only posts, political satire without a joke structure.
