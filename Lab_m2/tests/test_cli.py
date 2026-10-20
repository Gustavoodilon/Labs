from pdi_lab import exit_code
from pdi_lab.cli import parse_cli
from pdi_lab.contract import validate_contract
from pdi_lab.operations import is_known_operation


def test_parses_and_validates_known_operation():
    options = parse_cli(
        [
            "--operation",
            "negative",
            "--input",
            "images/input/m1_gray_ramp_256.png",
            "--output",
            "images/output/out.png",
        ]
    )
    assert options.operation == "negative"
    assert is_known_operation(options.operation)
    assert validate_contract(options).ok
    assert not is_known_operation("x")


def test_output_is_optional_only_for_inspect():
    inspect = parse_cli(
        [
            "--operation",
            "inspect",
            "--input",
            "images/input/m1_color_2x2.png",
        ]
    )
    negative = parse_cli(
        [
            "--operation",
            "negative",
            "--input",
            "images/input/m1_gray_ramp_256.png",
        ]
    )
    assert validate_contract(inspect).ok
    assert not validate_contract(negative).ok


def test_missing_input_returns_read_error():
    options = parse_cli(
        [
            "--operation",
            "negative",
            "--input",
            "images/input/nao_existe.png",
            "--output",
            "images/output/out.png",
        ]
    )
    result = validate_contract(options)
    assert not result.ok
    assert result.code == exit_code.READ_ERROR
