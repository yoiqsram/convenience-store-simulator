import os
from pathlib import Path
from typing import Any, Dict

from .cli import parse_args, init_simulator
from .context import GlobalContext
from .logging import simulator_logger
from .simulator import Simulator


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

    command: str = args.command
    if command == 'init':
        simulator: Simulator = init_simulator(
            seed=args.seed,
            rewrite=args.rewrite
        )
        dump_session(
            GlobalContext.CHECKPOINT_SESSION_PATH,
            { 'simulator': simulator }
        )

    elif command == 'run':
        load_session(GlobalContext.CHECKPOINT_SESSION_PATH)

        simulator: Simulator = globals()['simulator']
        simulator.speed = GlobalContext.CLOCK_SPEED
        while simulator.next_step() is not None:
            simulator.run(interval=args.checkpoint)

            temp_checkpoint_path = (
                GlobalContext.CHECKPOINT_SESSION_PATH.parent
                / (GlobalContext.CHECKPOINT_SESSION_PATH.name + '.tmp')
            )
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

            simulator_logger.info(f"Dump new checkpoint at '{simulator.current_step()}' simulated time.")
            os.rename(temp_checkpoint_path, GlobalContext.CHECKPOINT_SESSION_PATH)
