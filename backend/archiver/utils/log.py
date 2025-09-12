import prefect
import logging
import functools
import os

from prefect.context import MissingContextError


def getLogger():
    """
    Returns an logger depending on the environment:
    - Testing: returns a logger from the logging package
    - Prefect Flow: returns the logger from the prefect flow run context
    - Prefect error callback: there might not be a logger available, falls back to
        a logger from logging package
    """
    if "PYTEST_CURRENT_TEST" in os.environ:
        return logging.getLogger(name="TestLogger")
    else:
        try:
            prefect_logger = prefect.get_run_logger()
            return prefect_logger
        except MissingContextError:
            return logging.getLogger(name="FallbackLogger")
        except Exception:
            return logging.getLogger(name="FallbackLogger")


__attributes__ = ["getLogger"]


def log(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        args_repr = [repr(a) for a in args]
        kwargs_repr = [f"{k}={repr(v)}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)
        getLogger().info(f"Function {func.__name__}({signature[:500]})")
        value = func(*args, **kwargs)
        value_repr = str(value)[:200]
        getLogger().info(f"Function {func.__name__}() - returned {value_repr}")
        return value

    return wrapper_decorator


def log_debug(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        args_repr = [repr(a) for a in args]
        kwargs_repr = [f"{k}={repr(v)}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)
        getLogger().debug(f"Function {func.__name__}({signature[:500]})")
        value = func(*args, **kwargs)
        value_repr = str(value)[:200]
        getLogger().debug(f"Function {func.__name__}() - returned {value_repr}")
        return value

    return wrapper_decorator
