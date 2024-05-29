import argparse

from .init import add_init_parser, init_simulator
from .run import add_run_parser, run_simulator

__all__ = [
    'parse_args',
    'init_simulator',
    'run_simulator'
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        dest='command',
        required=True,
        help='Command to run.'
    )

    add_init_parser(subparsers)
    add_run_parser(subparsers)

    return parser.parse_args()
