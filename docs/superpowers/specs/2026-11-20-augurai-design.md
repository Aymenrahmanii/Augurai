# Augurai: Design

Date: 2026-11-20
Status: approved

> **Change, 2026-11-20 (after implementation):** the email channel was removed at the owner's request. The morning briefing is written once per local day and shown on the site's home page and archive; the coach writes private proposals to `coach/proposals/` and is reviewed with `/coach-review`. Sections below that mention email (5.7, the Gmail secrets, the email half of the coach) are superseded.

## 1. Intent

Aymen is an ML / data engineer who wants a system that keeps them current with AI and actively makes them better at working with AI, without manual upkeep.

Two jobs, one system:

1. **Stay current (daily).** A morning briefing email, readable in about 5 minutes, plus a website that holds everything: latest models, a "best model for what" benchmark with use cases, rising repos, skills, agents and MCP servers, the people worth following, and AI job-market trends.
2. **Get better (weekly).** A coach that reviews how Aymen actually used Claude Code that week and proposes concrete changes (habits, skills to use or install, `CLAUDE.md` rules), grounded in the practices of people like Matt Pocock and Lauren Tan. Aymen approves every change.

The model benchmark doubles as a quick answer for "which model for this client project?".

**Success looks like:**
- An email arrives every morning without Aymen touching anything, and it's worth reading.
- The website is always fresh (data ≤ 6 hours old) and looks simple and professional.
- New people and repos that rise in the field show up on their own.
- Each week Aymen gets a few specific, applicable suggestions about their own way of working, and their habits measurably change over time.

## 2. Goals, non-goals, anti-goals

**Goals**
- Fully autonomous: runs in the cloud on a schedule, with no human in the loop except approving coach suggestions.
- Covers: models, benchmark + use cases, repos, skills, agents, MCP servers, papers worth knowing, people, practices, jobs.
- Discovers new people and repos automatically and reports what changed.
- Public website (radar) + private email (briefing and coach).
- Free to run: GitHub Actions + Pages for hosting, and Aymen's existing Claude subscription for the LLM work (no API key or API bill).

**Non-goals**
- Real-time push; a 6-hour freshness window is enough.
- X/Twitter and LinkedIn data (no usable free API; scraping is fragile and against their terms).
- Multiple users, accounts, or comments on the site.
- Paid data sources.

**Anti-goals (failure even if it "works")**
- A briefing that takes longer than ~5 minutes to read, or is hype without signal.
- Stale data presented as fresh.
- Private session data (transcripts, coach output) ever reaching the public repo or site.
- A system that needs babysitting: silent breakage, or failures that need manual fixes to recover.

## 3. Constraints

