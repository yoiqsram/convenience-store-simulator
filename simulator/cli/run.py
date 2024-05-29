import argparse
from datetime import datetime
from typing import List

from ..core.utils import cast
from ..context import GlobalContext
from ..logging import simulator_logger
from ..simulator import Simulator


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
        help='Adjust simulator new minimum interval (secs) only for the run.'
    )
    parser.add_argument(
        '--interval-max',
        type=float,
        help='Adjust simulator new maximum interval (secs) only for the run.'
    )
    parser.add_argument(
        '--max-datetime', '-M',
        help=(
            'Max datetime for the run. '
            'It will not replace the simulation max datetime.'
        )
    )
    parser.add_argument(
        '--skip-step',
        action='store_true',
        help='Skip agent step when idle to reduce computation.'
    )
    parser.add_argument(
        '--no-sync',
        action='store_true',
        help='Run iteratively without simulating (scaled) time interval.'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=1,
        help='Number of workers. Default to 1.'
    )
    parser.add_argument(
        '--store-restore-files',
        help=argparse.SUPPRESS
    )


def run_simulator(
        max_datetime: datetime,
        speed: float,
        interval: float,
        interval_min: float,
        interval_max: float,
        skip_step: bool,
        sync: bool,
        workers: int,
        store_restore_files: List[str]
        ) -> None:
    _time = datetime.now()
    simulator_logger.info('Loading simulator state...')
    restore_file = GlobalContext.RESTORE_DIR / 'simulator.json'
    simulator: Simulator = Simulator.restore(
        restore_file,
        store_restore_files=store_restore_files
    )

    simulator_logger.info(
        f"Succesfully loaded the simulator. "
        f'{(datetime.now() - _time).total_seconds():.1f}s'
    )

    simulator_logger.info(
        'Continue run simulator from the last state '
        f'at {simulator.current_datetime()}.'
    )

    if interval_min is not None:
        interval_max = None
        if interval_max is not None:
            interval_max = interval_max
        simulator.interval = (interval_min, interval_max)
    elif interval is not None:
        simulator.interval = interval

    simulator.speed = speed

    if max_datetime is None:
        max_datetime = cast(max_datetime, datetime)

    simulator.run(
        sync=sync,
        max_datetime=max_datetime,
        skip_step=skip_step,
        workers=workers
    )
