"""Bounded description queries; metadata is data, never host instructions."""
import base64
from copy import deepcopy
import json
import re

from ocp_candidate.contract import parse_json
from ocp_candidate.fingerprint import fingerprint
from ocp_candidate.knowledge import project, VERSION
from ocp_candidate.native import NativeError

TEXTS = {
    'routing.basic': (
        ('Route planning from a distance matrix', 'Assign all visits to vehicles within weight capacity, using your integer meter distance matrix.', ['routing', 'vehicle assignment']),
        ('거리 행렬 기반 경로 계획', '직접 제공한 정수 미터 거리 행렬로 차량 용량을 지키면서 모든 방문지를 배정합니다.', ['경로 계획', '차량 배정'])),
    'routing.coordinates': (
        ('Route planning from coordinates', 'Use latitude, longitude and kg demand to plan routes with spherical distances. This does not calculate road travel times.', ['coordinates', 'route planning']),
        ('좌표 기반 경로 계획', '위도·경도와 kg 수요로 구면 거리 기준 경로를 구합니다. 실제 도로 이동시간은 계산하지 않습니다.', ['좌표', '배송 경로'])),
    'worker.scheduling': (
        ('Fixed-time worker assignment', 'Assign fixed-time tasks to available workers using the declared eligibility and cost inputs.', ['worker assignment', 'task allocation']),
        ('고정 시간 작업 배정', '고정 시간 작업을 가능 인력에게 배정합니다. 자격과 비용은 입력에서 명시합니다.', ['작업 배정', '인력 배정'])),
    'inventory.replenishment': (
        ('Inventory replenishment', 'Plan replenishment for declared periods using stock, demand and cost data.', ['inventory', 'replenishment']),
        ('재고 보충 계획', '재고·수요·비용 자료를 사용하여 명시된 기간의 보충 계획을 구합니다.', ['재고', '보충 계획']))}


def fail(code, path='', message=None):
    raise NativeError(code, body={'code': code, 'message': message or code,
        'requestId': 'knowledge', 'retryable': False,
        'issues': [{'code': code, 'fieldPath': path, 'message': message or code}]})


class KnowledgeService:
    def __init__(self, clients, *, localizations=None):
        self.clients = dict(clients)
        self.localizations = deepcopy(localizations or {})

    def bundle(self, domain):
        if domain not in self.clients:
            fail('UNSUPPORTED_DOMAIN', '/domain')
        catalog = deepcopy(self.clients[domain].capabilities())
        texts = self.localizations.get(domain)
        if texts is None and catalog['domainProfile']['id'] in TEXTS:
            texts = {locale: dict(zip(('title', 'summary', 'aliases'), values))
                     for locale, values in zip(('en', 'ko'), TEXTS[catalog['domainProfile']['id']])}
        return project(domain, catalog, texts)

    def descriptor(self):
        return {'version': VERSION, 'tool': 'ocp_native_describe', 'default_locale': 'en',
            'configured_domains': list(self.clients), 'max_page_size': 20,
            'scope': 'Read-only descriptions projected from current execution catalogs. No solve or model calls.'}

    def describe(self, domain, *, section=None, item_id=None, locale='en',
                 cursor=None, limit=20, expected_digest=None):
        if (not isinstance(locale, str) or not re.fullmatch(r'[a-z]{2}(?:-[A-Za-z0-9]{2,8})*', locale)
                or type(limit) is not int or not 1 <= limit <= 20):
            fail('INVALID_DESCRIPTION_QUERY')
        bundle = self.bundle(domain)
        digest = fingerprint(bundle)
        actual_locale = locale if locale in bundle['localizations'] else bundle['default_locale']
        if expected_digest is not None and expected_digest != digest:
            fail('STALE_KNOWLEDGE', '/expected_digest', 'Read the current summary and review the changed catalog before continuing.')
        response = {'version': VERSION, 'domain': domain, 'profile': bundle['profile'], 'digest': digest,
            'requested_locale': locale, 'locale': actual_locale, 'fallback': actual_locale != locale,
            'catalog_fingerprint': bundle['catalog_fingerprint'],
            'technical_content_locale': 'en', 'content_role': 'data'}
        if section is None:
            if cursor is not None or item_id is not None:
                fail('SECTION_REQUIRED', '/section')
            response.update(bundle['localizations'][actual_locale])
            response['sections'] = {name: len(items) for name, items in bundle['sections'].items()}
        else:
            if section not in bundle['sections']:
                fail('UNKNOWN_KNOWLEDGE_SECTION', '/section')
            items = bundle['sections'][section]
            offset = 0
            if cursor is not None:
                if item_id is not None or not isinstance(cursor, str) or len(cursor) > 1024:
                    fail('INVALID_CURSOR', '/cursor')
                try:
                    state = parse_json(base64.b64decode(cursor, altchars=b'-_', validate=True).decode('utf-8'))
                    if (not isinstance(state, dict) or set(state) != {'digest', 'domain', 'section', 'locale', 'offset'}
                            or type(state['offset']) is not int or not 0 < state['offset'] < len(items)):
                        raise ValueError()
                except (ValueError, UnicodeError):
                    fail('INVALID_CURSOR', '/cursor')
                if any(state[key] != value for key, value in (
                        ('digest', digest), ('domain', domain), ('section', section), ('locale', locale))):
                    fail('STALE_CURSOR', '/cursor')
                offset = state['offset']
            if item_id is not None:
                items = [item for item in items if item['id'] == item_id]
                if not items:
                    fail('UNKNOWN_KNOWLEDGE_ITEM', '/item_id')
            page = items[offset:offset + limit]
            response.update(section=section, items=page, next_cursor=None)
            if offset + len(page) < len(items):
                state = {'digest': digest, 'domain': domain, 'section': section, 'locale': locale,
                         'offset': offset + len(page)}
                response['next_cursor'] = base64.urlsafe_b64encode(json.dumps(state, separators=(',', ':')).encode()).decode()
        if len(json.dumps(response, ensure_ascii=False).encode()) > 32768:
            fail('DESCRIPTION_TOO_LARGE', '/limit', 'Request one item or a smaller page; no content was truncated.')
        return deepcopy(response)
