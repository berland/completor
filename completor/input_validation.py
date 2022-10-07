"""Functions to validate user input for Completor."""

from __future__ import annotations

import numpy as np
import pandas as pd

from completor.utils import abort


def set_default_packer_section(df_comp: pd.DataFrame) -> pd.DataFrame:
    """
    Set default value for the packer section.

    This procedure sets the default values of the
    completion_table in read_casefile class if the annulus is PA (packer)

    Args:
        df_comp: COMPLETION table

    Returns:
        Updated COMPLETION

    The format of the COMPLETION table DataFrame is shown in
    ``read_casefile.ReadCasefile.read_completion``.
    """
    # Set default values for packer sections
    df_comp["INNER_ID"] = np.where(df_comp["ANNULUS"] == "PA", 0.0, df_comp["INNER_ID"])
    df_comp["OUTER_ID"] = np.where(df_comp["ANNULUS"] == "PA", 0.0, df_comp["OUTER_ID"])
    df_comp["ROUGHNESS"] = np.where(df_comp["ANNULUS"] == "PA", 0.0, df_comp["ROUGHNESS"])
    df_comp["NVALVEPERJOINT"] = np.where(df_comp["ANNULUS"] == "PA", 0.0, df_comp["NVALVEPERJOINT"])
    df_comp["DEVICETYPE"] = np.where(df_comp["ANNULUS"] == "PA", "PERF", df_comp["DEVICETYPE"])
    df_comp["DEVICENUMBER"] = np.where(df_comp["ANNULUS"] == "PA", 0, df_comp["DEVICENUMBER"])
    return df_comp


def set_default_perf_section(df_comp: pd.DataFrame) -> pd.DataFrame:
    """
    Set the default value for the PERF section.

    Args:
        df_comp : COMPLETION table

    Returns:
        Updated COMPLETION

    The format of the COMPLETION table DataFrame is shown in
    ``read_casefile.ReadCasefile.read_completion``.
    """
    # set default value of the PERF section
    df_comp["NVALVEPERJOINT"] = np.where(df_comp["DEVICETYPE"] == "PERF", 0.0, df_comp["NVALVEPERJOINT"])
    df_comp["DEVICENUMBER"] = np.where(df_comp["DEVICETYPE"] == "PERF", 0, df_comp["DEVICENUMBER"])
    return df_comp


def check_default_non_packer(df_comp: pd.DataFrame) -> pd.DataFrame:
    """
    Check default values for non-packers.

    This procedure checks if the user enters default values 1*
    for non-packer annulus content, e.g. OA, GP.
    If this is the case, the program will report errors.

    Args:
        df_comp: COMPLETION table

    Returns:
        Updated COMPLETION

    Raises:
        SystemExit: If default value '1*' in non-packer columns

    The format of the COMPLETION table DataFrame is shown in
    ``read_casefile.ReadCasefile.read_completion``.
    """
    df_comp = df_comp.copy(True)
    # set default value of roughness
    df_comp["ROUGHNESS"].replace("1*", 1e-5, inplace=True)
    df_nonpa: pd.DataFrame = df_comp[df_comp["ANNULUS"] != "PA"]
    df_columns = df_nonpa.columns.to_numpy()
    for column in df_columns:
        if "1*" in df_nonpa[column]:
            raise abort(f"No default value 1* is allowed in {column} entry.")
    return df_comp


def set_format_completion(df_comp: pd.DataFrame) -> pd.DataFrame:
    """
    Set the column data format.

    Args:
        df_comp: COMPLETION table

    Returns:
        Updated COMPLETION table

    The format of the COMPLETION table DataFrame is shown in
    ``read_casefile.ReadCasefile.read_completion``.
    """
    return df_comp.astype(
        {
            "WELL": str,
            "BRANCH": np.int64,
            "STARTMD": np.float64,
            "ENDMD": np.float64,
            "INNER_ID": np.float64,
            "OUTER_ID": np.float64,
            "ROUGHNESS": np.float64,
            "ANNULUS": str,
            "NVALVEPERJOINT": np.float64,
            "DEVICETYPE": str,
            "DEVICENUMBER": np.int64,
        }
    )


def assess_completion(df_comp: pd.DataFrame):
    """
    Assess the user completion inputs.

    Args:
        df_comp: COMPLETION table

    The format of the COMPLETION table DataFrame is shown in
    ``read_casefile.ReadCasefile.read_completion``.
    """
    list_wells = df_comp["WELL"].unique()
    for well_name in list_wells:
        df_well = df_comp[df_comp["WELL"] == well_name]
        list_branches = df_well["BRANCH"].unique()
        for branch in list_branches:
            df_comp = df_well[df_well["BRANCH"] == branch]
            nrow = df_comp.shape[0]
            for idx in range(0, nrow):
                _check_for_errors(df_comp, well_name, idx)


def _check_for_errors(df_comp: pd.DataFrame, well_name: str, idx: int):
    """
    Check for errors in completion.

    Args:
        df_comp: Completion data frame
        well_name: Well name
        idx: Index

    Raises:
        SystemExit:
            If packer segments is missing length
            If non-packer segments is missing length
            If the completion description is incomplete for some range of depth
            If the completion description is overlapping for some range of depth
    """
    if df_comp["ANNULUS"].iloc[idx] == "PA" and (df_comp["STARTMD"].iloc[idx] != df_comp["ENDMD"].iloc[idx]):
        raise abort("Packer segments must not have length")

    if (
        df_comp["ANNULUS"].iloc[idx] != "PA"
        and df_comp["DEVICETYPE"].iloc[idx] != "ICV"
        and df_comp["STARTMD"].iloc[idx] == df_comp["ENDMD"].iloc[idx]
    ):
        raise abort("Non packer segments must have length")

    if idx > 0:
        if df_comp["STARTMD"].iloc[idx] > df_comp["ENDMD"].iloc[idx - 1]:
            raise abort(
                f"Incomplete completion description in well {well_name} from depth {df_comp['ENDMD'].iloc[idx - 1]} "
                f"to depth {df_comp['STARTMD'].iloc[idx]}"
            )

        if df_comp["STARTMD"].iloc[idx] < df_comp["ENDMD"].iloc[idx - 1]:
            raise abort(
                f"Overlapping completion description in well {well_name} from depth {df_comp['ENDMD'].iloc[idx - 1]} "
                f"to depth {(df_comp['STARTMD'].iloc[idx])}"
            )
    if df_comp["DEVICETYPE"].iloc[idx] not in ["PERF", "AICD", "ICD", "VALVE", "DAR", "AICV", "ICV"]:
        raise abort(
            f"{df_comp['DEVICETYPE'].iloc[idx]} not a valid device type. "
            "Valid types are PERF, AICD, ICD, VALVE, DAR, AICV, and ICV."
        )
    if df_comp["ANNULUS"].iloc[idx] not in ["GP", "OA", "PA"]:
