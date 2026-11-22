import sqlite3

from analysis.requests import prepare_v1_request
from evidence.intake import read_accepted_v1
from reports.issue import publish_v1
from reports.records import V1Report


def issue_v1(db: sqlite3.Connection, acceptance_id: int, marker: str) -> V1Report:
    piece, receipt = read_accepted_v1(db, acceptance_id)
    request = prepare_v1_request(piece, receipt, marker)
    return publish_v1(db, request)
