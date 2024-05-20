import argparse
from typing import Callable, Dict

from .init import add_init_parser
from .run import add_run_parser


def parse_args() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        dest='command',
        required=True,
        help='Command to run.'
    )

    command_runners: Dict[str, Callable] = {
        'init': add_init_parser(subparsers),
        'run': add_run_parser(subparsers)
    }

    args, _ = parser.parse_known_args()
    return args, command_runners
