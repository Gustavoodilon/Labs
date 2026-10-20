from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import exit_code
from .cli import CliOptions
from .m2_params import (
    MissingArgument,
    analyze_params,
    segment_params,
    validate_output_is_lossless,
)
from .operations import is_known_operation
from .parameters import (
    has_parameter,
    parameter_as_border,
    parameter_as_float,
    parameter_as_int,
    parameter_as_path,
)


@dataclass(frozen=True)
class ValidationResult:
    code: int = exit_code.SUCCESS
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.code == exit_code.SUCCESS


def _require(options: CliOptions, name: str) -> ValidationResult:
    if not has_parameter(options, name):
        return ValidationResult(
            exit_code.INVALID_ARGUMENTS,
            f"A operacao '{options.operation}' exige --{name}.",
        )
    return ValidationResult()


def _validate_parameters(options: CliOptions) -> ValidationResult:
    try:
        if options.operation == "quantize":
            required = _require(options, "levels")
            if not required.ok:
                return required
            levels = parameter_as_int(options, "levels")
            if levels not in {2, 4, 8, 16}:
                return ValidationResult(
                    exit_code.INVALID_PARAMETER,
                    "--levels deve ser 2, 4, 8 ou 16.",
                )

        elif options.operation == "brightness":
            required = _require(options, "value")
            if not required.ok:
                return required
            parameter_as_int(options, "value")

        elif options.operation == "contrast":
            required = _require(options, "alpha")
            if not required.ok:
                return required
            if parameter_as_float(options, "alpha") <= 0.0:
                return ValidationResult(
                    exit_code.INVALID_PARAMETER,
                    "--alpha deve ser maior que zero.",
                )

        elif options.operation == "threshold":
            required = _require(options, "threshold")
            if not required.ok:
                return required
            threshold = parameter_as_int(options, "threshold")
            if not 0 <= threshold <= 255:
                return ValidationResult(
                    exit_code.INVALID_PARAMETER,
                    "--threshold deve estar entre 0 e 255.",
                )

        elif options.operation == "convolution":
            required = _require(options, "kernel")
            if not required.ok:
                return required
            required = _require(options, "border")
            if not required.ok:
                return required

            kernel_path = parameter_as_path(options, "kernel")
            if not Path(kernel_path).is_file():
                return ValidationResult(
                    exit_code.READ_ERROR,
                    f"Nao foi possivel abrir o kernel: {kernel_path}",
                )
            parameter_as_border(options)

        elif options.operation == "mean_filter":
            required = _require(options, "size")
            if not required.ok:
                return required
            required = _require(options, "border")
            if not required.ok:
                return required
            size = parameter_as_int(options, "size")
            if size not in {3, 5}:
                return ValidationResult(
                    exit_code.INVALID_PARAMETER,
                    "--size deve ser 3 ou 5 para mean_filter.",
                )
            parameter_as_border(options)

        elif options.operation == "segment":
            segment_params(options)
            validate_output_is_lossless(options.output)

        elif options.operation == "analyze":
            analyze_params(options)

        elif options.operation in {"weighted_mean", "laplacian", "sobel"}:
            required = _require(options, "border")
            if not required.ok:
                return required
            parameter_as_border(options)

    except MissingArgument as error:
        return ValidationResult(exit_code.INVALID_ARGUMENTS, str(error))
    except FileNotFoundError as error:
        return ValidationResult(exit_code.READ_ERROR, str(error))
    except ValueError as error:
        return ValidationResult(exit_code.INVALID_PARAMETER, str(error))

    return ValidationResult()


def validate_contract(options: CliOptions) -> ValidationResult:
    if not options.operation:
        return ValidationResult(exit_code.INVALID_ARGUMENTS, "Informe --operation.")
    if not is_known_operation(options.operation):
        return ValidationResult(
            exit_code.UNKNOWN_OPERATION,
            f"Operacao desconhecida: {options.operation}",
        )
    if not options.input:
        return ValidationResult(exit_code.INVALID_ARGUMENTS, "Informe --input.")
    if not Path(options.input).is_file():
        return ValidationResult(
            exit_code.READ_ERROR,
            f"Nao foi possivel abrir a imagem: {options.input}",
        )
    if options.operation != "inspect" and not options.output:
        return ValidationResult(exit_code.INVALID_ARGUMENTS, "Informe --output.")

    return _validate_parameters(options)
