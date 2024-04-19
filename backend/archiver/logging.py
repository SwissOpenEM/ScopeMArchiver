import prefect
import logging


def getLogger() -> logging.Logger:
    return prefect.get_run_logger()


__attributes__ = [
    "getLogger"
]
