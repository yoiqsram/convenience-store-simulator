import argparse

from .init import add_init_parser, init_simulator
from .run import add_run_parser


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
