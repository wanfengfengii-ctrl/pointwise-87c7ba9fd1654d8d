from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from panel.batches import Batch
from panel.markers import validate_identifier


@dataclass(frozen=True)
class TrayRoster:
    batch: Batch
    tray_id: str
    members: tuple[str, ...]


def build_roster(batch: Batch, tray_id: str, members: Iterable[str]) -> TrayRoster:
    validate_identifier(tray_id)
    if isinstance(members, (str, bytes, Mapping)):
        raise ValueError('members must be a sequence of specimen identities')
    try:
        identities = tuple(validate_identifier(member) for member in members)
    except TypeError as exc:
        raise ValueError('members must be iterable') from exc
    distinct = set(identities)
    if len(distinct) != len(identities):
        raise ValueError('duplicate specimen identity on the tray')
    if not distinct.issuperset(batch.markers.as_tuple()):
        raise ValueError('both batch markers must be on the tray')
    return TrayRoster(batch, tray_id, tuple(sorted(identities)))
