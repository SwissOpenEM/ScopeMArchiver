import prefect
import logging
import functools
import os

import prefect.logging


def getLogger():
    if "PYTEST_CURRENT_TEST" in os.environ:
        return logging.getLogger(name="TestLogger")
    else:
        prefect_logger = prefect.get_run_logger()
        return prefect_logger


__attributes__ = ["getLogger"]


def log(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        args_repr = [repr(a) for a in args]
        kwargs_repr = [f"{k}={repr(v)}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)
        getLogger().info(f"Function {func.__name__}({signature})")
        value = func(*args, **kwargs)
        getLogger().info(f"Function {func.__name__}() - returned {repr(value)}")
        return value

    return wrapper_decorator
