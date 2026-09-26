"""Record server-observed paid responses without storing payment signatures."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid

from prime_agent import NETWORK

TX = re.compile(r'^0x[0-9a-fA-F]{64}$')
_write_lock = threading.Lock()
_logger = logging.getLogger(__name__)


def append_record(path: str, record: dict) -> None:
    """Append a single bounded JSON line; never include the payment signature."""
    data = (json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n').encode()
    if len(data) > 4096:
        raise ValueError('delivery record too large')
    with _write_lock:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            if os.write(fd, data) != len(data):
                raise OSError('incomplete journal write')
            os.fsync(fd)
        finally:
            os.close(fd)


class DeliveryJournalASGI:
    def __init__(self, app, *, path: str, pay_to: str, prices: dict[str, str]):
        self.app, self.path, self.pay_to, self.prices = app, path, pay_to, prices

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        response_status = None
        settlement = None
        digest = hashlib.sha256()
        request_id = uuid.uuid4().hex
        route = _route(scope.get('method', ''), scope.get('path', ''))

        async def observed_send(message):
            nonlocal response_status, settlement
            if message['type'] == 'http.response.start':
                response_status = message['status']
                headers = {key.lower(): value for key, value in message.get('headers', [])}
                settlement = headers.get(b'payment-response')
            if message['type'] == 'http.response.body':
                digest.update(message.get('body', b''))
            await send(message)
            if (message['type'] == 'http.response.body' and not message.get('more_body', False)
                    and response_status == 200 and settlement and route in self.prices):
                try:
                    receipt = json.loads(base64.b64decode(settlement, validate=True))
                    transaction = receipt['transaction']
                    if (receipt.get('success') is not True or receipt.get('network') != NETWORK
                            or not isinstance(transaction, str) or not TX.fullmatch(transaction)):
                        raise ValueError('invalid settlement response')
                    record = {
                        'event': 'asgi_response_sent', 'request_id': request_id,
                        'timestamp': int(time.time()), 'route': route, 'price': self.prices[route],
                        'status': response_status, 'network': NETWORK, 'pay_to': self.pay_to,
                        'transaction': transaction.lower(),
                        'payer_reported_by_facilitator': receipt.get('payer'),
                        'body_sha256': digest.hexdigest(),
                        'basis': 'seller observed settlement header and ASGI send completion',
                    }
                    append_record(self.path, record)
                    _logger.info(
                        'x402 settlement_delivered route=%s transaction=%s payer=%s body_sha256=%s',
                        route,
                        record['transaction'],
                        record['payer_reported_by_facilitator'],
                        record['body_sha256'],
                    )
                except (KeyError, TypeError, ValueError, OSError):
                    _logger.exception('Unable to journal a paid response; settlement requires separate reconciliation')

        await self.app(scope, receive, observed_send)


def _route(method: str, path: str) -> str:
    if method != 'GET':
        return ''
    if path == '/chain/status':
        return 'GET /chain/status'
    if re.fullmatch(r'/token/(metadata|context)/0x[0-9a-fA-F]{40}', path):
        return 'GET /token/' + path.split('/')[2] + '/:address'
    return ''
