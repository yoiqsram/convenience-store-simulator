import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .cli import parse_args, init_simulator
from .context import GlobalContext
from .database import *
from .logging import simulator_logger
from .simulator import Simulator
from .utils import cast


def dump_session(
        path: Path,
        global_vars: Dict[str, Any]
    ) -> None:
    import dill

    for var, value in global_vars.items():
        globals()[var] = value

    global_vars_to_ignore = set(
        var
        for var in globals().keys()
        if not var.startswith('__')
            and var not in global_vars.keys()
    )
    ignored_dir = {
        var: globals()[var]
        for var in global_vars_to_ignore
    }
    for var in global_vars_to_ignore:
        del globals()[var]

    dill.dump_session(path)

    for var, value in ignored_dir.items():
        globals()[var] = value


def load_session(path: Path) -> None:
    import dill

    dill.load_session(path)


if __name__ == '__main__':
    args = parse_args()

    temp_checkpoint_path = (
        GlobalContext.CHECKPOINT_SESSION_PATH.parent
        / (GlobalContext.CHECKPOINT_SESSION_PATH.name + '.tmp')
    )

    command: str = args.command
    if command == 'init':
        _time = datetime.now()
        simulator: Simulator = init_simulator(
            seed=args.seed,
            rewrite=args.rewrite
        )
        simulator_logger.info(
            f"Succesfully generate the simulator. "
            f'{(datetime.now() - _time).total_seconds():.1f}s'
        )

        _time = datetime.now()
        simulator_logger.info(f"Dumping simulator checkpoint at '{simulator.current_datetime()}' simulation time.")
        dump_session(temp_checkpoint_path, { 'simulator': simulator })
        os.rename(temp_checkpoint_path, GlobalContext.CHECKPOINT_SESSION_PATH)
        simulator_logger.info(
            f"Checkpoint saved in '{GlobalContext.CHECKPOINT_SESSION_PATH}'. "
            f'{(datetime.now() - _time).total_seconds():.1f}s'
        )

    elif command == 'run':
        simulator_logger.info('Loading last checkpoint...')
        load_session(GlobalContext.CHECKPOINT_SESSION_PATH)

        simulator: Simulator = globals()['simulator']

        # Adjust simulation speed and interval
        if args.speed is not None:
            simulator.speed = args.speed

        if args.interval_min is not None:
            interval_max = args.interval_max if args.interval_max is not None else simulator.interval_max
            simulator.interval = ( args.interval_min, interval_max )
        elif args.interval is not None:
            simulator.interval = args.interval

        # Run simulation
        current_datetime = simulator.current_datetime()
        simulator_logger.info('Continue run simulator from previous checkpoint. ')
        simulator_logger.info(f'Last simulation time: {current_datetime}.')

        for db_model in [
                EmployeeModel,
                EmployeeShiftScheduleModel,
                EmployeeAttendanceModel,
                OrderModel,
                OrderSKUModel,
                StoreModel
            ]:
            db_model.delete().where(db_model.created_datetime > current_datetime).execute()

        sync = not args.no_sync
        max_datetime = cast(args.max_datetime, datetime) if args.max_datetime is not None else args.max_datetime
        skip_step = args.skip_step
        checkpoint_interval = args.checkpoint if args.checkpoint > 0 else None
        while simulator.next_step() is not None:
            simulator.run(sync, max_datetime, skip_step)

            current_datetime = simulator.current_datetime()
            simulator_logger.info(f"Dumping simulator checkpoint at '{current_datetime}' simulation time.")
            dump_session(
                temp_checkpoint_path,
                { 'simulator': simulator }
            )

            old_checkpoint_path = (
                GlobalContext.CHECKPOINT_SESSION_PATH.parent
                / (
                    GlobalContext.CHECKPOINT_SESSION_PATH.name.split('.pkl')[0]
                    + f"_{simulator.current_step().isoformat(timespec='seconds')}.pkl"
                )
            )
            os.rename(GlobalContext.CHECKPOINT_SESSION_PATH, old_checkpoint_path)

            if not args.keep:
                old_checkpoint_path.unlink()

            os.rename(temp_checkpoint_path, GlobalContext.CHECKPOINT_SESSION_PATH)
            version_record = VersionModel.get()
            version_record.modified_datetime = current_datetime
            version_record.save()
            simulator_logger.info(f"Checkpoint saved in '{GlobalContext.CHECKPOINT_SESSION_PATH}'.")
