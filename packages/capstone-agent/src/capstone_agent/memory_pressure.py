"""Read worker memory pressure without importing domain or runtime objects."""

from pathlib import Path


def worker_memory_pressure(*, proc_root: Path = Path('/proc'),
                           cgroup_root: Path = Path('/sys/fs/cgroup')) -> bool:
    """Use container headroom and host available memory, whichever is tighter.

    Unknown measurements do not trigger destructive cache churn. Context count
    remains an independent safety ceiling. Linux workers expose cgroup v2 or v1;
    host MemAvailable includes reclaimable pages rather than only free pages.
    """
    budgets: list[tuple[int, int]] = []
    for limit_path, usage_path in (
        (cgroup_root / 'memory.max', cgroup_root / 'memory.current'),
        (cgroup_root / 'memory/memory.limit_in_bytes',
         cgroup_root / 'memory/memory.usage_in_bytes'),
    ):
        try:
            limit = int(limit_path.read_text().strip())
            usage = int(usage_path.read_text().strip())
            if 0 < limit < 1 << 60 and usage >= 0:
                budgets.append((limit, max(0, limit - usage)))
                break
        except (OSError, ValueError):
            continue
    try:
        values = {}
        for line in (proc_root / 'meminfo').read_text().splitlines():
            key, _, value = line.partition(':')
            if key in {'MemTotal', 'MemAvailable'}:
                values[key] = int(value.split()[0]) * 1024
        if values.get('MemTotal', 0) > 0 and 'MemAvailable' in values:
            budgets.append((values['MemTotal'], values['MemAvailable']))
    except (OSError, ValueError, IndexError):
        pass
    return any(available < min(256 * 1024**2, total // 8)
               for total, available in budgets)
