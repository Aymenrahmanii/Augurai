"""Write the weekly proposals to a private, git-ignored file."""

from pathlib import Path

from augurai.coach.propose import Proposals


def _markdown(proposals: Proposals) -> str:
    lines = [f"# Augurai coach, {proposals.week}", ""]
    for number, item in enumerate(proposals.items, start=1):
        source = f" (from {item.person})" if item.person else ""
        lines += [
            f"## {number}. {item.change}",
            "",
            f"**What I saw:** {item.observation}",
            "",
            f"**Practice{source}:** {item.practice_id or 'none in the library yet'}",
            "",
            f"**Type:** {item.change_kind.replace('_', ' ')}",
            "",
            f"**How to apply it:** `{item.apply}`",
            "",
        ]
    lines.append(
        "Review these with `/coach-review` in Claude Code. Nothing changes until you approve it."
    )
    return "\n".join(lines) + "\n"


def write(proposals: Proposals, root: Path) -> Path:
    path = root / "coach" / "proposals" / f"{proposals.week}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_markdown(proposals), encoding="utf-8")
    return path
