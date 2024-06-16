import numpy as np
import os
from celery import Celery, group
from pathlib import Path
from psutil import Process

from core.utils import load_memmap_to_array, get_memory_usage
from simulator.cli.run import run_simulator_sync
from simulator.logging import simulator_logger

__all__ = [
    'app',
    'group',
    'run_simulator_task'
]

broker_url = os.environ.get('BROKER_URL', 'redis://localhost:6379/0')
app = Celery(
    'simulator',
    broker=broker_url,
    backend=broker_url,
    include=['simulator']
)


@app.task(name='simulator.run')
def run_simulator_task(
        load_dir: str,
        max_datetime: str,
        interval: float,
        speed: float,
        sync: bool,
        store_ids: list[str] = None
        ) -> tuple[int, int, int]:
    try:
        return run_simulator_sync(
            load_dir=load_dir,
            max_datetime=max_datetime,
            interval=interval,
            speed=speed,
            sync=sync,
            store_ids=store_ids
        )

    except Exception:
        simulator_logger.error(
            'Unexpected error happened.',
            exc_info=True
        )

    simulator_steps = load_memmap_to_array(
        Path(load_dir) / 'simulator_steps.dat',
        dtype=np.uint32
    )
    return (
        int(simulator_steps[3]),
        int(simulator_steps[4]),
        get_memory_usage()
    )
