"""The types module contains common type annotation definitions."""

from pathlib import Path
import typing as t

from typing_extensions import Literal


T_PATHLIKE = t.Union[str, Path]
T_LS_FILTER_FN = t.Callable[[Path], bool]
T_LS_FILTERABLE = t.Union[str, t.Pattern, T_LS_FILTER_FN]
T_LS_FILTER = t.Union[T_LS_FILTERABLE, t.Iterable[T_LS_FILTERABLE]]
T_STD_FILE = t.Union[int, t.IO[t.Any]]
T_RUN_ARGS = t.Union[str, bytes, None, t.Iterable[t.Union[str, bytes, None]]]
T_READ_ONLY_TEXT_MODES = Literal["r", "rt", "tr"]
T_READ_ONLY_BIN_MODES = Literal["rb", "br"]

READ_ONLY_TEXT_MODES = t.get_args(T_READ_ONLY_TEXT_MODES)
READ_ONLY_BIN_MODES = t.get_args(T_READ_ONLY_BIN_MODES)
READ_ONLY_MODES = READ_ONLY_TEXT_MODES + READ_ONLY_BIN_MODES
