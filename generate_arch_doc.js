const {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  Table, TableRow, TableCell, WidthType, BorderStyle,
  AlignmentType, ShadingType, convertInchesToTwip,
} = require('docx');
const fs = require('fs');

// ── helpers ──────────────────────────────────────────────────────────────────

const BLUE  = '1F4E79';
const LBLUE = 'D6E4F0';
const GRAY  = 'F2F2F2';
const BLACK = '000000';

function h1(text) {
  return new Paragraph({
    text,
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 120 },
  });
}

function h2(text) {
  return new Paragraph({
    text,
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 80 },
  });
}

function h3(text) {
  return new Paragraph({
    text,
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 160, after: 60 },
  });
}

function p(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: 22, font: 'Calibri', ...opts })],
    spacing: { after: 100 },
    alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    children: [new TextRun({ text, size: 22, font: 'Calibri' })],
    bullet: { level },
    spacing: { after: 60 },
  });
}

function code(text) {
  return new Paragraph({
    children: [new TextRun({
      text,
      font: 'Courier New',
      size: 18,
      color: '1F4E79',
    })],
    spacing: { after: 40 },
    indent: { left: convertInchesToTwip(0.4) },
  });
}

function spacer() {
  return new Paragraph({ text: '', spacing: { after: 80 } });
}

function tableRow(cells, isHeader = false) {
  return new TableRow({
    tableHeader: isHeader,
    children: cells.map((text, i) => new TableCell({
      shading: isHeader
        ? { fill: BLUE, type: ShadingType.CLEAR }
        : (i === 0 ? { fill: GRAY, type: ShadingType.CLEAR } : undefined),
      children: [new Paragraph({
        children: [new TextRun({
          text,
          bold: isHeader || i === 0,
          color: isHeader ? 'FFFFFF' : BLACK,
          size: 20,
          font: 'Calibri',
        })],
        spacing: { after: 0 },
      })],
      margins: { top: 60, bottom: 60, left: 100, right: 100 },
    })),
  });
}

function makeTable(headers, rows) {
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [
      tableRow(headers, true),
      ...rows.map(r => tableRow(r, false)),
    ],
  });
}

// ── document ─────────────────────────────────────────────────────────────────

