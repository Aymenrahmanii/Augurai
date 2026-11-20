import argparse
import sys

from augurai import __version__

COMMANDS = ("collect", "finish", "build", "coach")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="augurai")
    parser.add_argument("--version", action="version", version=f"augurai {__version__}")
    sub = parser.add_subparsers(dest="command")
    for name in COMMANDS:
        sub.add_parser(name)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    if args.command is None:
        build_parser().print_help()
        return 0
    print(f"{args.command}: not implemented", file=sys.stderr)
    return 2
