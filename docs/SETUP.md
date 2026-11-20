# Setting up Augurai (one time, about 10 minutes)

Everything here is yours to do: Augurai never creates accounts or handles your secrets. Commands run in PowerShell or Git Bash from the repository folder, and `gh` is already signed in as `Aymenrahmanii`. There is no email: the briefing lives on the website.

## 1. Claude token (the daily summaries)

Augurai uses your Claude subscription, not an API key.

```bash
claude setup-token
```

Copy the token it prints, then store it as a repository secret (the command prompts you to paste it):

```bash
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo Aymenrahmanii/Augurai
```

If this token ever expires, the site still updates and the briefing says "Summaries unavailable today", with the fix: run the two commands above again.

## 2. Free API keys (optional but recommended)

Without these, the sources are skipped and the About page shows "missing env". Everything else still works.

- **Artificial Analysis** (benchmark scores that drive "best at"): create an account at https://artificialanalysis.ai/, generate a key under API key management, then `gh secret set ARTIFICIAL_ANALYSIS_API_KEY --repo Aymenrahmanii/Augurai`.
- **Adzuna** (France job market): register at https://developer.adzuna.com/, then `gh secret set ADZUNA_APP_ID --repo Aymenrahmanii/Augurai` and `gh secret set ADZUNA_APP_KEY --repo Aymenrahmanii/Augurai`.

## 3. Turn on GitHub Pages

In the repository on GitHub: Settings, Pages, Source: **GitHub Actions**. Or:

```bash
gh api -X PUT repos/Aymenrahmanii/Augurai/pages -f build_type=workflow
```

The site is at https://aymenrahmanii.github.io/Augurai/.

## 4. Run it

```bash
gh workflow run augurai.yml --repo Aymenrahmanii/Augurai -f mode=morning
gh run watch --repo Aymenrahmanii/Augurai
```

Check that no step is red (the "Enrich with Claude" step is allowed to fail) and that the home page shows the briefing. One briefing is written per local day, the first morning run of the day. To regenerate today's, delete `briefings/<date>.md` from the repository and run the workflow again in morning mode.

## 5. The weekly coach (on this PC)

The coach reads your local Claude Code sessions, so it runs here, not in the cloud. It writes private suggestions to `coach/proposals/<week>.md` (git-ignored).

1. Try it once:

```bash
uv run augurai coach
```

2. Schedule it for Sundays at 10:00 (PowerShell, in the repository folder):

```powershell
.\scripts\install-coach-task.ps1
```

If the PC is off at 10:00 the task runs as soon as it is back on.

3. Review the suggestions in Claude Code with `/coach-review`. It applies only the ones you approve.

## Things to check once

- **Lauren Tan's GitHub login** is set to `poteto` in `config/augurai.toml`. Confirm it is the right person, or fix the link.
- **Jobs:** Tunisian job boards are not tracked because their terms and robots.txt do not allow it. The France market uses Adzuna.
- **Credits:** the site footer credits Artificial Analysis and Remote OK, as their terms require. Keep those links.
