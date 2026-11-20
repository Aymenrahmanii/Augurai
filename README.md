# Augurai

Augurai keeps one AI engineer current and, over time, better at working with AI. It does two jobs:

- **The radar** runs on its own in the cloud. Every six hours it reads public sources (models and prices, benchmarks, rising repos, skills, agents and MCP servers, posts from people worth following, and job trends), finds new people and projects without anyone approving them, and publishes a static website. Each morning it also writes a short briefing, shown on the site's home page.
- **The coach** runs weekly on your own machine. It reads your Claude Code sessions (secrets removed first), compares how you worked with practices collected from respected practitioners, and proposes a few concrete changes. You approve each one.

Site: https://aymenrahmanii.github.io/Augurai/

## How it fits together

```
GitHub Actions (every 6h)                           Your PC (weekly)
┌──────────────────────────────────────┐            ┌─────────────────────────────┐
│ collect  → sources → data/*.json     │            │ augurai coach               │
│ rank     → velocity, best-at, people │            │  ~/.claude sessions         │
│ enrich   → Claude (morning only)     │  practices │  + CLAUDE.md + skills       │
│ build    → static site → Pages       │──────────▶│  + practices.json (site)    │
│ brief    → briefing (morning only)   │            │  → coach/proposals/*.md     │
└──────────────────────────────────────┘            │  → /coach-review            │
                                                    └─────────────────────────────┘
```

Only the morning run uses Claude, through your subscription (no API key). If that step fails, the site still ships with the ranked lists. See `docs/superpowers/specs/2026-11-20-augurai-design.md` for the full design and `docs/DESIGN.md` for the site's visual system.

## Commands

```bash
uv sync                                  # install
uv run pytest                            # tests (no network)
uv run augurai collect --mode refresh    # fetch, rank, update data/
uv run augurai build                     # render the site into _site/
uv run augurai finish --mode morning     # briefing and site (the workflow runs this)
uv run augurai coach                     # weekly coach (private suggestions)
```

## Learning, not outsourcing

Augurai is designed to teach: practices come with an exercise to try by hand, and the coach explains why before it suggests a change. See [docs/LEARNING.md](docs/LEARNING.md) for the habits and a `CLAUDE.md` snippet you can adopt.

## Setup

The Claude token, API keys, GitHub Pages and the coach schedule are one-time steps for you: see [docs/SETUP.md](docs/SETUP.md).

## Layout

- `src/augurai/sources/` one adapter per data source; a failing source never stops a run
- `src/augurai/domain/` ranking, discovery and change detection
- `src/augurai/enrich.py` the file contract with headless Claude (`prompts/`)
- `src/augurai/site/` templates and static assets
- `src/augurai/coach/` the local weekly coach
- `data/` committed state; `briefings/` daily briefings; `config/augurai.toml` settings and the seed people
