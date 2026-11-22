import json
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis.rank_review import issue_proof, issue_v1
from bench.revision_store import initialize_revisions
from bench.revisions import record_revision
from evidence.codec import encode_v1
from evidence.intake import accept_proof, accept_v1, initialize_intake
from evidence.issued_store import initialize_issued_pieces, read_issued_v1
from evidence.seal import seal_proof, seal_v1
from panel.registry import initialize_panel, register_panel
from reports.history import read_proof, read_v1
from reports.issue import initialize_reports
from samples.proof_cases import record_cases


def main():
    fixtures = [json.loads(Path(__file__).with_name(name).read_text(encoding='utf-8'))
                for name in ('chain.json', 'free.json')]
    with TemporaryDirectory(prefix='material-qc-') as folder:
        result = _v1_handoff(folder, fixtures)
        result.update(_proof_handoff(folder))
        print(json.dumps(result, ensure_ascii=False, indent=2))


def _v1_handoff(folder, fixtures):
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
    return {'v1': output}


def _proof_handoff(folder):
    source_path = Path(folder) / 'proof-source.sqlite3'
    center_path = Path(folder) / 'proof-center.sqlite3'
    with closing(sqlite3.connect(source_path)) as source:
        source.execute('PRAGMA foreign_keys = ON')
        initialize_panel(source)
        initialize_revisions(source)
        initialize_issued_pieces(source)
        revisions = record_cases(source)
        sealed = {label: seal_proof(source, revision_id)
                  for label, revision_id in revisions.items()}

    # The source database is now closed: only the V2 text and the centre
    # acceptance numbers cross the bench.  The source-side pair mapping never
    # does, so any request must be answerable from the accepted payload alone.
    issued = []
    with closing(sqlite3.connect(center_path)) as center:
        center.execute('PRAGMA foreign_keys = ON')
        initialize_intake(center)
        initialize_reports(center)
        accepted = {label: accept_proof(center, text)
                    for label, (text, _local) in sealed.items()}
        for label in ('manual-chain', 'reading-chain', 'dual-source', 'alternative'):
            local = sealed[label][1]
            inverse = {edge: cid for cid, edge in local.items()}
            for marker, side, rank, allowed in _requests(label, local, inverse):
                report = issue_proof(center, accepted[label], marker, side, rank, allowed)
                issued.append((label, report))

    output = []
    with closing(sqlite3.connect(center_path)) as reopened:
        reopened.execute('PRAGMA foreign_keys = ON')
        for label, report in issued:
            saved = read_proof(reopened, report['report_id'])
            if saved != report:
                raise AssertionError(f'reopened V2 report differs for {label}')
            output.append({
                'proof_case': label,
                'marker': saved['marker'],
                'side': saved['side'],
                'rank': saved['rank'],
                'status': saved['status'],
                'certificates': saved['certificates'],
                'report_id': saved['report_id'],
                'receipt_id': saved['receipt']['receipt_id'],
            })
    return _proof_correction(folder, output)


def _requests(label, local, inverse):
    requests = [('B', 'at_least', 3, list(local))]
    if label == 'alternative':
        requests.append(('B', 'at_least', 3, [inverse[('local-x', 'B')]]))
        requests.append(('B', 'at_least', 5, list(local)))
    return requests


def _proof_correction(folder, output):
    """Append a correction and confirm the earlier report still reads its own values."""
    source_path = Path(folder) / 'proof-source.sqlite3'
    center_path = Path(folder) / 'proof-center.sqlite3'
    with closing(sqlite3.connect(source_path)) as source:
        source.execute('PRAGMA foreign_keys = ON')
        initialize_panel(source)
        initialize_revisions(source)
        initialize_issued_pieces(source)
        # A legal correction: overlapping readings plus the same customer chain,
        # so it is a fresh revision that must still certify both links.
        correction = record_revision(
            source, 'proof-demo', 'chain',
            tuple((member, 0, 2) for member in ('A', 'B', 'local-x', 'local-y')),
            (('A', 'local-x'), ('local-x', 'B')))
        corrected_text, corrected_local = seal_proof(source, correction.revision_id)
    with closing(sqlite3.connect(center_path)) as center:
        center.execute('PRAGMA foreign_keys = ON')
        initialize_intake(center)
        initialize_reports(center)
        acceptance = accept_proof(center, corrected_text)
        report = issue_proof(center, acceptance, 'B', 'at_least', 3, list(corrected_local))
        issued = report
    with closing(sqlite3.connect(center_path)) as reopened:
        reopened.execute('PRAGMA foreign_keys = ON')
        saved = read_proof(reopened, issued['report_id'])
        previous = read_proof(reopened, output[0]['report_id'])
    if saved != issued or saved['receipt'] != issued['receipt']:
        raise AssertionError('corrected report changed after reopen')
    if previous['origin']['revision_id'] == saved['origin']['revision_id']:
        raise AssertionError('correction reissued under the original revision pin')
    output.append({
        'proof_case': 'manual-chain (corrected revision)',
        'marker': saved['marker'],
        'side': saved['side'],
        'rank': saved['rank'],
        'status': saved['status'],
        'certificates': saved['certificates'],
        'report_id': saved['report_id'],
        'receipt_id': saved['receipt']['receipt_id'],
        'prior_report_still_pinned_at': previous['origin']['revision_id'],
    })
    return {'proof': output}


if __name__ == '__main__':
    main()
