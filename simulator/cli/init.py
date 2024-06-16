import argparse
import os
import shutil
from datetime import datetime
from time import time
from typing import Union

from ..context import GlobalContext
from ..logging import simulator_logger
from ..simulator import Simulator
from ..database import (
    Database, SqliteDatabase,
    StoreModel, create_database
)
from ..database.config import config_database, create_config_database


def add_init_parser(subparsers) -> None:
    parser: argparse.ArgumentParser = subparsers.add_parser(
        'init',
        help='Initialize simulator session for the first time.',
        description='Initialize simulator session for the first time.'
    )
    parser.add_argument(
        '--seed', '-S',
        type=int,
        help='Seed for random generator.'
    )
    parser.add_argument(
        '--rewrite', '-R',
        action='store_true',
        help='Rewrite saved data if exists.'
    )


def init_simulator(
        seed: Union[int, None],
        rewrite: bool
        ) -> Simulator:
    save_dir = GlobalContext.SIMULATOR_SAVE_DIR
    save_file = save_dir / 'simulator.json'
    if not rewrite and save_file.exists():
        raise FileExistsError()

    database: Database = StoreModel._meta.database
    if rewrite and save_dir.exists():
        _time = time()
        simulator_logger.info('Removing old simulator data...')

        shutil.rmtree(save_dir)
        save_dir.mkdir()

        if isinstance(database, SqliteDatabase):
            if os.path.exists(database.database):
                os.remove(database.database)

            backup_database = str(database.database) + '.backup'
            if os.path.exists(backup_database):
                shutil.copy(
                    backup_database,
                    database.database
                )
                simulator_logger.info('Use backup database.')

        else:
            raise FileExistsError()

        simulator_logger.info(
            f'Old simulator data has been removed. '
            f'{time() - _time:.1f}s'
        )

    # Create simulator database if not available
    if not os.path.exists(config_database.database):
        create_config_database()

    if StoreModel.table_exists():
        if not rewrite and StoreModel.select().count() > 1:
            raise FileExistsError('Database is already exists.')

    else:
        _time = time()
        initial_datetime = datetime(
            GlobalContext.INITIAL_DATE.year,
            GlobalContext.INITIAL_DATE.month,
            GlobalContext.INITIAL_DATE.day
        )
        simulator_logger.info(
            f"Preparing {type(database).__name__.split('Database')[0]} "
            "database for the simulator..."
        )
        create_database(initial_datetime)
        simulator_logger.info(
            f'Simulator database is ready. '
            f'{time() - _time:.1f}s'
        )

        if isinstance(database, SqliteDatabase):
            shutil.copy(
                database.database,
                str(database.database) + '.backup'
            )

    simulator = Simulator(seed=seed)
    simulator.save(save_dir)
    return simulator
