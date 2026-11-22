import json
import sqlite3
from itertools import permutations

from analysis.rank_review import issue_proof
from bench.revision_store import get_revision
from bench.revisions import record_revision
from evidence.codec import encode_v1
from evidence.intake import accept_proof, accept_v1, initialize_intake, read_accepted_proof
from evidence.issued_store import initialize_issued_pieces, read_issued_v2, read_local_certificates
from evidence.proof_codec import decode_v2
from evidence.seal import seal_proof, seal_v1
from panel.registry import initialize_panel
from reports.history import read_proof
from reports.issue import initialize_reports
from samples.proof_cases import record_cases
from tests.support import LabTestCase


class ProofTestCase(LabTestCase):
    def setUp(self):
        super().setUp()
        self.revisions = record_cases(self.source)

    def seal_case(self, label):
        text, local = seal_proof(self.source, self.revisions[label])
        inverse = {edge: cid for cid, edge in local.items()}
        return text, local, inverse

    def accept(self, text):
        self.source.close()
        return accept_proof(self.center, text)


class TestProofCases(ProofTestCase):
    def test_manual_chain(self):
        text, local, inverse = self.seal_case('manual-chain')
        acceptance = self.accept(text)
        every = list(local)
        report = issue_proof(self.center, acceptance, 'B', 'at_least', 3, every)
        self.assertEqual(report['status'], 'proved')
        self.assertEqual(report['certificates'], [inverse[('A', 'local-x')], inverse[('local-x', 'B')]])
        partial = issue_proof(self.center, acceptance, 'B', 'at_least', 3,
                              [inverse[('A', 'local-x')]])
        self.assertEqual((partial['status'], partial['certificates']), ('impossible', None))
        top = issue_proof(self.center, acceptance, 'A', 'at_most', 2, every)
        self.assertEqual(top['status'], 'proved')
        self.assertEqual(set(top['certificates']),
                         {inverse[('A', 'local-x')], inverse[('local-x', 'B')]})

    def test_reading_chain(self):
        text, local, _ = self.seal_case('reading-chain')
        self.assertEqual(local, {})
        acceptance = self.accept(text)
        report = issue_proof(self.center, acceptance, 'B', 'at_least', 3, None)
        self.assertEqual((report['status'], report['certificates']), ('proved', []))

    def test_dual_source(self):
        text, local, inverse = self.seal_case('dual-source')
        self.assertEqual(len(local), 1)
        acceptance = self.accept(text)
        report = issue_proof(self.center, acceptance, 'B', 'at_least', 3, [])
        self.assertEqual((report['status'], report['certificates']), ('proved', []))

    def test_alternative(self):
        text, local, inverse = self.seal_case('alternative')
        acceptance = self.accept(text)
        every = list(local)
        least = issue_proof(self.center, acceptance, 'B', 'at_least', 3, every)
        self.assertEqual(least['status'], 'proved')
        self.assertEqual(least['certificates'], [inverse[('local-u', 'B')]])
        paired = issue_proof(self.center, acceptance, 'B', 'at_least', 3,
                             [inverse[('local-x', 'B')], inverse[('local-y', 'B')]])
        self.assertEqual(paired['status'], 'proved')
        self.assertEqual(paired['certificates'],
                         [inverse[('local-x', 'B')], inverse[('local-y', 'B')]])
        single = issue_proof(self.center, acceptance, 'B', 'at_least', 3,
                             [inverse[('local-x', 'B')]])
        self.assertEqual((single['status'], single['certificates']), ('impossible', None))
        beyond = issue_proof(self.center, acceptance, 'B', 'at_least', 5, every)
        self.assertEqual((beyond['status'], beyond['certificates']), ('impossible', None))

    def test_matches_brute_force(self):
        # Every accepted V2 piece must agree with an explicit linear-extension
        # enumeration, and any proved selection must be minimum-size.
        for label in ('manual-chain', 'reading-chain', 'dual-source', 'alternative'):
            with self.subTest(case=label):
                text, local, _ = self.seal_case(label)
                piece = decode_v2(text)
                acceptance = accept_proof(self.center, text)
                every = list(local)
                for marker in piece.marker_choices:
                    for side in ('at_least', 'at_most'):
                        for rank in range(1, piece.specimen_count + 1):
                            report = issue_proof(self.center, acceptance, marker, side, rank, every)
                            self.assertEqual(report['status'],
                                             self._expect_status(piece, marker, side, rank))
                            if report['status'] == 'proved':
                                chosen = set(report['certificates'])
                                self.assertTrue(self._guarantees(piece, chosen, marker, side, rank))
                                for size in range(len(chosen)):
                                    for smaller in self._subsets(every, size):
                                        self.assertFalse(self._guarantees(piece, set(smaller), marker, side, rank))

    @staticmethod
    def _orders(piece, chosen_ids):
        edges = set(piece.inferred_edges)
        certificates = piece.certificate_map()
        for cid in chosen_ids:
            edges.add(certificates[cid])
        nodes = piece.specimens
        orders = []
        for order in permutations(nodes):
            position = {node: index for index, node in enumerate(order)}
            if all(position[earlier] < position[later] for earlier, later in edges):
                orders.append(order)
        return orders

    def _guarantees(self, piece, chosen_ids, marker, side, rank):
        target = piece.node_for(marker)
        orders = self._orders(piece, chosen_ids)
        positions = [order.index(target) + 1 for order in orders]
        if side == 'at_least':
            return min(positions) >= rank
        return max(positions) <= rank

    def _expect_status(self, piece, marker, side, rank):
        return 'proved' if self._guarantees(piece, set(piece.certificate_ids), marker, side, rank) else 'impossible'

    @staticmethod
    def _subsets(mapping, size):
        from itertools import combinations
        keys = list(mapping)
        return [list(combo) for combo in combinations(keys, size)]


