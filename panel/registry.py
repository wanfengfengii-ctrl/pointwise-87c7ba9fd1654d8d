import json
import sqlite3

from panel.batches import make_batch
from panel.markers import validate_identifier
from panel.trays import TrayRoster, build_roster
from reports.transactions import write_transaction


def initialize_panel(db: sqlite3.Connection) -> None:
    with write_transaction(db):
        db.execute('''CREATE TABLE IF NOT EXISTS panel_batches (
            batch_id TEXT PRIMARY KEY NOT NULL,
            unit TEXT NOT NULL,
            first_marker TEXT NOT NULL,
            second_marker TEXT NOT NULL
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS panel_trays (
            batch_id TEXT NOT NULL REFERENCES panel_batches(batch_id),
            tray_id TEXT NOT NULL,
            members TEXT NOT NULL,
            PRIMARY KEY (batch_id, tray_id)
        )''')


def register_panel(db: sqlite3.Connection, batch_id: str, markers, unit: str,
                   tray_id: str, members) -> tuple[str, str]:
    batch = make_batch(batch_id, markers, unit)
    roster = build_roster(batch, tray_id, members)
    with write_transaction(db):
        definition = db.execute(
            'SELECT unit, first_marker, second_marker FROM panel_batches WHERE batch_id = ?',
            (batch_id,),
        ).fetchone()
        if definition is None:
            db.execute(
                'INSERT INTO panel_batches VALUES (?, ?, ?, ?)',
                (batch_id, batch.unit, *batch.markers.as_tuple()),
            )
        else:
            registered_unit, first, second = definition
            registered = make_batch(batch_id, (first, second), registered_unit)
            registered.require_matching_definition(batch)

        saved = db.execute(
            'SELECT members FROM panel_trays WHERE batch_id = ? AND tray_id = ?',
            (batch_id, tray_id),
        ).fetchone()
        if saved is None:
            db.execute(
                'INSERT INTO panel_trays VALUES (?, ?, ?)',
                (batch_id, tray_id, json.dumps(roster.members)),
            )
        elif tuple(json.loads(saved[0])) != roster.members:
            raise ValueError('conflicting registration for the same tray')
    return batch_id, tray_id


def read_roster(db: sqlite3.Connection, batch_id: str, tray_id: str) -> TrayRoster:
    try:
        validate_identifier(batch_id)
        validate_identifier(tray_id)
    except ValueError as exc:
        raise KeyError((batch_id, tray_id)) from exc
    row = db.execute('''SELECT batches.unit, batches.first_marker, batches.second_marker,
                              trays.members
                       FROM panel_trays AS trays
                       JOIN panel_batches AS batches USING (batch_id)
                       WHERE trays.batch_id = ? AND trays.tray_id = ?''',
                     (batch_id, tray_id)).fetchone()
    if row is None:
        raise KeyError((batch_id, tray_id))
    unit, first, second, members = row
    batch = make_batch(batch_id, (first, second), unit)
    return build_roster(batch, tray_id, json.loads(members))
