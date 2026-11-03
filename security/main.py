"""Collect port and service information for hosts in an allowlist."""
import argparse
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def validate_target(target):
    target = target.strip().lower().rstrip('.')
    try:
        return str(ipaddress.ip_address(target))
    except ValueError:
        if len(target) > 253 or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', target):
            raise ValueError('Target must be a single IP or hostname, not a URL, range, or command option.')
        if any(not label or len(label) > 63 or label.startswith('-') or label.endswith('-') for label in target.split('.')):
            raise ValueError('Invalid hostname')
        return target


def parse_nmap(xml):
    root = ET.fromstring(xml)
    rows = []
    for port in root.findall('.//host/ports/port'):
        state = port.find('state')
        if state is not None and state.get('state') == 'open':
            service = port.find('service')
            rows.append({'port': int(port.get('portid')), 'protocol': port.get('protocol'),
                         'service': dict(service.attrib) if service is not None else {}})
    return rows


def tcp_port(ip, port, timeout):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return {'port': port, 'protocol': 'tcp', 'service': {}, 'state': 'open'}
    except (OSError, TimeoutError):
        return None


def scan(targets, allowlist, ports, mode='tcp', workers=4, timeout=1, native=None):
    targets = list(dict.fromkeys(validate_target(t) for t in targets))
    allowed = {validate_target(t) for t in allowlist}
    if not targets or len(targets) > 128 or not set(targets) <= allowed:
        raise ValueError('Supply 1..128 targets, all explicitly present in allowlist.')
    if not ports or len(ports) > 1024 or any(not 1 <= p <= 65535 for p in ports):
        raise ValueError('Supply 1..1024 ports in range 1..65535.')
    if not 1 <= workers <= 16 or not .05 <= timeout <= 10:
        raise ValueError('workers=1..16, timeout=0.05..10 seconds')
    if mode not in {'tcp', 'nmap', 'rust', 'c'}:
        raise ValueError('mode must be tcp, nmap, rust, or c')
    if mode == 'nmap' and not shutil.which('nmap'):
        raise RuntimeError('Nmap is not installed/on PATH. Install it or use --mode tcp.')
    if mode in {'rust', 'c'} and (native is None or not Path(native).is_file()):
        raise ValueError('Native mode requires --native pointing to the built executable.')

    def one(target):
        try:
            # Resolve once and pass pinned numeric IPs to scanners, avoiding a second DNS lookup.
            ips = sorted({entry[4][0] for entry in socket.getaddrinfo(target, None, type=socket.SOCK_STREAM)})
            if len(ips) > 16:
                raise ValueError('Host resolves to more than 16 addresses')
            findings = []
            for ip in ips:
                if mode == 'tcp':
                    rows = [row for p in ports if (row := tcp_port(ip, p, timeout))]
                elif mode in {'rust', 'c'}:
                    process = subprocess.run([str(Path(native).resolve()), ip, ','.join(map(str, ports)), str(int(timeout * 1000))],
                                             capture_output=True, text=True, timeout=len(ports) * timeout + 5, check=True)
                    rows = [{'port': int(p), 'protocol': 'tcp', 'service': {}, 'state': 'open'} for p in process.stdout.split()]
                else:
                    command = ['nmap', '-sT', '-sV', '--version-light', '-Pn', '-n', '--host-timeout', '60s',
                               '-p', ','.join(map(str, ports)), '-oX', '-']
                    if ':' in ip:
                        command.append('-6')
                    process = subprocess.run(command + [ip], capture_output=True, text=True, timeout=65, check=True)
                    rows = parse_nmap(process.stdout)
                findings.extend(dict(row, ip=ip) for row in rows)
            return {'target': target, 'resolved_ips': ips, 'mode': mode, 'ports': findings, 'status': 'ok'}
        except (OSError, ValueError, subprocess.SubprocessError, ET.ParseError) as exc:
            return {'target': target, 'status': 'error', 'error': type(exc).__name__, 'ports': []}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, targets))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def parse_web_metadata(html):
    class Metadata(HTMLParser):
        def __init__(self):
            super().__init__(); self.in_title = False; self.title = []; self.description = ''

        def handle_starttag(self, tag, attrs):
            if tag == 'title':
                self.in_title = True
            attrs = dict(attrs)
            if tag == 'meta' and attrs.get('name', '').lower() == 'description':
                self.description = (attrs.get('content') or '')[:1000]

        def handle_endtag(self, tag):
            if tag == 'title':
                self.in_title = False

        def handle_data(self, text):
            if self.in_title:
                self.title.append(text)
    parser = Metadata(); parser.feed(html)
    return {'title': ''.join(parser.title).strip()[:500], 'description': parser.description}


