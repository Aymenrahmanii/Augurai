---
name: coach-review
description: Walk the user through the newest Augurai coach proposals so they learn from each one, and apply a change only after they understand it and say yes. Use when the user says /coach-review, or asks to go through the weekly Augurai coaching suggestions.
---

# Coach review (learning first)

The weekly coach writes private suggestions to `coach/proposals/<week>.md` (for example `2026-W47.md`). The goal of this review is that the user understands each suggestion and could do it by hand. Applying a change is the last and least important step. Never apply anything without an explicit yes.

## Steps

1. Find the newest file in `coach/proposals/` (sort by name; the week format sorts correctly). If there is none, say the coach has not run yet (`uv run augurai coach` creates it) and stop.
2. Go through the proposals one at a time, in order. For each one:
   1. **Explain.** Say what the coach saw in the user's own week and why the idea works, in your own words, using the proposal's "Why it works". Keep it short. Do not just read the file back.
   2. **Let them try it yourself first.** Give the proposal's "Try it yourself first" task and ask the user to do it, or to predict what will happen, before you show anything else. Wait for their answer. If they say they want to skip the exercise, accept that and move on without a lecture.
   3. **Discuss.** React to what they did or predicted: confirm what they got right, and point out gaps with a reason, not a verdict.
   4. **Preview, don't apply.** Only now show the exact change (the command, or the exact lines for `CLAUDE.md`) and explain what each part does, so they could type it themselves. Ask: apply, skip, or change it?
   5. **Apply only on an explicit yes for this proposal.** A yes to one proposal is not a yes to the next.
3. How to apply, by kind:
   - **claude_md:** show the exact lines first, then append them to the user's global `~/.claude/CLAUDE.md` (or the project's `CLAUDE.md` if they prefer). Do not rewrite or reorder existing content.
   - **skill_install:** name the skill and its source URL, ask the user to confirm the source, and install only if they confirm. Never run a remote script.
   - **skill_use / habit:** nothing to change in files. Describe the habit or command and offer to walk through it once together, narrating each step.
4. After each decision, append ` — applied` or ` — skipped` to that proposal's heading in the proposals file so the next review does not repeat it. Keep the numbering.
5. Finish with two lines: how many were applied or skipped, and one thing the user could now explain that they could not before.

## Rules

- Never apply anything without an explicit yes for that proposal. When in doubt, explain and ask instead of acting.
- Teach the reasoning, not just the action. If you make a change, narrate what you changed and why, so the user can reproduce it without you.
- Prefer showing a small diff or a one-line command over making edits silently.
- Never edit anything outside `~/.claude/CLAUDE.md`, the project `CLAUDE.md`, the user's skills folder (after confirmation), and the proposals file.
- The proposals file is private. Do not commit it, quote it in commit messages, or send it anywhere.
- If a proposal asks for something that sends data elsewhere or changes git history, skip it and say why.
