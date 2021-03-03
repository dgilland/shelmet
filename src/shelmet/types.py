"""The types module contains common type annotation definitions."""

from pathlib import Path
import typing as t

from typing_extensions import Literal


StrPath = t.Union[str, Path]
LsFilterFn = t.Callable[[Path], bool]
LsFilterable = t.Union[str, t.Pattern, LsFilterFn]
LsFilter = t.Union[LsFilterable, t.Iterable[LsFilterable]]
StdFile = t.Union[int, t.IO[t.Any]]
RunArgs = t.Union[str, bytes, None, t.Iterable[t.Union[str, bytes, None]]]
ReadOnlyTextMode = Literal["r", "rt", "tr"]
ReadOnlyBinMode = Literal["rb", "br"]
WriteOnlyTextMode = Literal["w", "wt", "tw", "a", "x"]
WriteOnlyBinMode = Literal["wb", "bw", "ab", "ba", "xb", "bx"]

READ_ONLY_TEXT_MODES = t.get_args(ReadOnlyTextMode)
READ_ONLY_BIN_MODES = t.get_args(ReadOnlyBinMode)
READ_ONLY_MODES = READ_ONLY_TEXT_MODES + READ_ONLY_BIN_MODES
WRITE_ONLY_TEXT_MODES = t.get_args(WriteOnlyTextMode)
WRITE_ONLY_BIN_MODES = t.get_args(WriteOnlyBinMode)
WRITE_ONLY_MODES = WRITE_ONLY_TEXT_MODES + WRITE_ONLY_BIN_MODES
