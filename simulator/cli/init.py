import argparse
import dill
from typing import Callable, Union

from ..context import GlobalContext
from ..simulator import Simulator


def add_init_parser(subparsers) -> Callable[[argparse.Namespace], None]:
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
    return init_simulator


def init_simulator(args: argparse.Namespace) -> Simulator:
    seed: Union[int, None] = args.seed
    rewrite: bool = args.rewrite

    if not rewrite and GlobalContext.CHECKPOINT_SESSION_PATH.exists():
        raise FileExistsError()

    return Simulator(seed=seed)
