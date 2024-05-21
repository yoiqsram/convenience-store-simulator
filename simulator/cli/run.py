import argparse

from ..simulator import Simulator


def add_run_parser(subparsers) -> None:
    parser: argparse.ArgumentParser = subparsers.add_parser(
        'run',
        help='Run simulator from the saved session.',
        description='Run simulator from the saved session.'
    )
    parser.add_argument(
        '--checkpoint', '-C',
        type=int,
        default=86400,
        help='Checkpoint save interval in seconds. Default: 86400 (daily).'
    )
    parser.add_argument(
        '--keep', '-K',
        action='store_true',
        help='Keep old checkpoint save.'
    )
