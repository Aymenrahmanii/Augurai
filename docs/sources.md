# Verified data sources (Task 2, 2026-11-20)

All endpoints below were called live on 2026-11-20. Fixtures live in `tests/fixtures/<dir>/`
(trimmed to at most 30 items; no secrets). Fixtures marked **synthetic** were hand-written to match the
documented shape because no key exists yet. HTTP User-Agent: `augurai/0.1`.

## Models and benchmarks

| Source | Endpoint | Auth | Fields used | Fixture |
|---|---|---|---|---|
| OpenRouter | `GET https://openrouter.ai/api/v1/models` returns `{data: [...]}` | none | `id` (`vendor/name`), `name`, `created` (epoch s), `context_length`, `pricing.prompt` / `pricing.completion` (USD **per token**, strings; multiply by 1e6), `architecture.input_modalities`, `hugging_face_id` | `openrouter/models.json` |
| Hugging Face trending models | `GET https://huggingface.co/api/models?sort=trendingScore&limit=50` returns a list | none | `id`, `trendingScore`, `likes`, `downloads`, `pipeline_tag`, `createdAt`, `tags` | `huggingface/models.json` |
| Artificial Analysis (free tier) | `GET https://artificialanalysis.ai/api/v2/language/models/free` returns `{tier, pagination, data}` | header `x-api-key: $ARTIFICIAL_ANALYSIS_API_KEY` | `id`, `name`, `slug`, `release_date`, `model_creator.name`, `evaluations.artificial_analysis_{intelligence,coding,agentic}_index` (coding and agentic are **deprecated** but still returned; they may become null), `pricing.price_1m_{input,output}_tokens`, `performance_v3.mean_output_tokens_per_second` | `aa/models_free.json` (**synthetic**; schema taken from the OpenAPI spec at `/api/v2/openapi`) |
| LMArena | no usable machine-readable endpoint (`lmarena.ai/leaderboard` returns 403 to bots; the HF dataset is parquet) | | | **dropped** |

- AA rate limit: 100 requests per 24h window on the free plan. One request per run is fine (follow `pagination.has_more`).
- AA **requires attribution**: the site footer and About page must link to https://artificialanalysis.ai/.
- Metric names stored under `Model.scores["artificial-analysis"]`: `intelligence`, `coding`, `agentic`, `output_tps`.

## Repos, skills, agents, MCP

| Source | Endpoint | Auth | Notes | Fixture |
|---|---|---|---|---|
| GitHub repo search | `GET https://api.github.com/search/repositories?q=topic:<t>+created:>YYYY-MM-DD&sort=stars&per_page=30` | optional `GITHUB_TOKEN` (search: 10 req/min unauthenticated, 30/min with token) | fields: `full_name`, `html_url`, `description`, `created_at`, `stargazers_count`, `topics`, `owner.login`. Topics: `llm`, `ai-agents`, `mcp`, `claude-code`, `rag`, `llmops` | `github/search_repos.json` |
| GitHub skill repos (topic) | same endpoint, `q=topic:claude-code-skills` | optional token | fallback when code search is unavailable | `github/search_skills.json` |
| GitHub code search for `SKILL.md` | `GET https://api.github.com/search/code?q=filename:SKILL.md` | **token required** (401 without) | in CI `GITHUB_TOKEN` works; locally the adapter must skip gracefully on 401 and fall back to the topic search | `github/search_code_skills.json` |
| MCP registry | `GET https://registry.modelcontextprotocol.io/v0/servers?limit=30` returns `{servers: [{server: {name, description, title, version, remotes, ...}, _meta}], metadata: {nextCursor, count}}` | none | cursor pagination (`cursor=<nextCursor>`); `_meta["io.modelcontextprotocol.registry/official"].publishedAt` gives the publish time | `mcp/servers.json` |
| GitHub user events | `GET https://api.github.com/users/{login}/events/public?per_page=30` | optional token | types seen: `CreateEvent`, `PushEvent`, `PullRequestEvent`, `DeleteEvent`. `ReleaseEvent` exists but did not appear for the sampled user. Use `CreateEvent` (`payload.ref_type == "repository"`) and `ReleaseEvent` | `github/events_mattpocock.json` |

## Community

| Source | Endpoint | Notes | Fixture |
|---|---|---|---|
| HN Algolia stories | `GET https://hn.algolia.com/api/v1/search_by_date?tags=story&numericFilters=points>100&query=<q>&hitsPerPage=30` | fields: `objectID`, `title`, `url`, `points`, `author`, `num_comments`, `created_at`. No key | `hn/stories.json` |
| HF daily papers | `GET https://huggingface.co/api/daily_papers` returns a list of `{paper: {id, title, upvotes}, title, summary, publishedAt, numComments}` | no key | `hfpapers/daily.json` |
| RSS/Atom feeds | via `feedparser` | verified list below | `feeds/simonwillison.atom` |

### Verified feeds (all returned 200 and valid RSS/Atom)

