import os
from celery import Celery, group
from pathlib import Path
from psutil import Process

from simulator.cli.run import run_simulator
from simulator.logging import simulator_logger

__all__ = [
    'app',
    'group',
    'run_simulator_async'
]

broker_url = os.environ.get('BROKER_URL', 'redis://localhost:6379/0')
app = Celery(
    'simulator',
    broker=broker_url,
    backend=broker_url,
    include=['simulator']
)


@app.task(name='simulator.run')
def run_simulator_async(
        load_dir: str,
        max_datetime: str,
        speed: float,
        interval: float,
        sync: bool,
        checkpoint: str,
        store_ids: list[str] = None
        ) -> tuple[Path, int]:
    try:
        run_simulator(
            load_dir=load_dir,
            max_datetime=max_datetime,
            speed=speed,
            interval=interval,
            sync=sync,
            checkpoint=checkpoint,
            store_ids=store_ids
        )
    except Exception:
        simulator_logger.error(
            'Unexpected error happened.',
            exc_info=True
        )

    return load_dir, Process().memory_info().rss
