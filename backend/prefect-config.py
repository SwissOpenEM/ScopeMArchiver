import argparse
from config.variables import register_variables_from_config, PrefectVariablesModel
from config.concurrency_limits import ConcurrencyLimits, register_concurrency_limits
from prefect.blocks.system import Secret
from pathlib import Path
import os


def register_secrets(secrets):
    for block in secrets:
        secret_file_name = os.environ.get(block)
        if secret_file_name is None:
            raise Exception(f"Could not find environment variable {block}")
        if not block.endswith("_FILE"):
            raise Exception(
                f"Secret file name needs to end with '_FILE' got {block} instead")

        with open(secret_file_name, 'r') as f:
            secret = f.read()
            secret_block = Secret(value=secret)
            secret_block.save(name=block.strip("_FILE").lower().replace("_", "-"), overwrite=True)


def register_variables(variables):
    config = PrefectVariablesModel(_env_file=variables)
    register_variables_from_config(config)


def register_limits(limits):
    limits = ConcurrencyLimits(_env_file=limits)
    register_concurrency_limits(limits)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='ConfigParser',
        description='Parses Variables and  of a .toml file as a pydantic model and registers them in Prefect.')

    parser.add_argument('-v', '--variables', default=None, type=Path)
    parser.add_argument('-s', '--secrets', nargs='+', default=None)
    parser.add_argument('-l', '--limits', default=None, type=Path)

    args, _ = parser.parse_known_args()

    register_variables(args.variables)
    register_secrets(args.secrets)
    register_limits(args.limits)
