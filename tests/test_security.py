import socket
import pytest
from security.main import parse_nmap, scan, validate_target, fetch_json, parse_web_metadata


def test_nmap_service_parse():
    xml = '<nmaprun><host><status state="up"/><ports><port protocol="tcp" portid="443"><state state="open"/><service name="https" product="nginx" version="1.2"/></port></ports></host></nmaprun>'
    result = parse_nmap(xml)
    assert result[0]['port'] == 443
    assert result[0]['service']['product'] == 'nginx'


@pytest.mark.parametrize('target', ['--script=all', '1.2.3.4/24', 'host;whoami', 'https://host', ''])
def test_invalid_target(target):
    with pytest.raises(ValueError):
        validate_target(target)


def test_local_scan_and_scope():
    with socket.socket() as server:
        server.bind(('127.0.0.1', 0)); server.listen()
        port = server.getsockname()[1]
        result = scan(['127.0.0.1'], ['127.0.0.1'], [port], mode='tcp')
        assert result[0]['ports'][0]['port'] == port
        with pytest.raises(ValueError):
            scan(['127.0.0.1'], [], [port], mode='tcp')


def test_reject_insecure_api_url():
    with pytest.raises(ValueError):
        fetch_json('http://example.com')


def test_web_metadata_is_data():
    result = parse_web_metadata('<html><title>Asset &amp; Lab</title><meta name="description" content="Research notes"><script>bad()</script></html>')
    assert result == {'title': 'Asset & Lab', 'description': 'Research notes'}
