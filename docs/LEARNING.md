# Learning with AI, not through it

Augurai is meant to make you a better engineer, so it is built to teach: the Playbook gives each practice an exercise to try by hand, the weekly coach explains why before it suggests anything, and `/coach-review` only applies a change after you have tried it and said yes.

These habits carry the same idea into your everyday work with any AI agent:

1. **Predict first.** Before reading an answer or running a command, write down what you expect. The gap between the guess and the result is the lesson.
2. **Try it by hand once.** Do a new technique yourself the first time. Use the agent to go faster at things you already understand, not to skip understanding them.
3. **Ask for the why.** Ask what the agent considered and rejected, and what would break if its assumption were wrong.
4. **Keep changes small and visible.** Ask for one diff or one command at a time and read it before accepting. Big silent edits are where understanding gets lost.
5. **Explain it back.** Write two sentences in your own words. If you cannot, ask again until you can.

## A snippet for your own `CLAUDE.md`

Augurai does not change your `CLAUDE.md`. If you like, add something like this to `~/.claude/CLAUDE.md` yourself:

```markdown
# Teach me while you work
- I want to understand, not just receive results. Before making a non-trivial change, say in two or three sentences what you plan to do and why.
- For new techniques or unfamiliar code, ask me for my prediction or a first attempt before you show yours, unless I say to skip it.
- Explain the reasoning behind a change after you make it, including what you ruled out. Keep it short.
- Prefer small diffs and one command at a time over large edits, so I can read each one.
- If I seem to be accepting something I may not understand, ask me to explain it back.
```

Tune it to taste: the point is that the agent explains and asks, and you decide.
