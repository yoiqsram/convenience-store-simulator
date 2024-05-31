from datetime import datetime

from .cli import parse_args, init_simulator, run_simulator
from .logging import simulator_logger


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
        store_ids = None
        if args.store_ids is not None:
            store_ids = args.store_ids.split(',')

        run_simulator(
            max_datetime=args.max_datetime,
            speed=args.speed,
            interval=args.interval,
            interval_min=args.interval_min,
            interval_max=args.interval_max,
            sync=not args.no_sync,
            checkpoint=args.checkpoint,
            workers=args.workers,
            store_ids=store_ids
        )
