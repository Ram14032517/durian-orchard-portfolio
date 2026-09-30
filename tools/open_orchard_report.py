"""Open the existing local map; reuse its server without installing anything."""
import argparse
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from urllib.error import URLError
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:8871/research_data/five_province_history/UNIFIED_MAP.html'
MARKER = '<title>แผนที่วิเคราะห์ทุเรียน • ดิน อากาศ ฤดูกาล</title>'.encode()

def server_ready():
    try:
        with urlopen(URL, timeout=2) as response:
            return response.status == 200 and MARKER in response.read(2048)
    except (URLError, OSError):
        return False

def ensure_server():
    if server_ready():
        return 'existing'
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',8871)) == 0:
            raise RuntimeError('Port 8871 is occupied by a different/unready page. No process was stopped.')
    log_dir = ROOT / '.build'
    log_dir.mkdir(exist_ok=True)
    with (log_dir/'report_server.log').open('ab') as log:
        child = subprocess.Popen([sys.executable,str(ROOT/'tools/serve_orchard_analysis.py')],
            cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    for _ in range(40):
        if server_ready():
            return 'started'
        if child.poll() is not None:
            raise RuntimeError('Server stopped. See .build/report_server.log')
        time.sleep(0.25)
    raise RuntimeError('Server not ready yet. See .build/report_server.log and retry.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Read-only readiness check; do not start or open anything')
    args = parser.parse_args()
    if args.check:
        ready = server_ready()
        print('ready' if ready else 'not ready')
        return 0 if ready else 1
    try:
        state = ensure_server()
        print(f'Server: {state}\n{URL}')
        if not webbrowser.open(URL):
            print('Open the URL above in your browser.')
        return 0
    except Exception as exc:
        print(f'Cannot open report: {exc}',file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
