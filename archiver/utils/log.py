import prefect


def getLogger():
    return prefect.get_run_logger()


__attributes__ = [
    "getLogger"
]