def web_metadata(target, *, port=443, ssl_context=None):
    target = validate_target(target)
    if not 1 <= port <= 65535:
        raise ValueError('HTTPS port must be 1..65535')
    host = '[' + target + ']' if ':' in target else target
    if port != 443:
        host += ':' + str(port)
    request = urllib.request.Request('https://' + host + '/', headers={'User-Agent': 'PortfolioAssetInventory/0.1'})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPSHandler(context=ssl_context)).open(request, timeout=10) as response:
            content = response.read(500_001)
            if len(content) > 500_000:
                return {'status': 'error', 'error': 'HTML exceeds 500KB limit'}
            if response.headers.get_content_type() != 'text/html':
                return {'status': 'skipped', 'reason': 'not HTML'}
            return {'status': 'ok', **parse_web_metadata(content.decode(response.headers.get_content_charset() or 'utf-8', errors='replace'))}
    except urllib.error.HTTPError as exc:
        return {'status': 'error', 'http_status': exc.code}
    except (OSError, LookupError, ValueError) as exc:
        return {'status': 'error', 'error': type(exc).__name__}


def fetch_json(url, headers=None):
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise ValueError('API URL must use HTTPS')
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as response:
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                return {'status': 'error', 'error': 'response too large'}
            return {'status': 'ok', 'data': json.loads(data)}
    except urllib.error.HTTPError as exc:
        # Never include URL/query/header in errors: Shodan uses a query-string key.
        return {'status': 'error', 'http_status': exc.code}
    except (OSError, ValueError) as exc:
        return {'status': 'error', 'error': type(exc).__name__}


def enrich(row, providers):
    evidence = {}
    if 'virustotal' in providers:
        key = os.environ.get('VIRUSTOTAL_API_KEY')
        target = row['target']
        try:
            ipaddress.ip_address(target); kind = 'ip_addresses'
        except ValueError:
            kind = 'domains'
        evidence['virustotal'] = fetch_json('https://www.virustotal.com/api/v3/' + kind + '/' + urllib.parse.quote(target, safe=''),
                                           {'x-apikey': key}) if key else {'status': 'unavailable', 'reason': 'VIRUSTOTAL_API_KEY missing'}
    if 'shodan' in providers:
        key = os.environ.get('SHODAN_API_KEY')
        evidence['shodan'] = {ip: fetch_json('https://api.shodan.io/shodan/host/' + urllib.parse.quote(ip, safe='') + '?' +
                                            urllib.parse.urlencode({'key': key, 'minify': 'true'}))
                              for ip in row.get('resolved_ips', [])} if key else {'status': 'unavailable', 'reason': 'SHODAN_API_KEY missing'}
    return row | {'osint': evidence}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--targets', nargs='+', required=True)
    parser.add_argument('--allowlist', type=Path, required=True, help='One authorized hostname/IP per line')
    parser.add_argument('--ports', default='80,443')
    parser.add_argument('--mode', choices=['tcp', 'nmap', 'rust', 'c'], default='tcp')
    parser.add_argument('--native', type=Path)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--timeout', type=float, default=1)
    parser.add_argument('--providers', nargs='*', choices=['shodan', 'virustotal'], default=[])
    parser.add_argument('--web', action='store_true', help='Fetch HTTPS title/description from each allowed host, without following redirects')
    parser.add_argument('--output', type=Path, default=Path('reports/security.json'))
    args = parser.parse_args()
    allowed = [line.strip() for line in args.allowlist.read_text().splitlines() if line.strip() and not line.startswith('#')]
    report = scan(args.targets, allowed, [int(p) for p in args.ports.split(',')], args.mode, args.workers, args.timeout, args.native)
    # Keep provider calls sequential and report rate limits without retrying.
    report = [enrich(row, args.providers) for row in report]
    if args.web:
        report = [row | {'web': web_metadata(row['target'])} for row in report]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
