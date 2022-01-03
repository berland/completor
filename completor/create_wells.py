"""Module for creating completion structure."""

from __future__ import annotations

import numpy as np
import pandas as pd

from completor import completion
from completor.constants import SegmentCreationMethod
from completor.logger import logger
from completor.read_casefile import ReadCasefile
from completor.read_schedule import fix_compsegs_by_priority

try:
    import numpy.typing as npt
except ImportError:
    pass


class CreateWells:
    """
    Class for creating well completion structure.

    Inputs to this class are two objects:

    1. class ReadCasefile
    2. class ReadSchedule

    Args:
        case: ReadCasefile class

    Attributes:
        schedule: ReadSchedule class
        active_wells (List): Active wells defined in the case file
        method (SegmentCreationMethod): Method for segment creation
        well_name (str): Well name (in loop)
        laterals (np.ndarray[int]): List of lateral number of the well in loop
        df_completion (pd.DataFrame): Completion data frame in loop
        df_reservoir (pd.DataFrame): COMPDAT and COMPSEGS data frame fusion in loop
        df_welsegs_header (pd.DataFrame): WELSEGS first record
        df_welsegs_content (pd.DataFrame): WELSEGS second record
        df_mdtvd (pd.DataFrame): Data frame of MD and TVD relationship
        df_tubing_segments (pd.DataFrame): Tubing segment data frame
        df_well (pd.DataFrame): Data frame after completion
        df_well_all (pd.DataFrame): Data frame (df_well) for all laterals
            after completion
        df_reservoir_all (pd.DataFrame): df_reservoir for all laterals
    """

    def __init__(self, case: ReadCasefile):
        """Initialize CreateWells."""
        self.well_name: str | None = None
        self.df_reservoir = pd.DataFrame()
        self.df_mdtvd = pd.DataFrame()
        self.df_completion = pd.DataFrame()
        self.df_tubing_segments = pd.DataFrame()
        self.df_well = pd.DataFrame()
        self.df_compdat = pd.DataFrame()
        self.df_well_all = pd.DataFrame()
        self.df_reservoir_all = pd.DataFrame()
        self.df_welsegs_header = pd.DataFrame()
        self.df_welsegs_content = pd.DataFrame()
        self.laterals: list[int] = []

        self.case: ReadCasefile = case
        self.active_wells = self._active_wells()
        self.method = self._method()

    def update(self, well_name: str, schedule: completion.WellSchedule) -> None:
        """
        Update class variables in CreateWells.

        Args:
            well_name: Well name
            schedule: ReadSchedule object

        """
        self.well_name = well_name
        self._active_laterals()
        for lateral in self.laterals:
            self.select_well(schedule, lateral)
            self.well_trajectory()
            self.define_annulus_zone()
            self.create_tubing_segments()
            self.insert_missing_segments()
            self.complete_the_well()
            self.get_devices()
            self.correct_annulus_zone()
            self.connect_cells_to_segments()
            self.add_well_lateral_column(lateral)
            self.combine_df(lateral)

    def _active_wells(self) -> npt.NDArray[np.unicode_]:
        """
        Get a list of active wells specified by users.

        If the well has annulus content set to gravel pack and the well is perforated,
        Completor will not add a device layer. In fact, completor do nothing to
        gravel-packed perforated wells by default. This behavior can be changed by
        setting the GP_PERF_DEVICELAYER keyword in the case file to true.

        ``get_activewells`` uses the case class DataFrame property ``completion_table``
        with a format as shown in the function
        ``read_casefile.ReadCasefile.read_completion``.

        Returns:
            Active wells
        """
        # Need to check completion of all wells in completion table to remove
        # GP-PERF type wells
        active_wells = list(set(self.case.completion_table["WELL"]))
        # We cannot update a list while iterating of it
        for well_name in active_wells.copy():
            # Annulus content of each well
            ann_series = self.case.completion_table[self.case.completion_table["WELL"] == well_name]["ANNULUS"]
            type_series = self.case.completion_table[self.case.completion_table["WELL"] == well_name]["DEVICETYPE"]
            gp_check = not ann_series.isin(["OA"]).any()
            perf_check = not type_series.isin(["AICD", "AICV", "DAR", "ICD", "VALVE", "ICV"]).any()
            if gp_check and perf_check and not self.case.gp_perf_devicelayer:
                # De-activate wells with GP_PERF if instructed to do so:
                active_wells.remove(well_name)
            if not active_wells:
                logger.warning(
                    "There are no active wells for Completor to work on. E.g. all wells are defined with Gravel Pack "
                    "(GP) and valve type PERF. If you want these wells to be active set GP_PERF_DEVICELAYER to TRUE."
                )
                return np.array([])
        return np.array(active_wells)

    def _method(self) -> SegmentCreationMethod:
        """
        Define how the user wants to create segments.

        Returns:
            Creation method enum OR ValueError

        Raises:
            ValueError: If method is not one of the defined methods
        """
        if isinstance(self.case.segment_length, float):
            if float(self.case.segment_length) > 0.0:
                return SegmentCreationMethod.FIX
            if float(self.case.segment_length) == 0.0:
                return SegmentCreationMethod.CELLS
            if self.case.segment_length < 0.0:
                return SegmentCreationMethod.USER
            else:
                raise ValueError(
                    f"Unrecognized method '{self.case.segment_length}' in "
                    "SEGMENTLENGTH keyword. The value should be one of: "
                    "'WELSEGS', 'CELLS', 'USER', or a number: -1 for 'USER', "
                    "0 for 'CELLS', positive number for 'FIX'."
                )

        elif isinstance(self.case.segment_length, str):
            if "welsegs" in self.case.segment_length.lower() or "infill" in self.case.segment_length.lower():
                return SegmentCreationMethod.WELSEGS
            if "cell" in self.case.segment_length.lower():
                return SegmentCreationMethod.CELLS
            if "user" in self.case.segment_length.lower():
                return SegmentCreationMethod.USER
            else:
                raise ValueError(
                    f"Unrecognized method '{self.case.segment_length}' in SEGMENTLENGTH keyword. "
                    "The value should be one of: "
                    "'WELSEGS', 'CELLS', 'USER', or a number: -1 for 'USER', 0 for 'CELLS', positive number for 'FIX'."
                )
        else:
            raise ValueError(
                f"Unrecognized type of '{self.case.segment_length}' in "
                "SEGMENTLENGTH keyword. The keyword must either be float or string."
            )

    def _active_laterals(self) -> None:
        """
        Get a list of lateral numbers for the well.

        ``get_active_laterals`` uses the case class DataFrame property
        ``completion_table`` with a format as shown in the function
        ``read_casefile.ReadCasefile.read_completion``.
        """
        self.laterals = list(
            self.case.completion_table[self.case.completion_table["WELL"] == self.well_name]["BRANCH"].unique()
        )

    def select_well(self, schedule: completion.WellSchedule, lateral: int) -> None:
        """
        .. _select_well:

        Filter all of the required DataFrames for this well and its laterals.

        The function sets the class property DataFrames df_completion, df_welsegs_header
        and df_welsegs_content, and df_reservoir, with the following formats:

        .. _df_completion:
        .. list-table:: df_completion
           :widths: 10 10
           :header-rows: 1

           * - COLUMNS
             - TYPE
           * - WELL
             - str
           * - BRANCH
             - int
           * - STARTMD
             - float
           * - ENDMD
             - float
           * - INNER_ID
             - float
           * - OUTER_ID
             - float
           * - ROUGHNESS
             - float
           * - ANNULUS
             - str
           * - NVALVEPERJOINT
             - float
           * - DEVICETYPE
             - str
           * - ANNULUS_ZONE
             - int

        .. _df_welsegs_header:
        .. list-table:: df_welsegs_header (WELSEGS header)
           :widths: 10 10
           :header-rows: 1

           * - COLUMN
             - TYPE
           * - WELL
             - str
           * - SEGMENTTVD
             - float
           * - SEGMENTMD
             - float
           * - WBVOLUME
             - float
           * - INFOTYPES
             - str
           * - PDROPCOMP
             - str
           * - MPMODEL
             - str
           * - ITEM8
             - float
           * - ITEM9
             - float
           * - ITEM10
             - float
           * - ITEM11
             - float
           * - ITEM12
             - float

        .. _df_welsegs_content:
        .. list-table:: df_welsegs_content (WELSEGS record)
           :widths: 10 10
           :header-rows: 1

           * - COLUMNS
             - TYPE
           * - TUBINGSEGMENT
             - int
           * - TUBINGSEGMENT2
             - int
           * - TUBINGBRANCH
             - int
           * - TUBINGOUTLET
             - int
           * - TUBINGMD
             - float
           * - TUBINGTVD
             - float
           * - TUBINGID
             - float
           * - TUBINGROUGHNESS
             - float
           * - CROSS
             - float
           * - VSEG
             - float
           * - ITEM11
             - float
           * - ITEM12
             - float
           * - ITEM13
             - float
           * - ITEM14
             - float
           * - ITEM15
             - float

        .. _df_reservoir:
        .. list-table:: df_reservoir
           :widths: 10 10
           :header-rows: 1

           * - COLUMNS
             - TYPE
           * - I
             - int
           * - J
             - int
           * - K
             - int
           * - STARTMD
             - float
           * - ENDMD
             - float
           * - COMPSEGS_DIRECTION
             - str
           * - ENDGRID
             -
           * - PERFDEPTH
             - float
           * - THERM
             -
           * - SEGMENT
             - int
           * - K2
             - int
           * - STATUS
             - str
           * - SATNUM
             - int
           * - CF
             - float
           * - DIAM
             - float
           * - KH
             - float
           * - SKIN
             - float
           * - DFACT
             - float
           * - COMPDAT_DIRECTION
             - str
           * - RO
             - float
           * - MD
             - float
           * - TUB_MD
             - float
           * - NDEVICES
             - float
           * - ANNULUS_ZONE
             - int
           * - WELL
             - str
           * - LATERAL
             - int

        See the Eclipse Reference Manual for further details on column and row
        definitions.
        """
        if self.well_name is None:
            raise ValueError("No well name given")

        self.df_completion = self.case.get_completion(self.well_name, lateral)
        self.df_welsegs_header, self.df_welsegs_content = schedule.get_welsegs(self.well_name, lateral)
        df_compsegs = schedule.get_compsegs(self.well_name, lateral)
        df_compdat = schedule.get_compdat(self.well_name)
        self.df_reservoir = pd.merge(df_compsegs, df_compdat, how="inner", on=["I", "J", "K"])

        # remove WELL column in the df_reservoir
        self.df_reservoir.drop(["WELL"], inplace=True, axis=1)
        # if multiple occurrences of same IJK in compdat/compsegs --> keep last
        # as Eclipse does.
        self.df_reservoir.drop_duplicates(subset="STARTMD", keep="last", inplace=True)
        self.df_reservoir.reset_index(inplace=True)
