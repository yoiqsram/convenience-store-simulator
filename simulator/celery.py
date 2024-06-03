import os
from celery import Celery, group
from typing import List

from simulator.cli.run import run_simulator

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
        restore_file: str,
        max_datetime: str,
        speed: float,
        interval: float,
        interval_min: float,
        interval_max: float,
        sync: bool,
        checkpoint: str,
        store_ids: List[str]
        ) -> None:
    return run_simulator(
        restore_file=restore_file,
        max_datetime=max_datetime,
        speed=speed,
        interval=interval,
        interval_min=interval_min,
        interval_max=interval_max,
        sync=sync,
        checkpoint=checkpoint,
        store_ids=store_ids
    )
