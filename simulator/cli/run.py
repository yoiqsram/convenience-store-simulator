import argparse
import numpy as np
import os
import uuid
import shutil
import subprocess
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path
from time import time

from core.utils import cast, load_memmap_to_array, get_memory_usage
from ..database import StoreModel
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
        load_dir: Path,
        max_datetime: datetime,
        interval: float,
        speed: float,
        sync: bool,
        workers: int,
        checkpoint: str = None,
        store_ids: list[str] = None
        ) -> tuple[int, int, int]:
    simulator_steps = load_memmap_to_array(
        load_dir / 'simulator_steps.dat',
        dtype=np.uint32
    )
    next_datetime = cast(simulator_steps[4], datetime)
    max_datetime = cast(max_datetime, datetime)
    max_datetime_ = max_datetime
    if checkpoint is not None:
        max_datetime_ = get_next_checkpoint(
            next_datetime + timedelta(days=1),
            checkpoint
        )

    if max_datetime is not None \
            and max_datetime < max_datetime_:
        max_datetime_ = max_datetime

    additional_memory_usage = 0
    while max_datetime is None \
            or next_datetime < max_datetime:
        if workers == 0:
            current_step, next_step, _ = \
                run_simulator_sync(
                    load_dir,
                    max_datetime_,
                    interval,
                    speed,
                    sync,
                    store_ids
                )
        else:
            current_step, next_step, memory_usage = \
                run_simulator_async(
                    load_dir,
                    max_datetime_,
                    interval,
                    speed,
                    sync,
                    workers,
                    store_ids
                )
            additional_memory_usage = max(
                additional_memory_usage,
                memory_usage
            )

        max_datetime_ = get_next_checkpoint(
            cast(next_step, datetime),
            checkpoint
        )

    return (
        current_step,
        next_step,
        get_memory_usage() + additional_memory_usage
    )


def run_simulator_sync(
        load_dir: Path,
        max_datetime: datetime,
        interval: int,
        speed: float,
        sync: bool,
        store_ids: list[int] = None
        ) -> tuple[int, int, int]:
    _time = time()
    simulator: Simulator = Simulator.load(load_dir, store_ids)
    simulator_logger.info(
        f'Succesfully loaded the simulator with {simulator.n_stores} stores. '
        f'Last simulation datetime at {simulator.current_datetime}. '
        f'{time() - _time:.1f}s.'
    )
    simulator_logger.info(f'Running simulator until {max_datetime}.')

    if interval is not None:
        simulator.interval = interval

    if speed is not None:
        simulator.speed = speed

    simulator.run(
        sync=sync,
        max_datetime=max_datetime
    )
    simulator.save(load_dir)
    return (
        int(simulator.current_step),
        int(simulator.next_step),
        get_memory_usage()
    )


def run_simulator_async(
        load_dir: Path,
        max_datetime: datetime,
        interval: int,
        speed: float,
        sync: bool,
        workers: int,
        store_ids: list[str] = None
        ) -> tuple[int, int, int]:
    from ..celery import app, group, run_simulator_task

    app.connection().heartbeat_check()

    simulator_last_step = load_memmap_to_array(
        load_dir / 'simulator_steps.dat',
        dtype=np.uint32
    )[3]

    store_query = StoreModel.select() \
        .where(
            StoreModel.created_datetime
            <= cast(simulator_last_step, datetime)
        )
    if store_ids is not None:
        store_query = store_query.where(
            StoreModel.id.in_(store_ids)
        )
    store_ids = [
        store_record.id
        for store_record in store_query
    ]
    workers = min(workers, len(store_ids))
    simulator_logger.info(
        f'Running simulator with {workers} workers...'
    )

    job_name = 'simulator-' + str(uuid.uuid4()).split('-')[0]
    job_pid_file = job_name + '.pid'
    subprocess.Popen(
        f'celery -A simulator.celery worker --logfile=INFO '
        f'--concurrency={workers} --hostname={job_name}@%h '
        f'--pidfile {job_pid_file}',
        shell=True
    )

    n_stores_per_worker = len(store_ids) / workers
    if n_stores_per_worker % 1 > 0:
        n_stores_per_worker = int(n_stores_per_worker) + 1
    else:
        n_stores_per_worker = int(n_stores_per_worker)

    run_tasks = []
    task_save_dirs = [
        load_dir.parent / f'simulator_{i:02d}'
        for i in range(workers)
    ]
    for i, task_save_dir in enumerate(task_save_dirs):
        task_save_dir.mkdir(exist_ok=True)

        for file_path in load_dir.glob('*.*'):
            shutil.copy(
                file_path,
                task_save_dir / file_path.name
            )

        store_ids_ = store_ids[
            i * n_stores_per_worker:
            (i + 1) * n_stores_per_worker
        ]
        for store_id in store_ids_:
            store_dir = load_dir / f'Store_{store_id:06d}'
            if store_dir.is_dir():
                shutil.copytree(
                    store_dir,
                    task_save_dir / store_dir.name,
                    dirs_exist_ok=True
                )

        run_task = run_simulator_task.s(
            load_dir=str(task_save_dir),
            max_datetime=max_datetime,
            interval=interval,
            speed=speed,
            sync=sync,
            store_ids=store_ids_
        )
        run_tasks.append(run_task)

    job = group(run_tasks).apply_async(expires=10)
    results = job.get()

    min_current_step = None
    min_next_step = None
    min_index = None
    workers_memory_usage = 0
    for i, (current_step, next_step, task_memory_usage) \
            in enumerate(results):
        if min_current_step is None \
                or current_step < min_current_step:
            min_current_step = current_step
            min_next_step = next_step
            min_index = i

        workers_memory_usage += task_memory_usage

    with open(job_pid_file, 'r') as f:
        pid = int(f.read())
        workers_memory_usage += get_memory_usage(pid)
        subprocess.run(f"kill -9 {pid}", shell=True)

    try:
        os.remove(job_pid_file)
    except Exception:
        pass

    for i, task_save_dir in enumerate(task_save_dirs):
        if i == min_index:
            for file_path in task_save_dir.glob('*.*'):
                shutil.copy(
                    file_path,
                    load_dir / file_path.name
                )

        for store_dir in task_save_dir.glob('*'):
            if not store_dir.is_dir():
                continue
            shutil.copytree(
                store_dir,
                load_dir / store_dir.name,
                dirs_exist_ok=True
            )

        try:
            shutil.rmtree(task_save_dir)
        except Exception:
            pass

        return (
            int(min_current_step),
            int(min_next_step),
            get_memory_usage() + workers_memory_usage
        )
