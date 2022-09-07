"""Common Completor test functions."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from completor import main, parse  # type: ignore
from completor.read_schedule import fix_compsegs, fix_welsegs  # type: ignore
from completor.utils import clean_file_lines  # type: ignore


def open_files_run_create(
    case: Path | str, schedule: Path | str, output: Path | str, show_figure: bool = False
) -> None:
    """
    Open files supplied as a path and convert the data to a string.

    Then run main.py's create function with the data.
    """

    if isinstance(case, Path):
        with open(case, encoding="utf-8") as file:
            case = file.read()

    if isinstance(schedule, Path):
        with open(schedule, encoding="utf-8") as file:
            schedule = file.read()

    if isinstance(output, Path):
        with open(output, encoding="utf-8") as file:
            output = file.read()

        main.create(case, schedule, output, show_figure)
    else:
        main.create(case, schedule, output)


def assert_results(true_file: str | Path, test_file: str | Path, check_exact=False, relative_tolerance=0.0001) -> None:
    """
    Assert the final Completor output.

    Arguments:
        true_file: True solution file
        test_file: Completor output file
        check_exact: Whether to compare number exactly
        relative_tolerance: Relative tolerance, only used when check_exact is False

    Note1: The df's are sorted so that the order of input is *not* important.
        Also, the index is set to well so that the original order is not used as index.
    Note2: We do the comparison numerically, so we dont care about 4th decimal place.
        Use global variables CHECK_EXACT and N_DIGITS for this purpose.
    Note3: WELSPECS is not included in the comparison since this keyword is left
        untouched by completor.
    """

    if isinstance(true_file, Path):
        with open(true_file, encoding="utf-8") as file:
            true_output = ReadSchedule(file.read())
    else:
        true_output = ReadSchedule(true_file)

    # test COMPDAT, COMPSEGS and WELSEGS
    with open(test_file, encoding="utf-8") as file:
        test_output = ReadSchedule(file.read())
