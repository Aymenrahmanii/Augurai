import argparse
import sys

from augurai import __version__

COMMANDS = ("collect", "finish", "build", "coach")
EXIT_EMAIL_FAILED = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="augurai")
    parser.add_argument("--version", action="version", version=f"augurai {__version__}")
    sub = parser.add_subparsers(dest="command")
    for name in COMMANDS:
        command = sub.add_parser(name)
        if name in ("collect", "finish"):
            command.add_argument("--mode", choices=["morning", "refresh"], default="refresh")
        if name == "coach":
            command.add_argument("--days", type=int, default=7)
            command.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    if args.command is None:
        build_parser().print_help()
        return 0
    if args.command == "collect":
        return _collect(args.mode)
    if args.command == "finish":
        return _finish(args.mode)
    if args.command == "coach":
        return _coach(args.days, args.dry_run)
    if args.command == "build":
        return _build()
    print(f"{args.command}: not implemented", file=sys.stderr)
    return 2


def _collect(mode: str) -> int:
    from datetime import UTC, datetime
    from pathlib import Path

    from augurai.config import load_settings
    from augurai.pipeline import collect

    changes = collect(Path.cwd(), load_settings(), mode, datetime.now(UTC))  # type: ignore[arg-type]
    print(f"collect ok: {len(changes.new_models)} new models, first_run={changes.first_run}")
    return 0


def _build() -> int:
    from pathlib import Path

    from augurai.config import load_settings
    from augurai.site.build import build_site

    pages = build_site(Path.cwd(), Path("_site"), load_settings())
    print(f"built {len(pages)} files into _site/")
    return 0


def _finish(mode: str) -> int:
    import os
    from datetime import UTC, datetime
    from pathlib import Path

    from augurai.config import load_settings
    from augurai.pipeline import finish

    record = finish(Path.cwd(), load_settings(), mode, datetime.now(UTC), os.environ)  # type: ignore[arg-type]
    print(
        f"finish ok: enrichment={record.enrichment}, email_sent={record.email_sent}"
        + (f" ({record.enrichment_note})" if record.enrichment_note else "")
    )
    if record.email_failed:
        print("the briefing email could not be sent (check the Gmail secrets)", file=sys.stderr)
        return EXIT_EMAIL_FAILED
    return 0


def _coach(days: int, dry_run: bool) -> int:
    import os
    from datetime import UTC, datetime
    from pathlib import Path

    from augurai.coach.run import load_env_file, run_coach
    from augurai.config import load_settings

    root = Path.cwd()
    env = {**load_env_file(root / ".env"), **os.environ}
    path = run_coach(root, load_settings(), datetime.now(UTC), days, dry_run, env)
    print(f"coach ok: {path}")
    return 0
