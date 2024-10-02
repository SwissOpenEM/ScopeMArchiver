import prefect.cli.concurrency_limit as concurrency_limit

from pydantic_settings import (
    BaseSettings,
)


class ConcurrencyLimits(BaseSettings):
    LTS_FREE_LIMIT: int = 1
    LTS_FREE_TAG: str = "wait-for-free-space-in-lts"

    MOVE_TO_LTS_LIMIT: int = 1
    MOVE_TO_LTS_TAG: str = "move-datablocks-to-lts"

    VERIFY_LTS_LIMIT: int = 1
    VERIFY_LTS_TAG: str = "verify-datablocks-in-lts"

    LTS_TO_RETRIEVAL_LIMIT: int = 1
    LTS_TO_RETRIEVAL_TAG: str = "copy-from-LTS-to-retrieval"


def register_concurrency_limits(limits: ConcurrencyLimits):
    model = limits.model_dump()
    print(f"Applying concurrency limits: {model}")
    stubs = [f.strip("_TAG") for f in model.keys() if f.endswith("_TAG")]
    for stub in stubs:
        tag = str(model.get(stub + "_TAG"))
        limit = int(model.get(stub + "_LIMIT"))
        try:
            concurrency_limit.create(tag=tag,
                                     concurrency_limit=limit)
        except Exception as e:
            print(f"failed to apply concurrency limit {tag}: {e}")
