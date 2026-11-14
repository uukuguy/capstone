"""Disposable parser process with deadlines and sampled RSS supervision.

RSS checks are supervisory, not a hard address-space bound. Production container
memory limits remain necessary. The child receives no Provider environment.
"""
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def _rss_bytes(pid, deadline):
    if sys.platform.startswith('linux'):
        try:
            status = Path(f'/proc/{pid}/status').read_text()
        except FileNotFoundError:
            return None
        for line in status.splitlines():
            if line.startswith('VmRSS:'):
                fields = line.split()
                if len(fields) == 3 and fields[2] == 'kB':
                    return int(fields[1])*1024
        return None
    sample = subprocess.run(['/bin/ps', '-o', 'rss=', '-p', str(pid)],
        capture_output=True, text=True, timeout=min(1, max(0.001, deadline-time.monotonic())))
    return int(sample.stdout.strip())*1024 if sample.stdout.strip() else None


def parse_isolated(parent_ref, content, *, max_input_bytes, max_blocks,
                   max_output_bytes, wall_seconds, cpu_seconds, max_rss_bytes):
    for budget in (max_input_bytes, max_blocks, max_output_bytes, cpu_seconds, max_rss_bytes):
        if type(budget) is not int or budget < 1:
            raise ValueError('invalid parser budget')
    if (type(wall_seconds) not in (int, float) or not math.isfinite(wall_seconds)
            or wall_seconds <= 0):
        raise ValueError('invalid parser deadline budget')
    if not isinstance(content, bytes) or len(content) > max_input_bytes:
        raise ValueError('parser input budget exceeded')
    with tempfile.TemporaryDirectory(prefix='capstone-paragraph-') as directory:
        root = Path(directory)
        (root/'source').write_bytes(content)
        (root/'request.json').write_text(json.dumps(dict(parent_ref=parent_ref,
            max_input_bytes=max_input_bytes, max_blocks=max_blocks,
            max_output_bytes=max_output_bytes, cpu_seconds=cpu_seconds)))
        deadline = time.monotonic() + wall_seconds
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), directory],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}, start_new_session=True)
        try:
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    raise ValueError('parser deadline exceeded')
                rss = _rss_bytes(process.pid, deadline)
                if rss is not None and rss > max_rss_bytes:
                    raise ValueError('parser memory budget exceeded')
                if rss is None and process.poll() is None:
                    raise ValueError('parser memory observation unavailable')
                time.sleep(min(0.02, max(0, deadline-time.monotonic())))
            if time.monotonic() >= deadline:
                raise ValueError('parser deadline exceeded')
            if process.returncode != 0:
                raise ValueError('isolated parser failed')
            with (root/'index.json').open('rb') as output:
                data = output.read(max_output_bytes+1)
            if len(data) > max_output_bytes:
                raise ValueError('parser output budget exceeded')
            return json.loads(data)
        except subprocess.TimeoutExpired as error:
            raise ValueError('parser deadline exceeded') from error
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


def _main(directory):
    import resource
    root = Path(directory)
    request = json.loads((root/'request.json').read_text())
    resource.setrlimit(resource.RLIMIT_CPU, (request['cpu_seconds'], request['cpu_seconds']))
    resource.setrlimit(resource.RLIMIT_FSIZE, (request['max_output_bytes'], request['max_output_bytes']))
    from capstone_agent.product_blocks import build_index
    with (root/'source').open('rb') as source:
        content = source.read(request['max_input_bytes']+1)
    index = build_index(request['parent_ref'], content,
                        max_input_bytes=request['max_input_bytes'], max_blocks=request['max_blocks'])
    data = json.dumps(index, ensure_ascii=False).encode()
    if len(data) > request['max_output_bytes']:
        raise ValueError('parser output budget exceeded')
    (root/'index.json').write_bytes(data)


if __name__ == '__main__':
    _main(sys.argv[1])
