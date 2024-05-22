import logging
from datetime import datetime
from logging import NOTSET, INFO, DEBUG, WARNING, ERROR

from .context import GlobalContext


def simulator_log_format(*args, dt: datetime, sep=' '):
    return f"[SIM-TIME {dt.isoformat(sep=' ')}] {sep.join([ str(arg) for arg in args ])}"


def get_logger(
        name: str,
        level: int = INFO
    ) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(level)
    return logger


database_logger = get_logger('peewee')
if GlobalContext.DEBUG_DATABASE:
    database_logger.setLevel(DEBUG)

simulator_logger = get_logger('simulator')
if GlobalContext.DEBUG_SIMULATOR:
    simulator_logger.setLevel(DEBUG)

store_logger = get_logger('store')
if GlobalContext.DEBUG_STORE:
    store_logger.setLevel(DEBUG)

order_logger = get_logger('order')
if GlobalContext.DEBUG_ORDER:
    order_logger.setLevel(DEBUG)