- Runs on GitHub Actions (cloud), so it works while Aymen's PC is off.
- The coach must run locally on Aymen's Windows 11 PC: Claude Code session history (`~/.claude/projects/**/*.jsonl`) exists only there.
- Python 3.12, `uv`, type hints, small functions, `ruff`, `pytest` (Aymen's defaults). Conventional commits.
- **No Claude API key.** All LLM work runs through **Claude Code in headless mode**, using Aymen's Claude subscription:
  - **In the cloud:** the `anthropics/claude-code-action` with the `claude_code_oauth_token` input. The token comes from `claude setup-token` and is stored as the `CLAUDE_CODE_OAUTH_TOKEN` secret.
  - **Locally:** `claude -p` for the coach.

  This draws on Aymen's subscription usage limits, so LLM work is kept to one session per day in the cloud and one per week locally.
- Python code never calls an LLM directly. Python prepares input files, Claude Code writes output files, and Python validates them against pydantic schemas. If the Claude step fails, or its output is invalid, the pipeline still ships the deterministic version.
- Secrets live only in GitHub Actions secrets (cloud) or a local `.env` (coach), never in the repo.
- Available today: git, gh (logged in), uv 0.13, Python 3.12, Node 24.

## 4. Approaches considered

| Approach | Trade-offs | Verdict |
|---|---|---|
| **A. GitHub Actions pipeline**: a Python project whose scheduled workflow fetches fixed sources, ranks them deterministically, enriches once a day with headless Claude Code, commits data files, rebuilds a static site on GitHub Pages and sends the email | Deterministic and testable; data history lives in git; free hosting; you own and maintain the source adapters | **Chosen** |
| B. Claude cloud routines: a scheduled agent researches the web and pushes files | Less code, but each run finds and judges things differently, so the benchmark is inconsistent and hard to test | Rejected |
| C. Local-only scheduled jobs | Stops whenever the PC is off | Rejected |

## 5. Architecture

```
GitHub Actions (cron, every 6h)                     Aymen's PC (weekly)
┌──────────────────────────────────────┐            ┌─────────────────────────────┐
│ collect  → sources/* adapters        │            │ augurai coach               │
│ store    → data/*.json (validated)   │            │  reads ~/.claude sessions,  │
│ rank     → scoring + discovery       │            │  CLAUDE.md, skills          │
│ enrich   → Claude API (cached)       │  practices │  + practices.json (site)    │
│ build    → static site → Pages       │──────────▶│  → proposals (local only)   │
│ brief    → email (morning run only)  │            │  → email                    │
│ commit   → data + briefing to repo   │            │ /coach-review skill applies │
└──────────────────────────────────────┘            │ approved changes            │
                                                    └─────────────────────────────┘
```

One repo, one Python package `augurai` with a CLI (`augurai collect | rank | enrich | build | brief | coach | run`). `augurai run` does the full cloud pipeline.

### 5.1 Repository layout (proposed)

```
src/augurai/
  sources/        one module per source, all implementing the same Source interface
  models.py       pydantic schemas for every data file
  store.py        read/write data/*.json, append-only snapshots
  rank.py         scoring, velocity, "best at" categories
  discover.py     people/repo discovery and promotion rules
  enrich.py       prepare work/enrich_input.json; validate + merge work/enrich_output.json
  site/           Jinja2 templates, static CSS/JS
  build.py        render site to _site/
  email.py        render + send briefing
  coach/          local-only: transcript reader, condenser, redactor, proposer
  cli.py
data/             committed, public: models, repos, mcps, skills, people, practices, jobs, health, runs
briefings/        committed: YYYY-MM-DD.md
config/augurai.toml seed people, source settings, thresholds, enrichment caps, schedule, timezone
prompts/          enrich.md, coach.md (prompts for headless Claude Code)
.github/workflows/augurai.yml, ci.yml
.claude/skills/coach-review/SKILL.md
tests/
```

### 5.2 Data model (pydantic, stored as JSON)

- **Model**: id, name, provider, released, open_weights, context_window, price_in/out per 1M, modalities, scores `{source: {metric: value}}`, `best_at: [category]`, `use_cases: [str]`, `avoid_for: [str]`, links, first_seen.
- **Repo / Skill / MCPServer / Agent**: id, name, url, owner, description, kind, stars, star_snapshots `[(date, stars)]`, velocity_7d, first_seen, summary.
- **Person**: id, name, links (github, blog/RSS, YouTube, site), status `seed | followed | rising | dormant`, score, score_history, why_follow, what_to_learn, recent_work.
- **Practice**: id, title, principle, how_to_apply, person_id, source_url, related_skill, tags, first_seen, reinforced_by `[source_url]`.
- **JobSnapshot**: month, source, total_posts, keyword_counts `{keyword: n}`, notable_roles.
- **Health**: per source: last_success, last_error, consecutive_failures.
- **Runs**: per run: timestamp, sources ok/failed, enrichment ran or skipped (and why).

"Best at" categories: coding, agentic/tool use, reasoning/math, long context, vision/multimodal, speed, cost-efficiency, open-weights.

### 5.3 Sources (each must be verified in the first spike task)

| Area | Sources |
|---|---|
| New models + pricing | OpenRouter models API, Hugging Face Hub API (trending), provider news/RSS (Anthropic, OpenAI, Google DeepMind, Meta, Mistral, DeepSeek, Qwen) |
| Benchmarks | Artificial Analysis API (free key), LMArena leaderboard data if programmatically available; otherwise drop it |
| Repos | GitHub search API (recent repos by stars across AI topics) + daily star snapshots for velocity |
| Skills / agents | GitHub search for `SKILL.md` repos and agent/skill topics; Claude Code plugin marketplaces listed in config |
| MCP servers | Official MCP registry API |
| Papers | Hugging Face daily papers API |
| Community | Hacker News Algolia API (AI stories above a points threshold); RSS from people's blogs, Latent Space, Simon Willison |
| People | GitHub user activity + RSS + YouTube channel RSS for followed people |
| Jobs | Three markets shown separately (details below the table) |

**Job markets:**
- **Global/remote:** HN "Who is hiring" threads (Algolia) and the RemoteOK API.
- **France/EU,** where many Tunisian engineers work with clients: the Adzuna API with country `fr` (free key). Adzuna does not cover Tunisia.
- **Tunisia:** one local job board, best-effort, only if its terms and robots.txt allow it (checked in the spike). Otherwise this market is dropped and the site says so.

Every source is an isolated adapter: a failure in one never fails the run. Failures are recorded in `data/health.json`, shown on the site, and listed in the email after 3 consecutive failures.

### 5.4 Ranking and discovery (autonomous)

- **Repos/skills/MCPs:** rank by star velocity (7-day) with a novelty bonus; the top N per kind are "rising".
- **People:** candidates come from owners of top-velocity repos, authors of top HN items, and people repeatedly linked by followed people. The score is a weighted 30-day sum of signals. A candidate who stays above the threshold for 2 consecutive runs is auto-promoted to `followed` (so one-day spikes don't count). Anyone inactive for 90 days becomes `dormant`. **Seed people are never demoted.**
- Every promotion or demotion is listed in the next email's "What changed" section.

Seed people: Matt Pocock, Lauren Tan, Simon Willison, Armin Ronacher, Geoffrey Huntley, Boris Cherny, Jesse Vincent, Harrison Chase, Hamel Husain, Shreya Shankar, Eugene Yan, Jason Liu, Andrej Karpathy, Chip Huyen, Sebastian Raschka, swyx.

### 5.5 LLM enrichment (headless Claude Code, once per day)

**The every-6-hours runs** are pure Python: collect, rank, discover, build. There is no LLM involved.

**The morning run** adds one Claude Code session:
1. Python writes `work/enrich_input.json`. It holds only new or changed items: the day's ranked deltas, new work by followed people, models whose scores changed, and the existing practice titles.
2. `anthropics/claude-code-action` runs with a fixed prompt from `prompts/enrich.md`. Its allowed tools are limited to reading `work/` and writing `work/enrich_output.json`.
3. That output contains:
   - **Summaries** of new items (≤ 2 sentences each), cached by content hash so nothing is summarized twice.
   - **Practices:** 0–3 per piece of new work by followed people, each either a new practice or a reinforcement of an existing one.
   - **Model use cases**, `best_at` and `avoid_for`, for new or re-scored models.
   - **The briefing text**, ≤ ~600 words.
4. Python validates the output against pydantic schemas, merges it into `data/`, then builds and sends.

**If anything fails** (token expired, usage limit hit, invalid output), the run continues without enrichment. The email and site show the ranked lists without summaries, and the email says so.

**Input size:** `work/enrich_input.json` is capped (config `max_enrich_items`), so the daily session stays small on subscription usage.

**Token expiry:** `data/health.json` records when the token was last used successfully. A failed Claude step appears in the email footer with the fix (`claude setup-token`, then update the secret).

### 5.6 Website

Static HTML from Jinja2 templates with hand-written CSS and a little vanilla JS for table filtering. There's no Node build step; Python-only keeps it maintainable.

Pages:
- **Today**: the latest briefing and what changed.
- **Models**: benchmark table, filterable by "best at", plus a detail page per model with use cases and what to avoid it for.
- **Ecosystem**: rising repos, skills, agents, MCP servers.
- **People**: followed and rising, each with what to learn from them and their recent work.
- **Playbook**: the practice library, filterable by person, tag and related skill.
- **Jobs**: trend charts of keyword demand over time.
- **Archive**: past briefings.
- **About**: how it works, plus source freshness/health.

Visual direction is set with the Impeccable and UI/UX Pro Max skills during implementation. The target is simple and professional, with light and dark themes, readable on a phone.

### 5.7 Email

- Sent by the run closest to `briefing_hour_local` in the configured timezone.
- HTML plus plain-text versions, rendered from the same templates.
- Sent via Gmail SMTP with an app password (secrets `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `BRIEFING_TO`).
- Sections, in this order:
  1. What changed (models, benchmark moves, rising repos/MCPs/skills, people promoted)
  2. From the people you follow
  3. One practice to try today
  4. Jobs pulse (weekly, on Mondays)
  5. Links to the site

### 5.8 Coach (local, private)

- `augurai coach`, scheduled by Windows Task Scheduler weekly (Sunday 10:00, "run as soon as possible after a missed start").
- **Reads** the last 7 days of `~/.claude/projects/**/*.jsonl`, `~/.claude/CLAUDE.md`, and the list of installed skills.
- **Condenses** them into a compact activity profile:
  - user prompts, truncated
  - which skills and slash commands were used
  - tool-use counts
  - session lengths
  - signals such as "planned before building", "ran tests", "used subagents"
- **Redacts** secret-like strings before anything leaves the machine.
- **Fetches** the latest `practices.json` from the public site.
- **Runs** `claude -p` with `prompts/coach.md` over the condensed profile, asking for 3–5 proposals as JSON. Python validates that JSON against a schema. This uses Aymen's local Claude Code login, so no API key or token setup is needed. Each proposal has:
  - an observation from the sessions
  - the matching practice and its source person
  - the concrete change: a habit, a skill to use or install, or a `CLAUDE.md` edit
  - the exact command or diff to apply it
- **Writes** them to `coach/proposals/YYYY-Www.md`. This path is gitignored and never committed.
- **Emails** the proposals to Aymen.
- **Applying them:** the `/coach-review` Claude Code skill walks through the proposals one by one and applies only the ones Aymen approves.
- **Privacy:** transcripts and proposals are never committed or published. They go only to the Anthropic API and Aymen's inbox.

### 5.9 Reliability and operations

- Workflow cron every 6 hours. The data commits each run keep the repo active, which stops GitHub from disabling the scheduled workflow.
- A run that changes nothing makes no commit. Retries with backoff per source.
- If the workflow itself fails, GitHub's own failure email notifies Aymen.
- CI on each push: ruff, pytest, schema validation of `data/`, and a site-build smoke test.

### 5.10 Testing

- Source adapters are tested against recorded fixtures; CI tests make no network calls.
- Enrichment is tested at the file boundary: tests feed recorded `enrich_output.json` fixtures (valid, invalid and missing) and check the merge and the fallback. No test calls Claude.
- Ranking, discovery promotion rules, redaction and transcript condensing are unit-tested.
- Site build smoke test: every page renders, and all internal links resolve.

## 6. Decided by Aymen

- Coach included (not just a reading feed).
- Email briefing plus a website.
- GitHub Actions pipeline (approach A).
- Fully autonomous discovery: no approval needed for new people or repos.
- Seed people list as above.
- Site design via the Impeccable and UI/UX Pro Max skills.
- The plan will be implemented by Claude Sonnet 5.5.

## 7. Claude's calls (correct any of these)

- Public site and repo; coach output private.
- 6-hour refresh; email once each morning.
- Python + Jinja2 static site with no JS framework.
- Gmail SMTP with an app password for email.
- Auto-promote people after 2 consecutive runs above threshold; dormant after 90 days; seeds never demoted.
- `/coach-review` skill as the approval mechanism.
- Coach runs via Windows Task Scheduler, Sunday 10:00.

- No API key: LLM work runs through headless Claude Code on Aymen's subscription (a cloud OAuth token plus local `claude -p`).
- Name: **Augurai**. Python package `augurai`, CLI `augurai`. Repo: https://github.com/Aymenrahmanii/Augurai (public, currently empty). Site: https://aymenrahmanii.github.io/Augurai/.
- Location: Tunis. Timezone `Africa/Tunis` (UTC+1, no DST); the briefing is sent at 07:00 local (06:00 UTC).

## 8. One-time setup Aymen does (the builder writes the instructions, never handles the values)

- `claude setup-token` → GitHub secret `CLAUDE_CODE_OAUTH_TOKEN`.
- A Gmail app password → secrets `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `BRIEFING_TO`.
- A free Artificial Analysis API key → `ARTIFICIAL_ANALYSIS_API_KEY`.
- A free Adzuna API key → `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`.
- Enabling GitHub Pages (source: GitHub Actions).

Any source whose key is missing is skipped and reported in `health.json`; the run carries on without it.

## 8b. Open questions for Aymen

1. ~~Subscription token in the cloud~~: approved by Aymen (2026-11-20).
2. ~~Location~~: Tunis (2026-11-20).

## 9. Left to the builder

- Exact scoring weights and thresholds (start simple, tune after a week of data).
- Exact endpoints and parameters per source, verified in the spike.
- Visual design details, within the direction in 5.6.
