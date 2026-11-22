import json
import sqlite3
from dataclasses import dataclass
from fractions import Fraction

from bench.observations import ReadingInterval
from bench.precedence import PrecedenceGraph
from panel.batches import make_batch
from panel.trays import TrayRoster, build_roster
from reports.transactions import write_transaction


@dataclass(frozen=True)
class RevisionSnapshot:
    revision_id: int
    roster: TrayRoster
    readings: tuple[tuple[str, ReadingInterval], ...]
    graph: PrecedenceGraph


def initialize_revisions(db: sqlite3.Connection) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS bench_revisions (
        revision_id INTEGER PRIMARY KEY,
        batch_id TEXT NOT NULL,
        tray_id TEXT NOT NULL,
        unit TEXT NOT NULL,
        first_marker TEXT NOT NULL,
        second_marker TEXT NOT NULL,
        observations TEXT NOT NULL,
        inferred_edges TEXT NOT NULL,
        certified_edges TEXT NOT NULL,
        FOREIGN KEY (batch_id, tray_id) REFERENCES panel_trays(batch_id, tray_id)
    )''')


def _pack_fraction(value: Fraction) -> tuple[str, str]:
    # Hex text preserves arbitrary-size integers without conversion to SQLite REAL.
    return hex(value.numerator), hex(value.denominator)


def _unpack_fraction(value: list[str]) -> Fraction:
    numerator, denominator = value
    return Fraction(int(numerator, 16), int(denominator, 16))


def insert_revision(db: sqlite3.Connection, roster: TrayRoster,
                    readings: tuple[tuple[str, ReadingInterval], ...],
                    graph: PrecedenceGraph) -> RevisionSnapshot:
    packed = [(name, _pack_fraction(interval.lower), _pack_fraction(interval.upper))
              for name, interval in readings]
    batch = roster.batch
    with write_transaction(db):
        inserted = db.execute('''INSERT INTO bench_revisions (
            batch_id, tray_id, unit, first_marker, second_marker,
            observations, inferred_edges, certified_edges
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (
            batch.batch_id, roster.tray_id, batch.unit, *batch.markers.as_tuple(),
            json.dumps(packed), json.dumps(graph.inferred_edges), json.dumps(graph.certified_edges),
        ))
        revision_id = inserted.lastrowid
    return RevisionSnapshot(revision_id, roster, readings, graph)


def get_revision(db: sqlite3.Connection, revision_id: int) -> RevisionSnapshot:
    if type(revision_id) is not int or not 1 <= revision_id < 2**63:
        raise KeyError(revision_id)
    row = db.execute('''SELECT batch_id, tray_id, unit, first_marker, second_marker,
                              observations, inferred_edges, certified_edges
                       FROM bench_revisions WHERE revision_id = ?''',
                     (revision_id,)).fetchone()
    if row is None:
        raise KeyError(revision_id)
    batch_id, tray_id, unit, first, second, observations, inferred, certified = row
    readings = tuple((name, ReadingInterval(_unpack_fraction(lower), _unpack_fraction(upper)))
                     for name, lower, upper in json.loads(observations))
    batch = make_batch(batch_id, (first, second), unit)
    roster = build_roster(batch, tray_id, (name for name, _ in readings))
    graph = PrecedenceGraph(roster.members, tuple(map(tuple, json.loads(inferred))),
                            tuple(map(tuple, json.loads(certified))))
    return RevisionSnapshot(revision_id, roster, readings, graph)
