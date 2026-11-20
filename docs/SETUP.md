# Setting up Augurai (one time, about 20 minutes)

Everything here is yours to do: Augurai never creates accounts or handles your secrets. Do the steps in order. Commands run in PowerShell or Git Bash from the repository folder, and `gh` is already signed in as `Aymenrahmanii`.

## 1. Claude token (the daily summaries)

Augurai uses your Claude subscription, not an API key.

```bash
claude setup-token
```

Copy the token it prints, then store it as a repository secret (the command prompts you to paste it):

```bash
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo Aymenrahmanii/Augurai
```

If this token ever expires, the morning email still arrives with ranked lists and says "Summaries unavailable today", followed by the fix: run the two commands above again.

## 2. Gmail (the morning email)

1. Turn on 2-Step Verification for the Google account that will send the email.
2. Open Google Account, Security, 2-Step Verification, then App passwords. Create one called "Augurai" and copy the 16 characters.
3. Store three secrets (each command prompts for the value):

```bash
gh secret set GMAIL_USER --repo Aymenrahmanii/Augurai
gh secret set GMAIL_APP_PASSWORD --repo Aymenrahmanii/Augurai
gh secret set BRIEFING_TO --repo Aymenrahmanii/Augurai
```

`GMAIL_USER` is the sending address, `BRIEFING_TO` is where the briefing goes (it can be the same address).

## 3. Free API keys (optional but recommended)

Without these, the sources are skipped and the About page shows "missing env". Everything else still works.

- **Artificial Analysis** (benchmark scores that drive "best at"): create an account at https://artificialanalysis.ai/, generate a key under API key management, then `gh secret set ARTIFICIAL_ANALYSIS_API_KEY --repo Aymenrahmanii/Augurai`.
- **Adzuna** (France job market): register at https://developer.adzuna.com/, then `gh secret set ADZUNA_APP_ID --repo Aymenrahmanii/Augurai` and `gh secret set ADZUNA_APP_KEY --repo Aymenrahmanii/Augurai`.

## 4. Turn on GitHub Pages

In the repository on GitHub: Settings, Pages, Source: **GitHub Actions**. The site will be at https://aymenrahmanii.github.io/Augurai/.

## 5. First run

```bash
gh workflow run augurai.yml --repo Aymenrahmanii/Augurai -f mode=morning
```

Then watch it:

```bash
gh run watch --repo Aymenrahmanii/Augurai
```

Check three things together: the Actions log has no red steps (the "Enrich with Claude" step is allowed to fail), the site loads, and the briefing email arrives ("Baseline established: Augurai is now tracking ..."). The first run only establishes a baseline; real changes show from the second day.

If the Claude step fails on the very first run, open its log: the most likely causes are an expired token or the action rejecting the `schedule` event. The email still goes out either way.

## 6. The weekly coach (on this PC)

The coach reads your local Claude Code sessions, so it runs here, not in the cloud.

1. Optional, so it can email you: create a file named `.env` in the repository folder (it is git-ignored) with:

```
GMAIL_USER=...
GMAIL_APP_PASSWORD=...
BRIEFING_TO=...
```

2. Try it once without emailing:

```bash
uv run augurai coach --dry-run
```

It writes `coach/proposals/<week>.md` (private, never committed).

3. Schedule it for Sundays at 10:00 (PowerShell, in the repository folder):

```powershell
.\scripts\install-coach-task.ps1
```

If the PC is off at 10:00 the task runs as soon as it is back on.

4. Review the suggestions in Claude Code with `/coach-review`. It applies only the ones you approve.

## Things to check once

- **Lauren Tan's GitHub login** is set to `poteto` in `config/augurai.toml`. Confirm it is the right person, or fix the link.
- **Jobs:** Tunisian job boards are not tracked because their terms and robots.txt do not allow it. The France market uses Adzuna.
- **Credits:** the site footer credits Artificial Analysis and Remote OK, as their terms require. Keep those links.
