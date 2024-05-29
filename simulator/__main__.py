from datetime import datetime

from .cli import parse_args, init_simulator, run_simulator
from .core.utils import cast
from .database import *
from .logging import simulator_logger
from .simulator import Simulator


if __name__ == '__main__':
    args = parse_args()

    command: str = args.command
    if command == 'init':
        _time = datetime.now()
        init_simulator(
            seed=args.seed,
            rewrite=args.rewrite
        )
        simulator_logger.info(
            f"Succesfully generate the simulator. "
            f'{(datetime.now() - _time).total_seconds():.1f}s'
        )

    elif command == 'run':
        run_simulator(
            max_datetime=cast(args.max_datetime, datetime) if args.max_datetime is not None else None,
            speed=args.speed,
            interval=args.interval,
            interval_min=args.interval_min,
            interval_max=args.interval_max,
            skip_step=args.skip_step,
            sync=not args.no_sync,
            workers=args.workers,
            store_restore_files=args.store_ids.split(',') if args.store_ids is not None else None
        )
