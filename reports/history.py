import sqlite3

from reports.proof_records import load_report
from reports.records import V1Report, report_from_rows
from panel.markers import validate_identifier


def read_v1(db: sqlite3.Connection, report_id: int) -> V1Report:
    if type(report_id) is not int or not 1 <= report_id < 2**63:
        raise KeyError(report_id)
    row = db.execute('''SELECT body.report_id, body.acceptance_id, body.piece_id,
                              body.batch_id, body.tray_id, body.revision_id, body.marker,
                              body.lower_rank, body.upper_rank, receipt.report_id, receipt.receipt_id
                       FROM v1_reports AS body
                       JOIN report_receipts AS receipt ON body.report_id = receipt.report_id
                       WHERE body.report_id = ?''', (report_id,)).fetchone()
    if row is None:
        raise KeyError(report_id)
    return report_from_rows(row[:9], row[9:])


def read_proof(db: sqlite3.Connection, report_id: str) -> dict:
    validate_identifier(report_id)
    return load_report(db, report_id)
