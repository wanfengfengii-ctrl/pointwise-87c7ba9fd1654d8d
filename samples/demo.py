import json
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis.rank_review import issue_v1
from bench.revision_store import initialize_revisions
from bench.revisions import record_revision
from evidence.codec import encode_v1
from evidence.intake import accept_v1, initialize_intake
from evidence.issued_store import initialize_issued_pieces, read_issued_v1
from evidence.seal import seal_v1
from panel.registry import initialize_panel, register_panel
from reports.history import read_v1
from reports.issue import initialize_reports


def main():
    fixtures = [json.loads(Path(__file__).with_name(name).read_text(encoding='utf-8'))
                for name in ('chain.json', 'free.json')]
    with TemporaryDirectory(prefix='material-qc-') as folder:
        source_path = Path(folder) / 'source.sqlite3'
        center_path = Path(folder) / 'center.sqlite3'
        handoff = []
        with closing(sqlite3.connect(source_path)) as source:
            source.execute('PRAGMA foreign_keys = ON')
            initialize_panel(source)
            initialize_revisions(source)
            initialize_issued_pieces(source)
            for fixture in fixtures:
                batch, tray = register_panel(source, fixture['batch_id'], fixture['markers'],
                                             fixture['unit'], fixture['tray_id'], fixture['members'])
                revision = record_revision(source, batch, tray, fixture['observations'],
                                           fixture['certificates'])
                piece = seal_v1(source, revision.revision_id)
                stored = read_issued_v1(source, piece.piece_id)
                handoff.append((fixture, encode_v1(stored)))

        issued = []
        with closing(sqlite3.connect(center_path)) as center:
            center.execute('PRAGMA foreign_keys = ON')
            initialize_intake(center)
            initialize_reports(center)
            for fixture, text in handoff:
                receipt = accept_v1(center, text)
                for marker, expected in fixture['expected_bounds'].items():
                    report = issue_v1(center, receipt.acceptance_id, marker)
                    if list(report.bounds) != expected or report.origin.tray_id != fixture['tray_id']:
                        raise AssertionError(f'hand-calculated result differs for {fixture["tray_id"]} {marker}')
                    if (report.piece_id, report.origin) != (receipt.piece_id, receipt.origin):
                        raise AssertionError('report provenance differs from acceptance')
                    issued.append(report)

        output = []
        with closing(sqlite3.connect(center_path)) as reopened:
            reopened.execute('PRAGMA foreign_keys = ON')
            for report in issued:
                retrieved = read_v1(reopened, report.report_id)
                if retrieved != report:
                    raise AssertionError('reopened history differs from the issued report')
                output.append({
                    'tray': retrieved.origin.tray_id,
                    'revision_id': retrieved.origin.revision_id,
                    'piece_id': retrieved.piece_id,
                    'marker': retrieved.marker,
                    'bounds': retrieved.bounds,
                    'report_id': retrieved.report_id,
                    'receipt_id': retrieved.receipt.receipt_id,
                })
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
