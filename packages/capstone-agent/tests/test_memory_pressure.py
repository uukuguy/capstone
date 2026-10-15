from capstone_agent.memory_pressure import worker_memory_pressure


def test_container_pressure_overrides_host_headroom(tmp_path):
    proc = tmp_path / 'proc'
    group = tmp_path / 'group'
    proc.mkdir()
    group.mkdir()
    (proc / 'meminfo').write_text('MemTotal: 8388608 kB\nMemAvailable: 4194304 kB\n')
    (group / 'memory.max').write_text(str(512 * 1024**2))
    (group / 'memory.current').write_text(str(500 * 1024**2))
    assert worker_memory_pressure(proc_root=proc, cgroup_root=group)
    (group / 'memory.current').write_text(str(200 * 1024**2))
    assert not worker_memory_pressure(proc_root=proc, cgroup_root=group)


def test_unlimited_container_uses_host_available_memory(tmp_path):
    (tmp_path / 'memory.max').write_text('max')
    (tmp_path / 'memory.current').write_text('1')
    (tmp_path / 'meminfo').write_text('MemTotal: 1048576 kB\nMemAvailable: 20480 kB\n')
    assert worker_memory_pressure(proc_root=tmp_path, cgroup_root=tmp_path)


def test_missing_measurements_do_not_trigger_repeated_eviction(tmp_path):
    assert not worker_memory_pressure(proc_root=tmp_path, cgroup_root=tmp_path)


def test_v1_container_limit_is_supported(tmp_path):
    memory = tmp_path / 'memory'
    memory.mkdir()
    (memory / 'memory.limit_in_bytes').write_text(str(1024**3))
    (memory / 'memory.usage_in_bytes').write_text(str(1000 * 1024**2))
    assert worker_memory_pressure(proc_root=tmp_path, cgroup_root=tmp_path)
