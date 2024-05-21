import argparse
from typing import Union

from ..context import GlobalContext
from ..simulator import Simulator


def add_init_parser(subparsers) -> None:
    parser: argparse.ArgumentParser = subparsers.add_parser(
        'init',
        help='Initialize simulator session for the first time.',
        description='Initialize simulator session for the first time.'
    )
    parser.add_argument(
        '--seed', '-S',
        type=int,
        help='Seed for random generator.'
    )
    parser.add_argument(
        '--rewrite', '-R',
        action='store_true',
        help='Rewrite session if exists.'
    )


def init_simulator(
        seed: Union[int, None],
        rewrite: bool
    ) -> Simulator:
    if not rewrite and GlobalContext.CHECKPOINT_SESSION_PATH.exists():
        raise FileExistsError()

    return Simulator(seed=seed)
