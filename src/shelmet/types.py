"""The types module contains common type annotation definitions."""

from pathlib import Path
import typing as t

from typing_extensions import Literal


def _get_literal_args(literal_type) -> tuple:  # pragma: no cover
    """Backwards compatible method to get arguments passed to ``Literal`` in lieu of
    ``typing.get_args``."""
    if hasattr(t, "get_args"):
        # Python 3.8+
        # pylint: disable=no-member
        return t.get_args(literal_type)  # type: ignore
    elif hasattr(literal_type, "__args__"):
        # Python 3.7
        return literal_type.__args__
    else:
        # Python 3.6
        return literal_type.__values__


StrPath = t.Union[str, Path]
LsFilterFn = t.Callable[[Path], bool]
LsFilterable = t.Union[str, t.Pattern, LsFilterFn]
LsFilter = t.Union[LsFilterable, t.Iterable[LsFilterable]]
StdFile = t.Union[int, t.IO[t.Any]]
RunArgs = t.Union[str, bytes, None, t.Iterable[t.Union[str, bytes, None]]]
ReadOnlyTextMode = Literal["r", "rt", "tr"]
ReadOnlyBinMode = Literal["rb", "br"]
WriteOnlyTextMode = Literal["w", "wt", "tw", "a", "at", "ta", "x", "xt", "tx"]
WriteOnlyBinMode = Literal["wb", "bw", "ab", "ba", "xb", "bx"]

READ_ONLY_TEXT_MODES = _get_literal_args(ReadOnlyTextMode)
READ_ONLY_BIN_MODES = _get_literal_args(ReadOnlyBinMode)
READ_ONLY_MODES = READ_ONLY_TEXT_MODES + READ_ONLY_BIN_MODES
WRITE_ONLY_TEXT_MODES = _get_literal_args(WriteOnlyTextMode)
WRITE_ONLY_BIN_MODES = _get_literal_args(WriteOnlyBinMode)
WRITE_ONLY_MODES = WRITE_ONLY_TEXT_MODES + WRITE_ONLY_BIN_MODES
