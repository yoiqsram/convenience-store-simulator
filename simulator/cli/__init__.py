import argparse
import numpy as np
from datetime import datetime
from pathlib import Path
from time import time

from core.utils import cast, load_memmap_to_array, get_memory_usage
from ..context import GlobalContext
from ..database import SqliteDatabase, StoreModel
from ..logging import simulator_logger
from .init import add_init_parser, init_simulator
from .run import add_run_parser, run_simulator

__all__ = [
    'parse_args',
    'init',
    'run'
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


def init(args) -> None:
    _time = time()
    init_simulator(
        seed=args.seed,
        rewrite=args.rewrite
    )
    simulator_logger.info(
        f"Succesfully initialize simulator. "
        f'{time() - _time:.1f}s'
    )
    simulator_logger.info(
        f'Total memory usage: {get_memory_usage():.1f} MB.'
    )


def run(args) -> None:
    load_dir = GlobalContext.SIMULATOR_SAVE_DIR

    _time = time()
    if args.workers > 0 and \
            isinstance(StoreModel._meta.database, SqliteDatabase):
        raise NotImplementedError()

    current_step, _, memory_usage = run_simulator(
        load_dir=load_dir,
        max_datetime=args.max_datetime,
        interval=args.interval,
        speed=args.speed,
        sync=not args.no_sync,
        workers=args.workers,
        checkpoint=args.checkpoint
    )

    simulator_logger.info(
        f'Complete run the simulator. Last simulation datetime at '
        f'{datetime.fromtimestamp(current_step)}.'
        f'{time() - _time:.1f}s'
    )
    simulator_logger.info(
        f'Total memory usage: {memory_usage:.1f} MB.'
    )
