import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from .cli import parse_args, init_simulator, run_simulator
from .context import GlobalContext
from .logging import simulator_logger


def _init(args) -> None:
    _time = datetime.now()
    init_simulator(
        seed=args.seed,
        rewrite=args.rewrite
    )
    simulator_logger.info(
        f"Succesfully generate the simulator. "
        f'{(datetime.now() - _time).total_seconds():.1f}s'
    )


def _run(args) -> None:
    restore_file = GlobalContext.RESTORE_DIR / 'simulator.json'
    clean_temporary_files(restore_file.parent)

    if args.workers <= 0:
        run_simulator(
            restore_file=str(restore_file),
            max_datetime=args.max_datetime,
            speed=args.speed,
            interval=args.interval,
            interval_min=args.interval_min,
            interval_max=args.interval_max,
            sync=not args.no_sync,
            checkpoint=args.checkpoint
        )

    else:
        from .celery import group, run_simulator_async

        _time = datetime.now()
        store_ids = [
            store_restore_file.parent.name
            for store_restore_file in (
                restore_file.parent.rglob('store.json')
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
            store_ids_ = store_ids[
                i * n_stores_per_worker:
                (i + 1) * n_stores_per_worker
            ]

            task_restore_file = (
                restore_file.parent
                / (restore_file.name[:-5] + f'-{i}.json')
            )
            shutil.copy(restore_file, task_restore_file)
            run_task = run_simulator_async.s(
                restore_file=str(task_restore_file),
                max_datetime=args.max_datetime,
                speed=args.speed,
                interval=args.interval,
                interval_min=args.interval_min,
                interval_max=args.interval_max,
                sync=not args.no_sync,
                checkpoint=args.checkpoint,
                store_ids=store_ids_
            )
            run_tasks.append(run_task)

        job = group(run_tasks).apply_async(expires=30)
        results = job.get()
        for i, task_restore_file in enumerate(results):
            if i == 0:
                shutil.copy(task_restore_file, restore_file)
            os.remove(task_restore_file)

        simulator_logger.info(
            'Complete run the simulator. '
            f'{(datetime.now() - _time).total_seconds():.1f}s'
        )

        subprocess.run(
            f"kill -9 $(cat {worker_name}.pid)",
            shell=True
        )
        # os.remove(f'{worker_name}.pid')


def clean_temporary_files(restore_dir: Path) -> None:
    _time = datetime.now()
    simulator_logger.info(
        'Cleaning up temporary files from the last run...'
    )

    for file in restore_dir.glob('*.pid'):
        file.unlink()

    for file in restore_dir.rglob('*.json.tmp'):
        file.unlink()

    simulator_logger.info(
        f"Temporary files have been cleaned. "
        f'{(datetime.now() - _time).total_seconds():.1f}s'
    )


if __name__ == '__main__':
    args = parse_args()

    command: str = args.command
    if command == 'init':
        _init(args)
    elif command == 'run':
        _run(args)
