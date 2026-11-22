import json
import sqlite3
from contextlib import closing

from analysis.rank_review import issue_v1
from bench.revision_store import initialize_revisions
from bench.revisions import record_revision
from evidence.codec import encode_v1
from evidence.intake import accept_v1, initialize_intake
from evidence.issued_store import initialize_issued_pieces
from evidence.seal import seal_v1
from panel.registry import initialize_panel, register_panel
from reports.issue import initialize_reports


CHAIN_READINGS = (("A", 0, 0), ("B", 2, 2), ("local-x", 1, 1), ("local-y", 0, 2))
CASES = {
    "manual-chain": (
        "chain",
        tuple((name, 0, 2) for name, _, _ in CHAIN_READINGS),
        (("A", "local-x"), ("local-x", "B")),
    ),
    "reading-chain": ("chain", CHAIN_READINGS, ()),
    "dual-source": ("chain", CHAIN_READINGS, (("local-x", "B"), ("local-x", "B"))),
    "alternative": (
        "fork",
        (("A", 0, 2), ("B", 0, 2), ("local-x", 0, 0), ("local-y", 0, 0),
         ("local-u", 1, 2)),
        (("local-u", "B"), ("local-x", "B"), ("local-y", "B")),
    ),
}
EXPECTED_V1_B = {
    "manual-chain": (3, 4),
    "reading-chain": (3, 4),
    "dual-source": (3, 4),
    "alternative": (4, 5),
}


def record_cases(db):
    """Seed an initialized source database using only the V1 recording API."""
    revisions = {}
    for label, (tray, readings, certificates) in CASES.items():
        register_panel(db, "proof-demo", ("A", "B"), "MPa", tray,
                       [name for name, _, _ in readings])
        snapshot = record_revision(db, "proof-demo", tray, readings, certificates)
        revisions[label] = snapshot.revision_id
    return revisions


def main():
    with closing(sqlite3.connect(":memory:")) as source:
        source.execute("PRAGMA foreign_keys = ON")
        initialize_panel(source)
        initialize_revisions(source)
        initialize_issued_pieces(source)
        revisions = record_cases(source)
        handoff = {label: encode_v1(seal_v1(source, revision_id))
                   for label, revision_id in revisions.items()}

    output = []
    with closing(sqlite3.connect(":memory:")) as center:
        center.execute("PRAGMA foreign_keys = ON")
        initialize_intake(center)
        initialize_reports(center)
        for label, text in handoff.items():
            accepted = accept_v1(center, text)
            report = issue_v1(center, accepted.acceptance_id, "B")
            if report.bounds != EXPECTED_V1_B[label]:
                raise AssertionError(f"unexpected V1 rank bounds for {label}: {report.bounds}")
            if report.origin.revision_id != revisions[label] or report.piece_id != accepted.piece_id:
                raise AssertionError(f"unexpected V1 provenance for {label}")
            output.append({"case": label, "revision_id": revisions[label], "B": report.bounds})
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
