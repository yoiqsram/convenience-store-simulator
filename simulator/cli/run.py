import argparse
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path
from typing import List

from ..core.utils import cast
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
        '--no-sync',
        action='store_true',
        help='Run iteratively without simulating (scaled) time interval.'
    )
    parser.add_argument(
        '--checkpoint',
        default='monthly',
        choices=('daily', 'weekly', 'biweekly', 'monthly'),
        help='Run iteratively without simulating (scaled) time interval.'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=0,
        help=(
            'Number of workers to be used in celery. '
            'Default to 0 (use sequential).'
        )
    )


def get_next_checkpoint(
        current_datetime: datetime,
        checkpoint: str
        ) -> datetime:
    if checkpoint == 'daily':
        checkpoint_datetime = (
            datetime(
                current_datetime.year,
                current_datetime.month,
                current_datetime.day
            )
            + timedelta(days=1)
        )

    elif checkpoint == 'weekly':
        checkpoint_datetime = (
            datetime(
                current_datetime.year,
                current_datetime.month,
                current_datetime.day
            )
            + timedelta(
                days=7 - current_datetime.weekday()
            )
        )

    elif checkpoint == 'biweekly':
        checkpoint_datetime = (
            datetime(
                current_datetime.year,
                current_datetime.month,
                current_datetime.day
            )
            + timedelta(
                days=14 - current_datetime.weekday()
            )
        )

    elif checkpoint == 'monthly':
        checkpoint_datetime = (
            datetime(
                current_datetime.year,
                current_datetime.month,
                current_datetime.day
            )
            + relativedelta(months=1)
        )

    else:
        raise NotImplementedError()

    return checkpoint_datetime


def run_simulator(
        restore_file: str,
        max_datetime: str,
        speed: float,
        interval: float,
        interval_min: float,
        interval_max: float,
        sync: bool,
        checkpoint: str,
        store_ids: List[str] = None
        ) -> None:
    restore_file = Path(restore_file)

    _time = datetime.now()
    simulator_logger.info('Loading simulator...')
    simulator: Simulator = Simulator.restore(
        restore_file,
        store_ids=store_ids
    )
    simulator_logger.info(
        f'Succesfully loaded the simulator. '
        f'Last simulation datetime at {simulator.current_datetime}. '
        f'{(datetime.now() - _time).total_seconds():.1f}s.'
    )

    if interval_min is not None \
            and interval_max is not None:
        simulator.interval = (interval_min, interval_max)
    elif interval is not None:
        simulator.interval = interval

    simulator._next_step = simulator._current_step + simulator.interval

    if speed is not None:
        simulator.speed = speed

    max_datetime = cast(max_datetime, datetime)
    max_datetime_ = get_next_checkpoint(
        simulator.next_datetime + timedelta(days=1),
        checkpoint
    )
    if max_datetime is not None \
            and max_datetime < max_datetime_:
        max_datetime_ = max_datetime

    while simulator.next_datetime is not None \
            and (
                max_datetime is None
                or simulator.next_datetime < max_datetime
            ):
        simulator.run(
            sync=sync,
            max_datetime=max_datetime_
        )
        simulator.push_restore()

        max_datetime_ = get_next_checkpoint(
            simulator.next_datetime,
            checkpoint
        )

    return str(simulator.restore_file)