const doc = new Document({
  styles: {
    paragraphStyles: [
      {
        id: 'Heading1',
        name: 'Heading 1',
        basedOn: 'Normal',
        next: 'Normal',
        run: { bold: true, size: 36, color: BLUE, font: 'Calibri' },
        paragraph: { spacing: { before: 400, after: 160 } },
      },
      {
        id: 'Heading2',
        name: 'Heading 2',
        basedOn: 'Normal',
        next: 'Normal',
        run: { bold: true, size: 28, color: BLUE, font: 'Calibri' },
        paragraph: { spacing: { before: 300, after: 100 } },
      },
      {
        id: 'Heading3',
        name: 'Heading 3',
        basedOn: 'Normal',
        next: 'Normal',
        run: { bold: true, size: 24, color: '2E74B5', font: 'Calibri' },
        paragraph: { spacing: { before: 200, after: 80 } },
      },
    ],
  },
  sections: [{
    properties: {
      page: {
        margin: {
          top: convertInchesToTwip(1),
          bottom: convertInchesToTwip(1),
          left: convertInchesToTwip(1.2),
          right: convertInchesToTwip(1.2),
        },
      },
    },
    children: [

      // ── Cover ───────────────────────────────────────────────────────────────
      new Paragraph({
        children: [new TextRun({
          text: 'Cantonese Joke Fetching Agent',
          bold: true, size: 56, color: BLUE, font: 'Calibri',
        })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 720, after: 160 },
      }),
      new Paragraph({
        children: [new TextRun({
          text: 'System Architecture & Implementation Plan',
          size: 32, color: '2E74B5', font: 'Calibri',
        })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 80 },
      }),
      new Paragraph({
        children: [new TextRun({
          text: `Version 1.0  |  ${new Date().toLocaleDateString('en-GB', { year:'numeric', month:'long', day:'numeric' })}`,
          size: 22, color: '595959', font: 'Calibri',
        })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 960 },
      }),

      // ── 1. Overview ─────────────────────────────────────────────────────────
      h1('1. Overview'),
      p('The Cantonese Joke Fetching Agent is an autonomous pipeline that discovers, extracts, deduplicates, classifies, and stores Cantonese and Traditional Chinese jokes from Hong Kong online forums. Every joke is preserved in its full original text — no summarisation or rewriting — so that the original humour is never lost.'),
      spacer(),

      makeTable(
        ['Property', 'Value'],
        [
          ['Primary language focus', 'Cantonese (廣東話) & Traditional Chinese'],
          ['Primary sources', 'LIHKG, HKGolden, Baby Kingdom, Google-discovered forums'],
          ['LLM', 'openai-codex/gpt-5.5 via codex-ollama-bridge (OpenAI protocol, http://127.0.0.1:11540/v1)'],
          ['Database', 'SQLite — /home/pi/.openclaw/workspace/state/jokes.db'],
          ['Markdown export', '/home/pi/.openclaw/workspace/joke.md'],
        ]
      ),
      spacer(),

      // ── 2. Architecture Diagram ─────────────────────────────────────────────
      h1('2. High-Level Architecture'),
      p('The system is composed of four logical layers:'),
      spacer(),

      makeTable(
        ['Layer', 'Components', 'Responsibility'],
        [
          ['Discovery', 'Google Search + forum crawler', 'Find new joke thread URLs; register in source_threads'],
          ['Extraction', 'HTTP fetcher + LLM boundary detector', 'Fetch pages; isolate joke blocks from user replies'],
          ['Processing', 'Fingerprint engine + LLM tagger', 'Dedup via SHA-256; assign tags from tag_taxonomy'],
          ['Storage', 'SQLite jokes.db + joke.md export', 'Persist jokes, sources, and crawl progress'],
        ]
      ),
      spacer(),

      h2('2.1 Source URL Examples'),
      p('Real thread URLs verified against the live agent fetcher. Direct HTML scraping fails for both forums (LIHKG is an SPA shell, HKGolden desktop is JS-rendered) — the agent uses LIHKG\'s JSON API and HKGolden\'s mobile site instead.'),
      spacer(),
      makeTable(
        ['Platform', 'Fetched URL', 'Total Pages'],
        [
          ['LIHKG (JSON API)', 'https://lihkg.com/api_v2/thread/596076/page/1', '36'],
          ['LIHKG (JSON API)', 'https://lihkg.com/api_v2/thread/34189/page/1', '31'],
          ['HKGolden (mobile)', 'https://md.hkgolden.com/view.aspx?message=5191089&page=1', '8 (was 29 on desktop)'],
        ]
      ),
      spacer(),
      p('URL pattern notes:'),
      bullet('LIHKG: source_ref stored as https://lihkg.com/thread/{id}/page/{N}; agent fetches via /api_v2/thread/{id}/page/{N} with X-LI-DEVICE: android header.'),
      bullet('HKGolden: source_ref stored as https://md.hkgolden.com/view.aspx?message={id}&page={N} (matches existing user data and what we actually fetch).'),
      bullet('Inputs like https://forum.hkgolden.com/thread/{id}/page/{N} are accepted and rewritten internally to the md.hkgolden.com form.'),
      bullet('Always strip the /page/{N} or &page={N} segment before storing into source_threads.thread_url.'),
      spacer(),

      // ── 3. Database ─────────────────────────────────────────────────────────
      h1('3. Database Design'),
      p('All persistent state lives in a single SQLite file. The schema has five tables, each with a specific responsibility.'),
      spacer(),

      h2('3.1 Table Summary'),
      makeTable(
        ['Table', 'Purpose', 'Key Columns'],
        [
          ['jokes', 'Master joke store — one row per unique joke', 'id, canonical_text, display_text, fingerprint, tags, status'],
          ['joke_sources', 'Raw extraction log (forensic record)', 'joke_id, raw_text, source_ref, imported_at'],
          ['source_threads', 'Forum crawl progress tracker', 'thread_url, reviewed_pages, total_pages, status'],
          ['tag_taxonomy', 'Valid tag registry (LLM reads from here)', 'tag, description'],
          ['meta', 'Agent key-value state store', 'key, value'],
        ]
      ),
      spacer(),

      h2('3.2 jokes Table — Column Reference'),
      makeTable(
        ['Column', 'Type', 'Agent Usage'],
        [
          ['id', 'TEXT PK', 'J000001 format; auto-incremented from MAX(id)'],
          ['canonical_text', 'TEXT', 'Normalised text (trimmed whitespace); input to SHA-256 fingerprint'],
          ['display_text', 'TEXT', 'Verbatim original text preserved exactly as extracted'],
          ['fingerprint', 'TEXT UNIQUE', 'SHA-256(canonical_text); SELECT before every INSERT for dedup'],
          ['source_type', 'TEXT', 'Platform label: lihkg | hkgolden | other'],
          ['source_ref', 'TEXT', 'Full page URL where the joke was found'],
          ['source_date', 'TEXT', 'ISO date of the fetch run'],
          ['tags', 'TEXT', 'Comma-separated tags from tag_taxonomy; set by LLM after extraction'],
          ['status', 'TEXT', 'active (default) | retired'],
          ['created_at', 'TEXT NOT NULL', 'ISO 8601 timestamp set on INSERT — date the joke was added to the DB; never updated after'],
          ['updated_at', 'TEXT NOT NULL', 'ISO 8601 timestamp; refreshed whenever any column on this row changes (tags, status, etc.)'],
        ]
      ),
      spacer(),

      h2('3.3 source_threads Table — Crawl Progress'),
      p('Tracks exactly how far the agent has crawled each forum thread. This prevents re-fetching pages already processed and makes progress visible at a glance.'),
      spacer(),
      makeTable(
        ['Column', 'Type', 'Agent Usage'],
        [
          ['thread_url', 'TEXT UNIQUE', 'Base thread URL — strip /page/N before inserting'],
          ['platform', 'TEXT', 'lihkg | hkgolden | other'],
          ['total_pages', 'INTEGER', 'Detected from pagination HTML on first page fetch; NULL until known'],
          ['reviewed_pages', 'INTEGER', 'Incremented by 1 after each page is fully processed'],
          ['status', 'TEXT', 'pending → in_progress → exhausted'],
          ['last_fetched_at', 'TEXT', 'Updated to now() after each page fetch'],
        ]
      ),
      spacer(),
      p('Progress query:'),
      code("SELECT platform,"),
      code("       substr(thread_url,1,55) AS thread,"),
      code("       reviewed_pages || ' / ' || COALESCE(CAST(total_pages AS TEXT), '?') AS progress,"),
      code("       status"),
      code("FROM source_threads"),
      code("ORDER BY status != 'exhausted', platform;"),
      spacer(),

      h2('3.4 tag_taxonomy Table — Tag Registry'),
      p('The LLM must query this table at runtime to get the valid tag list. Tags are never hardcoded in the prompt.'),
      spacer(),
      makeTable(
        ['Tag', 'Description'],
        [
          ['黃色笑話', 'Adult/dirty jokes — sexual innuendo or explicit content'],
          ['老少皆宜', 'Clean, family-friendly — safe for all ages'],
          ['攪笑IQ題', 'Riddle or brain-teaser format with a funny answer'],
          ['冷笑話', 'Dry/deadpan humour — the punchline lands quietly'],
          ['小明笑話', 'Classic 小明 joke series'],
          ['諧音笑話', 'Wordplay or homophone-based puns'],
          ['黑色幽默', 'Dark humour — morbid or absurdist punchlines'],
          ['動物笑話', 'Animals as main characters or subject'],
          ['學校笑話', 'School / teacher-student setting'],
          ['職場笑話', 'Workplace or boss-employee setting'],
          ['夫妻笑話', 'Marriage, couple, or relationship jokes'],
          ['爸爸笑話', 'Classic dad-joke style (groan-worthy puns)'],
          ['自我貶低', 'Self-deprecating humour'],
          ['鬼馬笑話', 'Witty, playful, or clever jokes (廣東話 鬼馬 style)'],
          ['其他笑話', 'Fallback — does not fit any category above'],
        ]
      ),
      spacer(),

      // ── 4. Agent Modules ────────────────────────────────────────────────────
      h1('4. Agent Modules'),

      h2('Module A — Discovery'),
      p('Responsibility: find new joke thread URLs and register them.'),
      spacer(),
      makeTable(
        ['Step', 'Action'],
        [
          ['1', 'Rotate through Google search keyword pool'],
          ['2', 'Parse search results for forum thread URLs (LIHKG, HKGolden, other HK forums)'],
          ['3', 'For each new thread: strip page suffix, INSERT OR IGNORE into source_threads (status=pending)'],
          ['4', 'Log discovery method in discovered_via column'],
        ]
      ),
      spacer(),

      h2('Module B — Extraction'),
      p('Responsibility: fetch forum pages and extract joke text blocks.'),
      spacer(),
      makeTable(
        ['Step', 'Action'],
        [
          ['1', 'Query source_threads WHERE status != "exhausted"'],
          ['2', 'Compute next_page = reviewed_pages + 1'],
          ['3', 'Fetch page content via HTTP'],
          ['4', 'On first page: detect total_pages from pagination; UPDATE source_threads'],
          ['5', 'Pass raw page content to LLM for joke boundary detection'],
          ['6', 'LLM returns list of self-contained joke text blocks; user replies discarded'],
          ['7', 'UPDATE source_threads: reviewed_pages += 1, last_fetched_at = now()'],
          ['8', 'If reviewed_pages >= total_pages: set status = "exhausted"'],
        ]
      ),
      spacer(),

      h2('Module C — Processing (Dedup + Tagging)'),
      p('Responsibility: fingerprint check and LLM classification before storage.'),
      spacer(),
      makeTable(
        ['Step', 'Action'],
        [
          ['1', 'Normalise extracted text (trim whitespace, normalise line breaks) → canonical_text'],
          ['2', 'Compute fingerprint = sha256(canonical_text)'],
          ['3', 'SELECT 1 FROM jokes WHERE fingerprint = ? — if found, skip'],
          ['4', 'SELECT tag FROM tag_taxonomy — pass list to LLM tagging prompt'],
          ['5', 'LLM returns comma-separated tags'],
          ['6', 'Validate: every returned tag must exist in tag_taxonomy'],
          ['7', 'INSERT INTO jokes (all columns)'],
          ['8', 'INSERT INTO joke_sources (raw_text = pre-normalisation text)'],
          ['9', 'Append to joke.md export'],
        ]
      ),
      spacer(),

      // ── 5. Operating Modes ──────────────────────────────────────────────────
      h1('5. Operating Modes'),
      p('The agent runs in one of two modes. Live mode is fully automated. Test mode pauses for human approval before any DB write — used to spot-check extraction quality and tag accuracy without polluting jokes.db.'),
      spacer(),

      h2('5.1 Mode Comparison'),
      makeTable(
        ['Step', 'Live Mode', 'Test Mode'],
        [
          ['Discover & fetch', 'Yes', 'Yes'],
          ['LLM boundary detection', 'Yes', 'Yes'],
          ['Fingerprint dedup vs jokes.db', 'Yes', 'Yes'],
          ['LLM tagging', 'Yes', 'Yes (pre-review, so user sees proposed tags)'],
          ['INSERT INTO jokes', 'Automatic', 'Only after user approval'],
          ['INSERT INTO joke_sources', 'Automatic', 'Only after user approval'],
          ['Append to joke.md / joke_source.md', 'Automatic', 'Only after user approval'],
          ['source_threads.reviewed_pages increment', 'Automatic', 'Only on save; no-op on abandon'],
        ]
      ),
      spacer(),

      h2('5.2 Test Mode Invocation'),
      code('fetch <N> jokes --review'),
      code('# or via env flag:'),
      code('JOKE_AGENT_MODE=test'),
      p('N defaults to 5 if not specified.'),
      spacer(),

      h2('5.3 Test Mode Flow'),
      makeTable(
        ['Step', 'Action'],
        [
          ['1', 'Run normal pipeline: Discover → Extract → Dedup → Tag'],
          ['2', 'source_threads pages are FETCHED but reviewed_pages is NOT incremented yet'],
          ['3', 'Dedup against jokes.fingerprint runs as usual — already-saved jokes never appear in review'],
          ['4', 'LLM tagging runs so the user sees proposed tags during review'],
          ['5', 'Candidates held in memory only — no DB writes'],
          ['6', 'Continue crawling until N unique candidates are collected'],
          ['7', 'Print all N candidates to terminal in review format'],
          ['8', 'Prompt user: [a]ll save / [n]one (abandon) / [p]er-joke / [q]uit'],
          ['9a', 'On SAVE: atomic commit — INSERT jokes + joke_sources, append markdown, increment reviewed_pages, update last_fetched_at'],
          ['9b', 'On ABANDON: discard candidates, no DB writes, reviewed_pages NOT incremented (same pages refetched next run)'],
        ]
      ),
      spacer(),

      h2('5.4 Terminal Review Format'),
      p('Each candidate is printed as a self-contained block:'),
      code('═════════════════════════════════════════════════'),
      code('  Candidate 1 of 5'),
      code('═════════════════════════════════════════════════'),
      code('  Source     : https://lihkg.com/thread/596076/page/14'),
      code('  Platform   : lihkg'),
      code('  Tags (LLM) : 諧音笑話, 鬼馬笑話'),
      code('  Fingerprint: 3a9f...e21c  (not yet in DB)'),
      code('─────────────────────────────────────────────────'),
      code('  學校中文口試'),
      code('  老師：時間夠 同學汁埋啲野可以走'),
      code('  學生：（呼），老師咁我走啦，thank you'),
      code('  老師：中文口試你講咩英文'),
      code('  學生：啊係喎，sorry'),
      code('═════════════════════════════════════════════════'),
      spacer(),
      p('After all N candidates are displayed:'),
      code('Decision? [a]ll save / [n]one (abandon) / [p]er-joke / [q]uit:'),
      spacer(),
      p('If [p] is chosen, the agent prompts per-joke:'),
      code('Candidate 1: save? [y/n]:'),
      code('Candidate 2: save? [y/n]:'),
      spacer(),

      h2('5.5 Test Mode Rules'),
      makeTable(
        ['Rule', 'Detail'],
        [
          ['No silent writes', 'No row is inserted, updated, or appended without explicit user approval'],
          ['Same dedup logic', 'jokes.fingerprint is checked during candidate gathering — duplicates are skipped before reaching review'],
          ['Tagging pre-review', 'LLM tagging runs before display so the user can verify proposed tags'],
          ['Atomic commit on save', 'DB INSERTs, markdown appends, and reviewed_pages updates run in one transaction'],
          ['Quit is safe', '[q] at the prompt has identical effect to abandon — zero side effects'],
          ['Trade-off', 'Abandoning wastes the fetch+LLM cost, since the same pages will be re-crawled next run. Use per-joke mode to keep the good ones'],
        ]
      ),
      spacer(),

      // ── 6. LLM Configuration & Roles ────────────────────────────────────────
      h1('6. LLM Configuration & Roles'),

      h2('6.1 LLM Access — codex-ollama-bridge'),
      p('The agent reaches the LLM through the locally-running codex-ollama-bridge, which exposes OpenClaw\'s OAuth-authenticated openai-codex provider as a standard OpenAI-compatible HTTP endpoint. The bridge reuses the OpenClaw OAuth profile and auto-refreshes tokens — no API key, no per-call setup.'),
      spacer(),
      makeTable(
        ['Setting', 'Value'],
        [
          ['Bridge service', 'codex-ollama-bridge.service (user systemd, port 11540)'],
          ['Base URL', 'http://127.0.0.1:11540/v1'],
          ['Protocol', 'OpenAI Chat Completions — POST /v1/chat/completions'],
          ['Model ID', 'openai-codex/gpt-5.5'],
          ['API key', 'Any non-empty string (ignored by bridge)'],
          ['Streaming', 'Supported via stream:true (SSE)'],
          ['Auth', 'OpenClaw OAuth profile — auto-refreshing'],
          ['Fallback bridge', 'nvidia-ollama-bridge (port 11545, google/gemma-4-31b-it) — same OpenAI protocol'],
        ]
      ),
      spacer(),
      p('Why this route was chosen over openclaw capability model run:'),
      bullet('The native CLI currently fails for openai-codex/gpt-5.5 ("No text output returned").'),
      bullet('Bridge succeeds end-to-end in ~7–8s for the same model.'),
      bullet('Standard HTTP means the joke agent uses the OpenAI Python SDK directly — no subprocess, no CLI parsing.'),
      bullet('Provider-swap requires only a base_url change.'),
      spacer(),
      p('Python usage (reference):'),
      code('from openai import OpenAI'),
      code(''),
      code('client = OpenAI('),
      code('    base_url="http://127.0.0.1:11540/v1",'),
      code('    api_key="codex-bridge",  # any non-empty string'),
      code(')'),
      code(''),
      code('resp = client.chat.completions.create('),
      code('    model="openai-codex/gpt-5.5",'),
      code('    messages=[{"role": "user", "content": prompt_text}],'),
      code('    stream=False,'),
      code(')'),
      code('print(resp.choices[0].message.content)'),
      spacer(),
      p('Pre-run health check:'),
      code('curl -sS http://127.0.0.1:11540/v1/models | head -1'),
      p('If the bridge is down: systemctl --user restart codex-ollama-bridge'),
      spacer(),

      h2('6.2 Joke Boundary Detection'),
      p('Given raw forum page content, the LLM identifies which contiguous lines form a complete, self-contained joke and which are user replies or commentary.'),
      spacer(),
      makeTable(
        ['Input', 'Output'],
        [
          ['Raw thread page content (all posts on the page)', 'List of joke text blocks, each a contiguous extract'],
        ]
      ),
      spacer(),
      p('Decision rules:'),
      bullet('Does the block have a setup and a punchline?'),
      bullet('Is it self-contained without the surrounding context?'),
      bullet('Are the remaining lines reactions (emotes, ":o)", commentary) rather than part of the joke?'),
      spacer(),
      p('Example — LIHKG thread 34189, page 28:'),
      code('學校中文口試'),
      code('老師：時間夠 同學汁埋啲野可以走'),
      code('學生：（呼），老師咁我走啦，thank you'),
      code('老師：中文口試你講咩英文'),
      code('學生：啊係喎，sorry'),
      p('→ Extract (complete joke)'),
      spacer(),
      code('汁你老母:o) :o) :o)'),
      code('汁唔係5p都屌:-( :-('),
      p('→ Discard (user replies)'),
      spacer(),

      h2('6.3 Tag Classification'),
      p('Given a joke\'s display_text and the list of valid tags from tag_taxonomy, the LLM assigns one or more tags.'),
      spacer(),
      makeTable(
        ['Property', 'Rule'],
        [
          ['Tag source', 'Must query: SELECT tag FROM tag_taxonomy — never hardcode'],
          ['Multiple tags', 'Allowed; return as comma-separated string'],
          ['Fallback', 'Use 其他笑話 if no other tag applies'],
          ['Basis', 'Joke content only — ignore thread title or source URL'],
          ['Output format', 'ONLY the comma-separated tags, no explanation'],
        ]
      ),
      spacer(),
      p('Prompt template:'),
      code('You are a joke classifier for a Cantonese/Chinese joke database.'),
      code('Valid tags: {SELECT tag FROM tag_taxonomy}'),
      code(''),
      code('Assign one or more tags to the joke below.'),
      code('Return ONLY the comma-separated tags. No explanation.'),
      code(''),
      code('Joke:'),
      code('{display_text}'),
      spacer(),

      // ── 6. Critical Rules ───────────────────────────────────────────────────
      h1('7. Critical Rules (Non-Negotiable)'),
      spacer(),
      makeTable(
        ['Rule', 'Detail'],
        [
          ['No summarising', 'Store the joke exactly as posted. Never rewrite or condense.'],
          ['No punchline alteration', 'The original punchline must be preserved character-for-character.'],
          ['No duplicates', 'Check jokes.fingerprint before every INSERT. Reject any match.'],
          ['Original text only', 'If the original cannot be extracted cleanly, skip that joke.'],
          ['Source always recorded', 'Every stored joke must have its source URL in joke_sources.'],
          ['Tags from DB only', 'LLM must query tag_taxonomy — never use hardcoded tag lists.'],
          ['Test mode = no silent writes', 'In test mode, no DB row or markdown line is written without explicit user approval.'],
        ]
      ),
      spacer(),

      // ── 7. Implementation Plan ──────────────────────────────────────────────
      h1('8. Implementation Plan'),

      h2('Phase 1 — Foundation (Week 1)'),
      makeTable(
        ['Task', 'Detail'],
        [
          ['1.1 DB migration', 'Verify all 5 tables exist; run backfill of English tags to Chinese'],
          ['1.2 Fingerprint backfill', 'Compute SHA-256 fingerprints for any jokes with empty fingerprint column'],
          ['1.3 source_threads seed', 'Confirm existing 6 threads are correctly seeded from joke_source.md'],
          ['1.4 Tag taxonomy', 'Confirm tag_taxonomy has all 15 rows; add/remove tags if needed'],
          ['1.5 LLM client wrapper', 'Build a thin OpenAI SDK client pointing at http://127.0.0.1:11540/v1 with model openai-codex/gpt-5.5; include health check + retry; expose chat() helper used by all downstream LLM calls'],
          ['1.6 Bridge dependency check', 'On agent startup, verify codex-ollama-bridge is reachable; surface clear error if down (with restart hint)'],
        ]
      ),
      spacer(),

      h2('Phase 2 — Discovery & Extraction (Week 2)'),
      makeTable(
        ['Task', 'Detail'],
        [
          ['2.1 Google Search module', 'Implement keyword rotation, URL parsing, source_threads INSERT'],
          ['2.2 HTTP fetcher', 'Fetch forum pages; handle pagination detection for LIHKG and HKGolden'],
          ['2.3 LLM boundary detector', 'Prompt design, output parsing, raw_text capture'],
          ['2.4 source_threads updater', 'reviewed_pages increment, status transition logic'],
        ]
      ),
      spacer(),

      h2('Phase 3 — Processing & Storage (Week 3)'),
      p('Note: writes in this phase must be gated by mode — in test mode they are deferred until user approval (see Phase 4).'),
      makeTable(
        ['Task', 'Detail'],
        [
          ['3.1 Canonicaliser', 'Normalise whitespace/line breaks to produce canonical_text'],
          ['3.2 Fingerprint engine', 'sha256(canonical_text) dedup check before every INSERT'],
          ['3.3 LLM tagger', 'Query tag_taxonomy, build prompt, validate returned tags, store'],
          ['3.4 jokes + joke_sources INSERT', 'Write both rows atomically; gated by mode (live writes immediately, test mode defers)'],
          ['3.5 joke.md exporter', 'Append new jokes in Source / Tags / Original Text format'],
          ['3.6 Mode flag plumbing', 'Read JOKE_AGENT_MODE / --review CLI flag; expose live | test to downstream modules'],
        ]
      ),
      spacer(),

      h2('Phase 4 — Test Mode CLI (Week 4)'),
      p('Implements the Operating Modes spec from Section 5. Gates all DB and markdown writes behind explicit user approval.'),
      makeTable(
        ['Task', 'Detail'],
        [
          ['4.1 CLI entry point', 'Accept "fetch <N> jokes --review" command; default N=5; also support JOKE_AGENT_MODE=test env flag'],
          ['4.2 Candidate buffer', 'In-memory list holding parsed jokes (canonical_text, display_text, tags, fingerprint, source_ref) before any write'],
          ['4.3 Crawl-until-N loop', 'Continue fetching pages until N unique candidates are gathered; pages fetched but reviewed_pages NOT yet incremented'],
          ['4.4 Terminal renderer', 'Print numbered candidate blocks with source URL, platform, proposed tags, fingerprint preview, verbatim joke text'],
          ['4.5 Decision prompt', 'Prompt: [a]ll save / [n]one (abandon) / [p]er-joke / [q]uit; per-joke loops y/n on each candidate'],
          ['4.6 Atomic save transaction', 'On approval: BEGIN; INSERT jokes + joke_sources, append joke.md + joke_source.md, increment reviewed_pages, update last_fetched_at; COMMIT (rollback on any failure)'],
          ['4.7 Abandon path', 'Discard buffer; verify zero side effects (no DB row, no markdown line, reviewed_pages unchanged)'],
          ['4.8 Quit safety', '[q] at any prompt = same as abandon; SIGINT handler also triggers abandon path'],
          ['4.9 Test-mode tests', 'Verify: dedup against jokes.fingerprint runs pre-review; tags appear pre-review; abandon leaves DB+markdown unchanged; save commits all four artifacts atomically'],
        ]
      ),
      spacer(),

      h2('Phase 5 — Backfill & Hardening (Week 5)'),
      makeTable(
        ['Task', 'Detail'],
        [
          ['5.1 English tag migration', 'One-shot pass: wordplay→諧音笑話, animal→動物笑話, school→學校笑話, iq→攪笑IQ題'],
          ['5.2 LLM re-tag pass', 'Re-classify all 20 untagged / English-tagged jokes'],
          ['5.3 joke_sources audit backfill', 'Identify the 2 jokes missing a joke_sources row; reconstruct or mark as legacy'],
          ['5.4 Error handling', 'Retry logic for HTTP failures; graceful LLM timeout handling'],
          ['5.5 Smoke tests', 'End-to-end test in BOTH modes: live (auto-write) and test (review → save / abandon)'],
        ]
      ),
      spacer(),

      // ── 8. Data Paths ───────────────────────────────────────────────────────
      h1('9. Data Paths'),
      makeTable(
        ['Asset', 'Path'],
        [
          ['SQLite Joke DB', '/home/pi/.openclaw/workspace/state/jokes.db'],
          ['Markdown Export', '/home/pi/.openclaw/workspace/joke.md'],
          ['Source Registry (mirror)', '/home/pi/.openclaw/workspace/joke_source.md'],
          ['Project Folder', '/home/pi/Documents/joke_agent_project/'],
          ['Goal Document', '/home/pi/Documents/joke_agent_project/goal.md'],
        ]
      ),
      spacer(),

      // ── 9. Scope ────────────────────────────────────────────────────────────
      h1('10. Scope Boundaries'),
      makeTable(
        ['In Scope', 'Out of Scope'],
        [
          ['Cantonese jokes (廣東話)', 'Mainland Simplified Chinese jokes'],
          ['Traditional Chinese jokes', 'Image-only memes (no text)'],
          ['Hong Kong vernacular text', 'Political satire without a joke structure'],
          ['Multi-forum discovery', 'Non-Chinese language jokes'],
        ]
      ),
      spacer(),

      // ── footer ──────────────────────────────────────────────────────────────
      new Paragraph({
        children: [new TextRun({
          text: `Generated ${new Date().toISOString().slice(0,10)} — Cantonese Joke Fetching Agent v1.0`,
          size: 16, color: '595959', font: 'Calibri', italics: true,
        })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 400 },
      }),
    ],
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = '/home/pi/Documents/joke_agent_project/Joke_Agent_Architecture.docx';
  fs.writeFileSync(out, buf);
  console.log('Written:', out);
});
