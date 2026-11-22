import sqlite3

from bench.consistency import topological_order
from bench.observations import normalize_observations
from bench.precedence import build_precedence
from bench.revision_store import RevisionSnapshot, insert_revision
from panel.registry import read_roster


def record_revision(db: sqlite3.Connection, batch_id: str, tray_id: str,
                    observations, certificates=()) -> RevisionSnapshot:
    roster = read_roster(db, batch_id, tray_id)
    readings = normalize_observations(roster, observations)
    graph = build_precedence(readings, certificates)
    topological_order(graph)
    return insert_revision(db, roster, readings, graph)
