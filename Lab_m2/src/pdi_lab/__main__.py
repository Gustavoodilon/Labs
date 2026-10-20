from __future__ import annotations

import sys

from . import CONTRACT_VERSION, __version__, exit_code
from .cli import parse_cli, version_requested
from .contract import validate_contract
from .errors import PdiError
from .operations import run_operation


def main(argv=None) -> int:
    try:
        options = parse_cli(argv)

        if version_requested(options):
            print(f"pdi_lab {__version__} contract={CONTRACT_VERSION}")
            return exit_code.SUCCESS

        validation = validate_contract(options)
        if not validation.ok:
            print(f"Erro: {validation.message}", file=sys.stderr)
            return validation.code

        return run_operation(options)
    except PdiError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return error.code
    except (ValueError, OSError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return exit_code.GENERAL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
