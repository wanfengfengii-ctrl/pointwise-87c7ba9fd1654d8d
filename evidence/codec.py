import json

from evidence.pieces import PieceOrigin, V1Piece, make_v1_piece


_V1_FIELDS = frozenset({
    'version', 'piece_id', 'batch_id', 'tray_id', 'revision_id',
    'markers', 'specimen_count', 'rank_bounds',
})


def encode_v1(piece: V1Piece) -> str:
    body = {
        'version': 1,
        'piece_id': piece.piece_id,
        'batch_id': piece.origin.batch_id,
        'tray_id': piece.origin.tray_id,
        'revision_id': piece.origin.revision_id,
        'markers': piece.markers.as_tuple(),
        'specimen_count': piece.specimen_count,
        'rank_bounds': piece.rank_bounds,
    }
    return json.dumps(body, sort_keys=True, separators=(',', ':'))


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON field {key!r}')
        result[key] = value
    return result


def decode_v1(text: str) -> V1Piece:
    if not isinstance(text, str):
        raise ValueError('a V1 piece must be JSON text')
    try:
        body = json.loads(text, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('invalid V1 JSON') from exc
    if not isinstance(body, dict) or set(body) != _V1_FIELDS:
        raise ValueError('unexpected V1 piece fields')
    version = body['version']
    if type(version) is not int or version != 1:
        raise ValueError('unsupported piece version')
    origin = PieceOrigin(body['batch_id'], body['tray_id'], body['revision_id'])
    return make_v1_piece(body['piece_id'], origin, body['markers'],
                         body['specimen_count'], body['rank_bounds'])
