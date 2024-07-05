import argparse
from .variables import register_variables_from_config, PrefectVariablesModel
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='ConfigParser',
        description='Parses Variables of a .toml file as a pydantic model and registers them in Prefect.')

    parser.add_argument('-c', '--config', default=None, type=Path)

    args, _ = parser.parse_known_args()
    config = PrefectVariablesModel(_env_file=args.config)
    register_variables_from_config(config)