`https://www.aihero.dev/rss.xml` (Matt Pocock), `https://simonwillison.net/atom/everything/`,
`https://lucumr.pocoo.org/feed.atom`, `https://ghuntley.com/rss/`, `https://borischerny.com/feed.xml`,
`https://hamel.dev/index.xml`, `https://sh-reya.com/rss.xml`, `https://eugeneyan.com/rss/`,
`https://karpathy.bearblog.dev/feed/`, `https://huyenchip.com/feed.xml`,
`https://magazine.sebastianraschka.com/feed`, `https://www.latent.space/feed`, `https://www.swyx.io/rss.xml`,
`https://openai.com/news/rss.xml`, `https://deepmind.google/blog/rss.xml`, `https://mistral.ai/rss.xml`,
`https://qwenlm.github.io/blog/index.xml`.

No working feed found for: Anthropic, Meta AI, DeepSeek, LangChain, Lauren Tan, Jesse Vincent, Jason Liu.
Their activity is covered through GitHub events and HN. YouTube channel ids were **not** verified, so no
YouTube feeds are seeded (the feeds source still accepts any YouTube feed URL added to config later).

## Seed people (GitHub logins verified via `gh api users/<login>`)

| id | name | github | feed |
|---|---|---|---|
| matt-pocock | Matt Pocock | mattpocock | https://www.aihero.dev/rss.xml |
| lauren-tan | Lauren Tan | poteto | none |
| simon-willison | Simon Willison | simonw | https://simonwillison.net/atom/everything/ |
| armin-ronacher | Armin Ronacher | mitsuhiko | https://lucumr.pocoo.org/feed.atom |
| geoffrey-huntley | Geoffrey Huntley | ghuntley | https://ghuntley.com/rss/ |
| boris-cherny | Boris Cherny | bcherny | https://borischerny.com/feed.xml |
| jesse-vincent | Jesse Vincent | obra | none |
| harrison-chase | Harrison Chase | hwchase17 | none |
| hamel-husain | Hamel Husain | hamelsmu | https://hamel.dev/index.xml |
| shreya-shankar | Shreya Shankar | shreyashankar | https://sh-reya.com/rss.xml |
| eugene-yan | Eugene Yan | eugeneyan | https://eugeneyan.com/rss/ |
| jason-liu | Jason Liu | jxnl | none |
| andrej-karpathy | Andrej Karpathy | karpathy | https://karpathy.bearblog.dev/feed/ |
| chip-huyen | Chip Huyen | chiphuyen | https://huyenchip.com/feed.xml |
| sebastian-raschka | Sebastian Raschka | rasbt | https://magazine.sebastianraschka.com/feed |
| swyx | swyx | swyxio | https://www.swyx.io/rss.xml |

Lauren Tan's GitHub login `poteto` (profile name "lauren") is an inference: the React-team Lauren Tan. The
profile has no bio to confirm it, so Aymen should confirm it is the right person.

## Jobs

| Market | Source | Endpoint | Notes | Fixture |
|---|---|---|---|---|
| global | HN "Who is hiring" | find the thread: `search_by_date?tags=story,author_whoishiring`; the title starts `Ask HN: Who is hiring?`. Comments: `GET https://hn.algolia.com/api/v1/search?tags=comment,story_<id>&hitsPerPage=1000&page=N` | keep only comments whose `parent_id` equals the story id (top-level postings); `comment_text` is HTML-escaped | `hn/whoishiring.json`, `hn/hiring_comments.json` |
| global | RemoteOK | `GET https://remoteok.com/api` returns `[legal, job, ...]`; the first element is a legal notice, skip it | job fields: `id`, `position`, `company`, `tags`, `description`, `date`, `apply_url`. **Terms require a follow-link back to RemoteOK** and naming it as the source: the Jobs page must credit and link https://remoteok.com/ | `remoteok/jobs.json` |
| fr | Adzuna | `GET https://api.adzuna.com/v1/api/jobs/fr/search/1?app_id=&app_key=&what=<kw>&results_per_page=50` | free keys; response `{count, results: [{id, title, description (snippet), created, redirect_url, company.display_name, location.display_name}]}`; `count` is the total postings per keyword. Country `fr` is assumed supported; confirm on the first live call | `adzuna/search_fr.json` (**synthetic**, shape from the Adzuna docs) |
| tn | Tanitjobs / Keejob / Emploitunisie | | Tanitjobs `robots.txt` disallows keyword search (`Disallow: /*keyword`), leaving only the generic `/jobs/` listing, which is not enough for keyword trends. Keejob and Emploitunisie were not pursued (Emploitunisie's robots.txt reserves AI and data-mining rights). | **dropped** |

## Claude tooling

`anthropics/claude-code-action` (action.yml read 2026-11-20), inputs we use:

- `claude_code_oauth_token`: "Claude Code OAuth token (alternative to anthropic_api_key)". Falls back to env `CLAUDE_CODE_OAUTH_TOKEN`.
- `prompt`: the instruction text (we pass the contents of `prompts/enrich.md`).
- `claude_args`: extra CLI args, for example `--allowedTools "Read,Write" --max-turns 15`.
- `github_token`: optional. The workflow also needs `id-token: write` for the action's own GitHub App token exchange.
- The action accepts a `prompt` on any event, including `schedule` ("automation mode"). Only a real run can confirm this; the first manual `workflow_dispatch` is the test.

Local `claude --help` (this machine): `-p/--print`, `--output-format <text|json|stream-json>`,
`--allowedTools/--allowed-tools <tools...>`, `--model`, `--permission-mode`, `--input-format`.
The coach calls `claude -p --output-format json` with the prompt on stdin; the JSON envelope's `result`
field holds the model text.
