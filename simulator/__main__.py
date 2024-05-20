import os
import dill

from .cli import parse_args
from .context import GlobalContext
from .logging import simulator_logger
from .simulator import Simulator


if __name__ == '__main__':
    args, command_runners = parse_args()

    command: str = args.command
    command_runner = command_runners[command]
    if command == 'init':
        simulator: Simulator = command_runner(args)

        args_, command_runner_, simulator_logger_ = args, command_runner, simulator_logger
        del args, command_runner, simulator_logger
        dill.dump_session(GlobalContext.CHECKPOINT_SESSION_PATH)
        args, command_runner, simulator_logger = args_, command_runner_, simulator_logger_

    elif command == 'run':
        dill.load_session(GlobalContext.CHECKPOINT_SESSION_PATH)

        simulator: Simulator
        while simulator.next_step() is not None:
            command_runner(args, simulator)

            args_, command_runner_, simulator_logger_ = args, command_runner, simulator_logger
            del args, command_runner, simulator_logger
            temp_checkpoint_path = (
                GlobalContext.CHECKPOINT_SESSION_PATH.parent
                / (GlobalContext.CHECKPOINT_SESSION_PATH.name + '.tmp')
            )
            dill.dump_session(temp_checkpoint_path)
            args, command_runner, simulator_logger = args_, command_runner_, simulator_logger_

            old_checkpoint_path = (
                GlobalContext.CHECKPOINT_SESSION_PATH.parent
                / (
                    GlobalContext.CHECKPOINT_SESSION_PATH.name.split('.pkl')[0]
                    + f"_{simulator.current_step().isoformat(timespec='seconds')}.pkl"
                )
            )
            simulator_logger.info(f"Dump new checkpoint at '{simulator.current_step()}' simulated time.")
            os.rename(GlobalContext.CHECKPOINT_SESSION_PATH, old_checkpoint_path)

            if not args.keep:
                old_checkpoint_path.unlink()

            os.rename(temp_checkpoint_path, GlobalContext.CHECKPOINT_SESSION_PATH)
