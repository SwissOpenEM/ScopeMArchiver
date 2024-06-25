import prefect
import logging

import prefect.logging


def getLogger():
    try:
        prefect_logger = prefect.get_run_logger()
        return prefect_logger
    except Exception:
        return logging.getLogger()


__attributes__ = [
    "getLogger"
]
