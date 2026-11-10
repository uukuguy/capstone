"""Run the named direct consumers of the joint investigation candidate."""
from pathlib import Path
import json
import subprocess
import time


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'configs/development/investigation-closeout-gate.json').read_text())
    if manifest['schema'] != 'capstone-joint-development-gate/1':
        raise ValueError('Unsupported closeout gate')
    for name, group in manifest['groups'].items():
        for path in group['paths']:
            if '..' in Path(path).parts or Path(path).is_absolute() or not (root / path).is_file():
                raise ValueError('Invalid scoped input: ' + path)
        started = time.monotonic()
        print('Check group: ' + name, flush=True)
        subprocess.run(group['command'], cwd=root, check=True, timeout=180)
        print(f'Passed {name}: {time.monotonic() - started:.2f}s', flush=True)


if __name__ == '__main__':
    main()
