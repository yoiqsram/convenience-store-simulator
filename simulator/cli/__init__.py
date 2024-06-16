import argparse
import numpy as np
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from psutil import Process
from time import time

from core.utils import cast, load_memmap_to_array
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
        f'Total memory usage: {Process().memory_info().rss / 1048576:.1f} MB.'
    )


def run(args) -> None:
    load_dir = GlobalContext.SIMULATOR_SAVE_DIR

    _time = time()
    task_memory = 0
    if args.workers <= 0:
        simulator = run_simulator(
            load_dir=load_dir,
            max_datetime=args.max_datetime,
            speed=args.speed,
            interval=args.interval,
            sync=not args.no_sync,
            checkpoint=args.checkpoint
        )
        simulator_last_step = simulator.current_step

    elif isinstance(StoreModel._meta.database, SqliteDatabase):
        raise NotImplementedError()

    else:
        from ..celery import app, group, run_simulator_async

        app.connection().heartbeat_check()

        simulator_last_step = load_memmap_to_array(
            load_dir / 'simulator_steps.dat',
            dtype=np.uint32
        )[3]

        store_ids = [
            store_record.id
            for store_record in
                StoreModel.select()
                .where(
                    StoreModel.created_datetime
                    <= cast(simulator_last_step, datetime)
                )
        ]

        workers = min(args.workers, len(store_ids))
        simulator_logger.info(
            f'Running simulator with {workers} workers...'
        )

        worker_name = 'simulator-' + str(uuid.uuid4()).split('-')[0]
        subprocess.Popen(
            f'celery -A simulator.celery worker --logfile=INFO '
            f'--concurrency={workers} --hostname={worker_name}@%h '
            f'--pidfile {worker_name}.pid',
            shell=True
        )

        n_stores_per_worker = len(store_ids) / workers
        if n_stores_per_worker % 1 > 0:
            n_stores_per_worker = int(n_stores_per_worker) + 1
        else:
            n_stores_per_worker = int(n_stores_per_worker)

        run_tasks = []
        for i in range(workers):
            task_save_dir = load_dir.parent / f'simulator_{i:02d}'
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

            run_task = run_simulator_async.s(
                load_dir=str(task_save_dir),
                max_datetime=args.max_datetime,
                speed=args.speed,
                interval=args.interval,
                sync=not args.no_sync,
                checkpoint=args.checkpoint,
                store_ids=store_ids_
            )
            run_tasks.append(run_task)

        job = group(run_tasks).apply_async(expires=30)
        results = job.get()

        min_step = None
        min_index = None
        for i, (task_save_dir, task_memory_) \
                in enumerate(results):
            task_memory += task_memory_
            task_save_dir = Path(task_save_dir)
            simulator_step = load_memmap_to_array(
                task_save_dir / 'simulator_steps.dat',
                dtype=np.uint32
            )[3]
            if min_step is None \
                    or simulator_step < min_step:
                min_step = simulator_step
                min_index = i

        for i, (task_save_dir, _) in enumerate(results):
            task_save_dir = Path(task_save_dir)
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

        simulator_last_step = min_step
        subprocess.run(
            f"kill -9 $(cat {worker_name}.pid)",
            shell=True
        )
        if os.path.exists(f'{worker_name}.pid'):
            os.remove(f'{worker_name}.pid')

    simulator_logger.info(
        f'Complete run the simulator. Last simulation datetime at '
        f'{datetime.fromtimestamp(simulator_last_step)}.'
        f'{time() - _time:.1f}s'
    )
    simulator_logger.info(
        f'Total memory usage: '
        f'{(Process().memory_info().rss + task_memory) / 1048576:.1f} MB.'
    )
