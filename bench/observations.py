from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from panel.markers import validate_identifier
from panel.trays import TrayRoster


def _endpoint(value) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, str, Fraction)):
        raise ValueError('an endpoint requires an integer, Fraction or rational text')
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f'invalid rational endpoint {value!r}') from exc


@dataclass(frozen=True)
class ReadingInterval:
    lower: Fraction
    upper: Fraction

    def __post_init__(self) -> None:
        if self.lower > self.upper:
            raise ValueError('lower endpoint exceeds upper endpoint')


def normalize_observations(roster: TrayRoster, rows: Iterable) -> tuple[tuple[str, ReadingInterval], ...]:
    allowed = set(roster.members)
    readings = {}
    try:
        rows = iter(rows)
    except TypeError as exc:
        raise ValueError('observations must contain reading rows') from exc
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != 3:
            raise ValueError('each reading requires a specimen and two endpoints')
        name, lower, upper = row
        validate_identifier(name)
        if name not in allowed:
            raise ValueError(f'specimen outside the tray roster: {name!r}')
        if name in readings:
            raise ValueError(f'duplicate reading for {name!r}')
        readings[name] = ReadingInterval(_endpoint(lower), _endpoint(upper))
    missing = allowed.difference(readings)
    if missing:
        raise ValueError(f'missing readings for {sorted(missing)!r}')
    return tuple((name, readings[name]) for name in roster.members)
