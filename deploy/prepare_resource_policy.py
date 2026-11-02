"""Seed a private resource policy once; preserve operator changes on rebuild."""
import argparse
import json
from pathlib import Path
import os
import sys


def prepare(directory: Path, template: Path):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink():
        raise ValueError('resource policy directory must not be a link')
    target = directory / 'resource-permissions.json'
    if target.is_symlink():
        raise ValueError('resource policy file must not be a link')
    try:
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        json.loads(target.read_text())
        return target
    try:
        content = template.read_bytes()
        json.loads(content)
        with os.fdopen(descriptor, 'wb') as writer:
            writer.write(content)
            writer.flush()
            os.fsync(writer.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path)
    parser.add_argument('--compose-config-stdin',action='store_true')
    args=parser.parse_args()
    directory=args.directory
    if args.compose_config_stdin:
        configuration=json.load(sys.stdin)
        matches=[v['source'] for v in configuration['services']['general-pi']['volumes']
                 if v.get('type')=='bind' and v.get('target')=='/run/capstone-private/resource-policy' and v.get('read_only') is True]
        if len(matches)!=1:raise ValueError('missing protected resource policy mount')
        directory=Path(matches[0])
    if directory is None:parser.error('select --directory or --compose-config-stdin')
    prepare(directory,Path(__file__).resolve().parents[1]/'configs/runtime/resource-permissions.json')
    print('Resource permission policy is ready; existing settings preserved.')
