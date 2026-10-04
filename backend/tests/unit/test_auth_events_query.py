"""Admin login audit: query parsing, SQL shape and the public row format."""

from datetime import datetime, timezone

import pytest

from services.auth_events_query import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    build_auth_events_sql,
    parse_auth_events_query,
    parse_ip,
    public_auth_event,
    public_details,
)
from services.request_validation import RequestValidationError


def test_defaults_without_filters():
    q = parse_auth_events_query({})
    assert q == {'where': [], 'params': [], 'limit': DEFAULT_LIMIT, 'offset': 0}
    sql, params = build_auth_events_sql(q)
    assert 'WHERE' not in sql
    assert sql.endswith('ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s')
    assert params == [DEFAULT_LIMIT + 1, 0]


def test_all_filters_become_placeholders():
    q = parse_auth_events_query({
        'user_id': ' 7 ', 'username': ' Alice ', 'event': 'login_failed', 'ip': '10.0.0.5',
        'limit': '25', 'offset': '50',
    })
    sql, params = build_auth_events_sql(q)
    assert 'WHERE user_id = %s AND LOWER(username) = LOWER(%s) AND event = %s AND ip = %s ' in sql
    assert params == [7, 'Alice', 'login_failed', '10.0.0.5', 26, 50]
    # No value is ever pasted into the SQL text.
    for value in ('Alice', 'login_failed', '10.0.0.5'):
        assert value not in sql


def test_limit_and_offset_are_clamped():
    assert parse_auth_events_query({'limit': '0'})['limit'] == 1
    assert parse_auth_events_query({'limit': '100000'})['limit'] == MAX_LIMIT
    assert parse_auth_events_query({'offset': '-5'})['offset'] == 0
    assert parse_auth_events_query({'limit': ''})['limit'] == DEFAULT_LIMIT


@pytest.mark.parametrize('args, message', [
    ({'user_id': 'x'}, 'user_id must be an integer'),
    ({'limit': 'ten'}, 'limit must be an integer'),
    ({'offset': '1.5'}, 'offset must be an integer'),
    ({'ip': '*'}, 'ip must be an IPv4 or IPv6 address'),
])
def test_bad_values_raise_a_public_message(args, message):
    with pytest.raises(RequestValidationError) as exc:
        parse_auth_events_query(args)
    assert exc.value.public_message == message


def test_parse_ip_accepts_one_address_only():
    assert parse_ip(' 192.168.1.20 ') == '192.168.1.20'
    assert parse_ip('2001:DB8::1') == '2001:db8::1'
    assert parse_ip('') == ''
    assert parse_ip(None) == ''
    for bad in ('10.0.0.*', '10.0.0.0/24', '10.0.0.1|x', 'localhost', '[::1]'):
        with pytest.raises(RequestValidationError):
            parse_ip(bad)


def test_public_details_keeps_only_whitelisted_fields():
    assert public_details('{"known_user": true, "fam": "abc123"}') == {'known_user': True}
    assert public_details({'code_prefix': 'SR-ABCD', 'role': 'player'}) == {'role': 'player'}
    assert public_details('{"fam": "x"}') is None
    assert public_details('not json') is None
    assert public_details('[1, 2]') is None
    assert public_details(None) is None


def test_public_auth_event_marks_naive_timestamps_as_utc():
    row = {
        'id': 3, 'created_at': datetime(2026, 10, 4, 6, 30, 0), 'event': 'lockout', 'user_id': None,
        'username': 'bob', 'ip': '1.2.3.4', 'user_agent': 'curl/8', 'details': '{"seconds": 900}',
        'extra_column': 'never sent',
    }
    out = public_auth_event(row)
    assert out == {
        'id': 3, 'created_at': '2026-10-04T06:30:00Z', 'event': 'lockout', 'user_id': None,
        'username': 'bob', 'ip': '1.2.3.4', 'user_agent': 'curl/8', 'details': {'seconds': 900},
    }
    aware = public_auth_event({'created_at': datetime(2026, 1, 1, tzinfo=timezone.utc)})
    assert aware['created_at'] == '2026-01-01T00:00:00+00:00'
