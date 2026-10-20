from pathlib import Path

from pdi_lab.cli import CliOptions
from pdi_lab.contract import validate_contract
from pdi_lab.image_io import read_image, write_image
from pdi_lab.kernel import read_kernel
from pdi_lab.parameters import BorderStrategy, parameter_as_border, parameter_as_int
from pdi_lab.result_io import write_histogram_csv, write_json_object


def test_typed_parameters_and_contract():
    options = CliOptions(
        operation="quantize",
        input="images/input/m1_gray_ramp_256.png",
        output="images/output/out.png",
        parameters={"levels": "8"},
    )
    assert validate_contract(options).ok
    assert parameter_as_int(options, "levels") == 8

    options.parameters["levels"] = "3"
    assert not validate_contract(options).ok

    convolution = CliOptions(
        operation="convolution",
        input="images/input/m1_gray_5x5.png",
        output="images/output/out.png",
        parameters={
            "kernel": "kernels/identity_3x3.txt",
            "border": "replicate",
        },
    )
    assert validate_contract(convolution).ok
    assert parameter_as_border(convolution) is BorderStrategy.REPLICATE


def test_image_read_and_write(tmp_path: Path):
    image = read_image("images/input/m1_color_2x2.png")
    assert image.shape[0] == 2
    assert image.shape[1] == 2

    output = tmp_path / "nested" / "image.png"
    write_image(str(output), image)
    assert output.exists()


def test_kernel_csv_and_json(tmp_path: Path):
    kernel_path = tmp_path / "identity.txt"
    kernel_path.write_text("0 0 0\n0 1 0\n0 0 0\n", encoding="utf-8")

    kernel = read_kernel(kernel_path)
    assert kernel.size == 3
    assert kernel.radius == 1
    assert kernel.at(1, 1) == 1.0

    histogram = [0] * 256
    histogram[0] = 2
    histogram[255] = 1
    csv_path = tmp_path / "nested" / "histogram.csv"
    write_histogram_csv(csv_path, histogram)
    assert csv_path.exists()
    assert csv_path.read_text(encoding="utf-8").startswith("intensity,count")

    json_path = tmp_path / "nested" / "metadata.json"
    write_json_object(json_path, {"operation": "test", "status": "ok"})
    assert json_path.exists()
