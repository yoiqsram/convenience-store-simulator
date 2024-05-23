import argparse

from ..context import GlobalContext


def add_run_parser(subparsers) -> None:
    parser: argparse.ArgumentParser = subparsers.add_parser(
        'run',
        help='Run simulator from the saved session.',
        description='Run simulator from the saved session.'
    )
    parser.add_argument(
        '--speed',
        type=float,
        help='Adjust simulator new speed only for the run.'
    )
    parser.add_argument(
        '--interval',
        type=float,
        help='Adjust simulator new fixed interval (seconds) only for the run.'
    )
    parser.add_argument(
        '--interval-min',
        type=float,
        help='Adjust simulator new minimum interval (seconds) only for the run.'
    )
    parser.add_argument(
        '--interval-max',
        type=float,
        help='Adjust simulator new maximum interval (seconds) only for the run.'
    )
    parser.add_argument(
        '--no-sync',
        action='store_true',
        help='Run iteratively without simulating (scaled) time interval.'
    )
    parser.add_argument(
        '--max-datetime', '-M',
        help='Max datetime for the run. It will not replace the simulation max datetime.'
    )
    parser.add_argument(
        '--skip-step',
        action='store_true',
        help='Skip agent step when idle to reduce computation.'
    )
    parser.add_argument(
        '--checkpoint', '-C',
        type=int,
        default=GlobalContext.CHECKPOINT_INTERVAL,
        help='Checkpoint save interval in seconds. Default: 86400 (daily).'
    )
    parser.add_argument(
        '--keep', '-K',
        action='store_true',
        help='Keep old checkpoint save.'
    )
