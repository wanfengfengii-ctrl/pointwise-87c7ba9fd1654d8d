from dataclasses import dataclass


def validate_identifier(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or not value.isprintable():
        raise ValueError('identity must be nonblank printable text')
    return value


@dataclass(frozen=True)
class MarkerPair:
    first: str
    second: str

    def __post_init__(self) -> None:
        first = validate_identifier(self.first)
        second = validate_identifier(self.second)
        if first == second:
            raise ValueError('the two marker identities must differ')
        if first > second:
            object.__setattr__(self, 'first', second)
            object.__setattr__(self, 'second', first)

    def as_tuple(self) -> tuple[str, str]:
        return self.first, self.second

    def contains(self, marker: str) -> bool:
        return marker in self.as_tuple()


def make_marker_pair(markers) -> MarkerPair:
    if isinstance(markers, MarkerPair):
        return markers
    if not isinstance(markers, (tuple, list)) or len(markers) != 2:
        raise ValueError('exactly two marker identities are required')
    return MarkerPair(*markers)
