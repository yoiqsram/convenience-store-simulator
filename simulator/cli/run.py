import argparse
import shutil
from datetime import datetime, timedelta
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
        '--checkpoint',
        default='monthly',
        choices=('hourly', 'daily', 'weekly', 'biweekly', 'monthly'),
        help='Run iteratively without simulating (scaled) time interval.'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=1,
        help='Number of workers. Default to 1.'
    )
    parser.add_argument(
        '--store-ids',
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
        checkpoint: str,
        workers: int,
        store_ids: List[str]
        ) -> None:
    restore_file = GlobalContext.RESTORE_DIR / 'simulator.json'

    _time = datetime.now()
    simulator_logger.info('Cleaning up temporary files from last run...')
    for file in restore_file.parent.rglob('*.json.tmp'):
        file.unlink()
        shutil.copy(
            file.parent / file.name[:-4],
            file
        )
    simulator_logger.info(
        f"Temporary files have been cleaned.. "
        f'{(datetime.now() - _time).total_seconds():.1f}s'
    )

    _time = datetime.now()
    simulator_logger.info('Loading simulator restore...')
    simulator: Simulator = Simulator.restore(
        restore_file,
        store_ids=store_ids
    )

    simulator_logger.info(
        f"Succesfully loaded the simulator restore. "
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

    if checkpoint == 'hourly':
        checkpoint_interval = timedelta(hours=1)
    elif checkpoint == 'daily':
        checkpoint_interval = timedelta(days=1)
    elif checkpoint == 'weekly':
        checkpoint_interval = timedelta(days=7)
    elif checkpoint == 'biweekly':
        checkpoint_interval = timedelta(days=14)
    else:
        checkpoint_interval = timedelta(days=30)

    max_datetime_ = simulator.current_datetime() + checkpoint_interval
    while simulator.next_datetime() is not None \
            and (
                max_datetime is None
                or simulator.next_datetime <= max_datetime
            ):
        simulator.run(
            sync=sync,
            max_datetime=max_datetime_,
            skip_step=skip_step
        )
        simulator.push_restore()
