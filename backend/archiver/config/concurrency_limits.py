import prefect.cli.concurrency_limit as concurrency_limit

from pydantic_settings import (
    BaseSettings,
)


class ConcurrencyLimits(BaseSettings):
    LTS_FREE_LIMIT: int = 1
    LTS_FREE_TAG: str = "wait-for-free-space-in-lts"

    LTS_WRITE_LIMIT: int = 1
    LTS_WRITE_TAG: str = "write-to-lts-share"

    LTS_READ_LIMIT: int = 1
    LTS_READ_TAG: str = "read-from-lts-share"


def register_concurrency_limits(limits: ConcurrencyLimits):
    model = limits.model_dump()
    print(f"Applying concurrency limits: {model}")
    stubs = [f.strip("_TAG") for f in model.keys() if f.endswith("_TAG")]
    for stub in stubs:
        tag = str(model.get(stub + "_TAG"))
        limit = int(model.get(stub + "_LIMIT"))
        try:
            concurrency_limit.create(tag=tag, concurrency_limit=limit)
        except Exception as e:
            print(f"failed to apply concurrency limit {tag}: {e}")
