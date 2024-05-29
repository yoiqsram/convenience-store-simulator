# from celery import Celery
# from pathlib import Path
# from typing import List


# app = Celery(
#     'simulator',
#     broker='redis://:@simulator-redis:6379/0',
#     backend='rpc://',
#     include=[ 'simulator.core.environment' ]
# )


# @app.task
# def run_environment(
#         env_db_path: Path,
#         agent_ids: List[int] = None,
#         **kwargs
#     ):
#     simulator = load_environment(
#         env_db_path,
#         agent_ids
#     )
#     simulator.run(**kwargs)
