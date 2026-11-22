"""Canonical JSON encoding for V2 proof pieces.

The outer object is fixed and small; the ``evidence`` member is an
implementation-defined object that carries everything the offline reviewer
needs: the specimen labels, the marker-to-specimen map, the reading-derived
strict precedence, and the manual certificate edges keyed by their piece-local
identifiers.
"""
import json

from evidence.pieces import PieceOrigin
from evidence.proof_models import ProofPiece, make_proof_piece


_V2_FIELDS = frozenset({
    'version', 'piece_id', 'batch_id', 'tray_id', 'revision_id',
    'markers', 'specimen_count', 'certificate_ids', 'evidence',
})
_EVIDENCE_FIELDS = frozenset({'specimens', 'markers', 'inferred', 'certificates'})


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON field {key!r}')
        result[key] = value
    return result


def encode_v2(piece: ProofPiece) -> str:
    body = {
        'version': 2,
        'piece_id': piece.piece_id,
        'batch_id': piece.origin.batch_id,
        'tray_id': piece.origin.tray_id,
        'revision_id': piece.origin.revision_id,
        'markers': list(piece.markers.as_tuple()),
        'specimen_count': piece.specimen_count,
        'certificate_ids': list(piece.certificate_ids),
        'evidence': {
            'specimens': list(piece.specimens),
            'markers': {name: label for name, label in piece.marker_nodes},
            'inferred': [list(edge) for edge in piece.inferred_edges],
            'certificates': {cid: [earlier, later]
                             for cid, earlier, later in piece.certificate_edges},
        },
    }
    return json.dumps(body, sort_keys=True, separators=(',', ':'))


def decode_v2(text: str) -> ProofPiece:
    if not isinstance(text, str):
        raise ValueError('a V2 piece must be JSON text')
    try:
        body = json.loads(text, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('invalid V2 JSON') from exc
    if not isinstance(body, dict) or set(body) != _V2_FIELDS:
        raise ValueError('unexpected V2 piece fields')
    version = body['version']
    if type(version) is not int or version != 2:
        raise ValueError('unsupported piece version')
    evidence = body['evidence']
    if not isinstance(evidence, dict) or set(evidence) != _EVIDENCE_FIELDS:
        raise ValueError('unexpected V2 evidence fields')
    if not isinstance(evidence['specimens'], list):
        raise ValueError('specimens must be a JSON array')
    if not isinstance(evidence['markers'], dict):
        raise ValueError('marker nodes must be a JSON object')
    if not isinstance(evidence['inferred'], list):
        raise ValueError('inferred precedence must be a JSON array')
    if not isinstance(evidence['certificates'], dict):
        raise ValueError('certificate edges must be a JSON object')
    origin = PieceOrigin(body['batch_id'], body['tray_id'], body['revision_id'])
    return make_proof_piece(
        body['piece_id'], origin, body['markers'], body['specimen_count'],
        body['certificate_ids'], evidence['specimens'], evidence['markers'],
        evidence['inferred'], evidence['certificates'],
    )