class TestProofReport(ProofTestCase):
    def test_report_shape_and_persistence(self):
        text, local, inverse = self.seal_case('manual-chain')
        acceptance = self.accept(text)
        report = issue_proof(self.center, acceptance, 'B', 'at_least', 3, list(local))
        piece = read_accepted_proof(self.center, acceptance)
        self.assertEqual(report['acceptance_id'], acceptance)
        self.assertEqual(report['piece_id'], piece.piece_id)
        self.assertEqual(report['origin'], {'batch_id': 'proof-demo', 'tray_id': 'chain',
                                            'revision_id': self.revisions['manual-chain']})
        self.assertEqual(report['marker'], 'B')
        self.assertEqual(report['side'], 'at_least')
        self.assertEqual(report['rank'], 3)
        self.assertEqual(report['allowed'], list(local))
        self.assertEqual(report['receipt']['report_id'], report['report_id'])
        self.assertTrue(report['receipt']['receipt_id'].strip())

        report['allowed'].append('tampered')
        report['origin']['batch_id'] = 'other'
        report['receipt']['receipt_id'] = 'tampered'
        self.center.close()
        reopened = self.open_db(self.center_path)
        saved = read_proof(reopened, report['report_id'])
        self.assertEqual(saved['allowed'], list(local))
        self.assertEqual(saved['origin']['batch_id'], 'proof-demo')
        self.assertNotEqual(saved['receipt']['receipt_id'], 'tampered')

    def test_unknown_and_invalid(self):
        text, local, _ = self.seal_case('manual-chain')
        acceptance = self.accept(text)
        report = issue_proof(self.center, acceptance, 'B', 'at_least', 3, None)
        with self.assertRaises(KeyError):
            read_proof(self.center, 'no-such-report')
        with self.assertRaises(ValueError):
            read_proof(self.center, 17)
        with self.assertRaises(KeyError):
            issue_proof(self.center, 'no-such-acceptance', 'B', 'at_least', 3, None)
        for args in [('x', 'at_least', 3, None), ('B', 'wrong', 3, None),
                     ('B', 'at_least', 0, None), ('B', 'at_least', 99, None),
                     ('B', 'at_least', True, None), ('B', 'at_least', 3, 'nope'),
                     ('B', 'at_least', 3, ['missing']),
                     ('B', 'at_least', 3, [local[list(local)[0]]] * 2)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                issue_proof(self.center, acceptance, *args)
        self.assertEqual(read_proof(self.center, report['report_id']), report)

    def test_v1_acceptance_rejected(self):
        piece = seal_v1(self.source, self.revisions['manual-chain'])
        self.source.close()
        acceptance = accept_v1(self.center, encode_v1(piece))
        with self.assertRaises(ValueError):
            issue_proof(self.center, acceptance.acceptance_id, 'B', 'at_least', 3, None)
        # V2 text is still rejected by the V1 intake, keeping the two streams apart.
        with self.assertRaises(ValueError):
            accept_proof(self.center, encode_v1(piece))

    def test_cross_piece_certificates_differ(self):
        first_text, first_local, _ = self.seal_case('manual-chain')
        first = self.accept(first_text)
        self.source = self.open_db(self.source_path)
        second_text, second_local, _ = self.seal_case('manual-chain')
        second = accept_proof(self.center, second_text)
        self.assertTrue(set(first_local).isdisjoint(second_local))
        self.assertNotEqual(first, second)
        with self.assertRaises(ValueError):
            issue_proof(self.center, second, 'B', 'at_least', 3, list(first_local))
        report = issue_proof(self.center, second, 'B', 'at_least', 3, list(second_local))
        self.assertEqual(report['status'], 'proved')


class TestProofIntake(ProofTestCase):
    def test_equivalent_and_conflicting_repeats(self):
        text, local, _ = self.seal_case('manual-chain')
        first = accept_proof(self.center, text)
        parsed = json.loads(text)
        alternate = json.dumps(dict(reversed(list(parsed.items()))), indent=2)
        self.assertNotEqual(alternate, text)
        self.assertEqual(accept_proof(self.center, alternate), first)
        self.assertEqual(self.count(self.center, 'accepted_v2'), 1)

        conflict = json.loads(text)
        conflict['specimen_count'] = conflict['specimen_count'] + 1
        with self.assertRaises(ValueError):
            accept_proof(self.center, json.dumps(conflict))

    def test_invalid_pieces(self):
        text, local, _ = self.seal_case('manual-chain')
        accept_proof(self.center, text)
        body = json.loads(text)
        for patch in [dict(version=1), dict(version=True), dict(extra=[]),
                      dict(specimen_count='4'), dict(markers=['A', 'A']),
                      dict(revision_id=False), dict(certificate_ids='x')]:
            invalid = {**body, **patch}
            invalid['piece_id'] = 'unseen-' + str(hash(json.dumps(patch, sort_keys=True)))
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                accept_proof(self.center, json.dumps(invalid))
        with self.assertRaises(ValueError):
            accept_proof(self.center, text.replace('"A"', '"A","A"', 1))
        with self.assertRaises(ValueError):
            accept_proof(self.center, text[:-1])
        self.assertEqual(self.count(self.center, 'accepted_v2'), 1)

    def test_source_data_stays_local(self):
        text, local, _ = self.seal_case('manual-chain')
        piece = decode_v2(text)
        # Original ordinary specimen numbers never travel; readers stay named.
        self.assertNotIn('local-x', text)
        self.assertNotIn('local-y', text)
        self.assertEqual(set(piece.specimens), {'A', 'B', 's1', 's2'})
        self.assertEqual(piece.marker_nodes, (('A', 'A'), ('B', 'B')))
        # The original pair mapping and original readings remain only in the source.
        self.assertEqual(read_local_certificates(self.source, piece.piece_id), local)
        self.assertEqual(set(local.values()),
                         {('A', 'local-x'), ('local-x', 'B')})
        self.assertEqual(read_issued_v2(self.source, piece.piece_id), piece)
        for edge in piece.inferred_edges:
            self.assertTrue(all(node in piece.specimens for node in edge))


class TestProofDurability(ProofTestCase):
    def test_seal_rollback_and_retry(self):
        revision = get_revision(self.source, self.revisions['manual-chain'])
        self.source.executescript('''
            CREATE TABLE proof_gate_parent (id INTEGER PRIMARY KEY);
            CREATE TABLE proof_gate (
                parent_id INTEGER REFERENCES proof_gate_parent(id) DEFERRABLE INITIALLY DEFERRED
            );
            CREATE TRIGGER proof_fail_seal AFTER INSERT ON issued_v2
            BEGIN INSERT INTO proof_gate (parent_id) VALUES (1); END;
        ''')
        with self.assertRaises(sqlite3.IntegrityError):
            seal_proof(self.source, revision.revision_id)
        self.assertFalse(self.source.in_transaction)
        observer = self.open_db(self.source_path)
        self.assertEqual(observer.execute('SELECT count(*) FROM issued_v2').fetchone()[0], 0)
        self.assertEqual(observer.execute('SELECT count(*) FROM proof_gate').fetchone()[0], 0)
        observer.close()
        self.source.execute('DROP TRIGGER proof_fail_seal')
        text, local = seal_proof(self.source, revision.revision_id)
        self.assertEqual(read_issued_v2(self.source, decode_v2(text).piece_id), decode_v2(text))

    def test_issue_rollback_and_retry(self):
        text, local, _ = self.seal_case('manual-chain')
        acceptance = self.accept(text)
        self.center.executescript('''
            CREATE TABLE report_gate_parent (id INTEGER PRIMARY KEY);
            CREATE TABLE report_gate (
                parent_id INTEGER REFERENCES report_gate_parent(id) DEFERRABLE INITIALLY DEFERRED
            );
            CREATE TRIGGER proof_fail_report AFTER INSERT ON proof_receipts
            BEGIN INSERT INTO report_gate (parent_id) VALUES (1); END;
        ''')
        with self.assertRaises(sqlite3.IntegrityError):
            issue_proof(self.center, acceptance, 'B', 'at_least', 3, list(local))
        self.assertFalse(self.center.in_transaction)
        observer = self.open_db(self.center_path)
        self.assertEqual(observer.execute('SELECT count(*) FROM proof_reports').fetchone()[0], 0)
        self.assertEqual(observer.execute('SELECT count(*) FROM proof_receipts').fetchone()[0], 0)
        observer.close()
        self.center.execute('DROP TRIGGER proof_fail_report')
        report = issue_proof(self.center, acceptance, 'B', 'at_least', 3, list(local))
        self.assertEqual(report['status'], 'proved')
        self.assertEqual(self.count(self.center, 'proof_reports'), 1)

    def test_accept_rollback_and_retry(self):
        text, local, _ = self.seal_case('manual-chain')
        self.center.executescript('''
            CREATE TABLE accept_gate_parent (id INTEGER PRIMARY KEY);
            CREATE TABLE accept_gate (
                parent_id INTEGER REFERENCES accept_gate_parent(id) DEFERRABLE INITIALLY DEFERRED
            );
            CREATE TRIGGER proof_fail_accept AFTER INSERT ON accepted_v2
            BEGIN INSERT INTO accept_gate (parent_id) VALUES (1); END;
        ''')
        with self.assertRaises(sqlite3.IntegrityError):
            accept_proof(self.center, text)
        self.assertFalse(self.center.in_transaction)
        observer = self.open_db(self.center_path)
        self.assertEqual(observer.execute('SELECT count(*) FROM accepted_v2').fetchone()[0], 0)
        observer.close()
        self.center.execute('DROP TRIGGER proof_fail_accept')
        acceptance = accept_proof(self.center, text)
        self.assertEqual(self.count(self.center, 'accepted_v2'), 1)
        report = issue_proof(self.center, acceptance, 'B', 'at_least', 3, list(local))
        self.assertEqual(report['status'], 'proved')

    def test_correction_and_reopen(self):
        text, local, _ = self.seal_case('manual-chain')
        acceptance = accept_proof(self.center, text)
        old = issue_proof(self.center, acceptance, 'B', 'at_least', 3, list(local))
        # The source appends a corrected revision; the old report still pins its own.
        self.source = self.open_db(self.source_path)
        correction = record_revision(self.source, 'proof-demo', 'chain',
                                     tuple((member, 0, 2) for member in ('A', 'B', 'local-x', 'local-y')),
                                     (('A', 'local-x'), ('local-x', 'B')))
        new_text, new_local = seal_proof(self.source, correction.revision_id)
        new_acceptance = accept_proof(self.center, new_text)
        new = issue_proof(self.center, new_acceptance, 'B', 'at_least', 3, list(new_local))
        self.center.close()
        reopened = self.open_db(self.center_path)
        for report, revision_id in [(old, self.revisions['manual-chain']),
                                    (new, correction.revision_id)]:
            saved = read_proof(reopened, report['report_id'])
            self.assertEqual(saved, report)
            self.assertEqual(saved['origin']['revision_id'], revision_id)
            self.assertEqual(saved['receipt'], report['receipt'])

    def test_reinitialize_keeps_records(self):
        text, local, _ = self.seal_case('manual-chain')
        acceptance = self.accept(text)
        report = issue_proof(self.center, acceptance, 'B', 'at_least', 3, list(local))
        self.center.close()
        self.source = self.open_db(self.source_path)
        # initialize_issued_pieces and initialize_reports are idempotent.
        initialize_issued_pieces(self.source)
        initialize_panel(self.source)
        center = self.open_db(self.center_path)
        initialize_intake(center)
        initialize_reports(center)
        self.assertEqual(read_proof(center, report['report_id']), report)
        self.assertEqual(accept_proof(center, text), acceptance)
        self.assertEqual(self.count(center, 'proof_reports'), 1)
