# Workstream A Domain Kernel Seams Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Design reference:** [`2026-08-27-general-domain-agent-framework-upgrade-design.md`](../specs/2026-08-27-general-domain-agent-framework-upgrade-design.md)

**Goal:** 在不改变现有 grid CLI、`grid-capability/1.0`、模型工具、证据、运行目录和答案信封的前提下，把 pandapower 业务装配收敛到一个内建领域 Profile，并为合同发现、执行、投影和证据权威建立可验证的中立接口。

**Architecture:** 新的 `grid_agent.domain` 仅定义中立运行时协议和值对象；`grid_agent.domains.pandapower` 把现有 `GridctlClient`、`project_domain_result` 和 `ContentReferenceVerifier` 包装为第一个领域实现；`grid_agent.application.composition` 负责从 Profile 生成环境描述、工具目录、指南索引、执行器和权威对象。CLI 只选择内建 Profile，不再独立拼接合同与指南路径或直接构造具体执行器/验证器。

**Tech Stack:** Python >=3.12, Pydantic >=2.12,<3, pytest >=9,<10, Typer, JSON Schema 2020-12, Pi RPC, `grid-capability/1.0`, Markdown.

## Global Constraints

- 本计划只实施批准规格中的 Workstream A；不移动 Python distribution，不全局改名，不增加生产级第二领域，不引入写操作、审批流、多领域路由或新协议。
- `grid-agent run`、`analysis`、`report`、`doctor`、认证和 trajectory 命令的名称、参数和退出语义保持不变。
- 默认 CLI stdout 仍必须恰好为一个只含 `question_id` 与 `answer_output` 的 JSON 对象；所有进度、警告和诊断仍写 stderr。
- 数值、网络、拓扑、排序和证据事实仍只能由当前运行的 `gridctl` 经 `grid-capability/1.0` 返回；不得引入绕过 simulator boundary 的快捷路径。
- 所有现有 `grid_*` 工具名称、输入 schema、`grid-tool-catalog/1.0` 物化格式和 `grid_record_decision` 行为保持兼容。
- pandapower 对象、DataFrame、任意 shell/文件/Python 能力不得暴露给模型。
- `runs/`、`.grid-agent/`、证据引用、trajectory 与 analysis context 的 schema 和路径保持可读且不迁移。
- 中立 `grid_agent.domain` 模块不得导入 `grid_agent.simulator`、`grid_agent.domains`、pandapower 领域投影实现或 simulator capability definition 路径。
- 合成领域只存在于测试中；不得在生产 CLI 增加领域选择参数或隐式 fallback。
- 每个任务先运行最小失败测试，再实施，再运行相关回归并原子提交；只暂存任务自有文件。
- 不运行 `make validate-provider`；它需要显式凭证与计费授权。
- 当前工作树已有用户/状态维护改动 `docs/status/JOURNAL.md` 与 `docs/status/RESUME-NEXT-SESSION.md`；实现者不得覆盖、还原或混入功能提交。

---

## Dependency and Delivery Boundary

本计划输出 Workstream B 可以直接搬移、Workstream C 可以直接实现的稳定 seam：

- `DomainManifest`：领域身份、协议、执行器名、工具前缀和版本化资源位置；
- `CapabilityContractSource`：合同发现所有权；
- `CapabilityExecutor`：业务调用边界；
- `DomainProjectorRegistry`：业务结果到持久领域状态的解释边界；
- `ArtifactAuthority`：当前运行结果、证据和引用准入边界；
- `DomainRuntimeProfile`：单领域应用的唯一装配根；
- `prepare_domain_runtime(...)`：CLI 共享的 provider-free 领域物化流程。

本计划不承诺 Agent Kernel 已成为独立发布包。只有后续非 grid 领域在不修改 Kernel 的情况下通过同一 SPI 后，才能宣称框架完成通用化。

## File Map

### Neutral domain runtime

- Create `packages/grid-agent/src/grid_agent/domain/__init__.py`
- Create `packages/grid-agent/src/grid_agent/domain/manifest.py`
- Create `packages/grid-agent/src/grid_agent/domain/contracts.py`
- Create `packages/grid-agent/src/grid_agent/domain/execution.py`
- Create `packages/grid-agent/src/grid_agent/domain/projection.py`
- Create `packages/grid-agent/src/grid_agent/domain/authority.py`
- Create `packages/grid-agent/src/grid_agent/domain/profile.py`

### Built-in pandapower integration

- Create `packages/grid-agent/src/grid_agent/domains/__init__.py`
- Create `packages/grid-agent/src/grid_agent/domains/pandapower.py`
- Modify `packages/grid-agent/src/grid_agent/analysis/projector.py`
- Preserve `packages/grid-agent/src/grid_agent/analysis/domain_projection.py`
- Preserve `packages/grid-agent/src/grid_agent/analysis/integrity.py`
- Preserve `packages/grid-agent/src/grid_agent/simulator/client.py`

### Shared composition and CLI routing

- Create `packages/grid-agent/src/grid_agent/application/composition.py`
- Modify `packages/grid-agent/src/grid_agent/cli/app.py`
- Modify `packages/grid-agent/src/grid_agent/tools/catalog.py`

### Tests and documentation

- Create `packages/grid-agent/tests/domain/__init__.py`
- Create `packages/grid-agent/tests/domain/test_manifest.py`
- Create `packages/grid-agent/tests/domain/test_contracts.py`
- Create `packages/grid-agent/tests/domain/test_profile.py`
- Create `packages/grid-agent/tests/domain/test_pandapower_profile.py`
- Create `packages/grid-agent/tests/application/test_composition.py`
- Create `packages/grid-agent/tests/contract/test_domain_runtime_boundaries.py`
- Modify `packages/grid-agent/tests/tools/test_catalog.py`
- Modify `packages/grid-agent/tests/analysis/test_projector.py`
- Modify `packages/grid-agent/tests/cli/test_app.py`
- Modify `docs/architecture/pandapower-capability-composition.md`
- Modify `docs/RUNBOOK.md`
- Modify `docs/status/CURRENT-STATE.md`

---

### Task 1: Lock the current externally observable assembly contract

**Files:**

- Modify: `packages/grid-agent/tests/tools/test_catalog.py`
- Modify: `packages/grid-agent/tests/tools/test_guide.py`
- Modify: `packages/grid-agent/tests/simulator/test_client.py`
- Modify: `packages/grid-agent/tests/cli/test_app.py`

**Interfaces:**

- Consumes: current packaged capability documents, current `environment.describe`, current grid guide root, current CLI commands.
- Produces: characterization tests for exact tool names/schemas, guide materialization, wire protocol and stdout envelope.

- [ ] **Step 1: Add a catalog characterization test before changing catalog construction**

Add a test that records the current product contract without hard-coding an entire generated JSON file:

```python
def test_grid_catalog_characterization_preserves_names_and_schemas(
    capability_documents: tuple[dict[str, object], ...],
) -> None:
    executable = [
        {"id": document["id"]}
        for document in capability_documents
        if document["availability"] == "published"
    ]

    catalog = ToolCatalog.from_environment(
        capability_documents,
        {"executable_capabilities": executable},
    )

    expected = {
        str(document["tool_name"]): (
            str(document["id"]),
            document["input_schema"],
        )
        for document in capability_documents
    }
    expected["grid_record_decision"] = (
        "grid_record_decision",
        catalog.require("grid_record_decision").input_schema,
    )
    assert {
        tool.name: (tool.capability, tool.input_schema)
        for tool in catalog.tools
    } == expected
```

- [ ] **Step 2: Add guide and protocol characterization assertions**

In `test_guide.py`, assert materialization remains `grid-guide-index/1.0`, contains `overview`, and points only under `skills/grid-static-analysis`. In `test_client.py`, extend the fake executable assertion so the request still contains:

```python
assert request["protocol"] == "grid-capability"
assert request["protocol_version"] == "1.0"
assert request["capability"] == "model.list"
assert request["arguments"] == {}
```

In `test_app.py`, retain the existing one-line stdout assertion and add `assert result.stderr == ""` for the monkeypatched successful `analysis` characterization path.

- [ ] **Step 3: Run the characterization slice**

Run:

```bash
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/tools/test_catalog.py \
  packages/grid-agent/tests/tools/test_guide.py \
  packages/grid-agent/tests/simulator/test_client.py \
  packages/grid-agent/tests/cli/test_app.py -q
```

Expected: PASS before production changes. A failure means the assertion does not describe the present contract; fix the test, not production behavior.

- [ ] **Step 4: Commit only the characterization tests**

```bash
git add packages/grid-agent/tests/tools/test_catalog.py \
  packages/grid-agent/tests/tools/test_guide.py \
  packages/grid-agent/tests/simulator/test_client.py \
  packages/grid-agent/tests/cli/test_app.py
git commit -m "test: lock domain assembly compatibility"
```

---

### Task 2: Introduce neutral domain contracts and the profile value object

**Files:**

- Create: `packages/grid-agent/src/grid_agent/domain/__init__.py`
- Create: `packages/grid-agent/src/grid_agent/domain/manifest.py`
- Create: `packages/grid-agent/src/grid_agent/domain/contracts.py`
- Create: `packages/grid-agent/src/grid_agent/domain/execution.py`
- Create: `packages/grid-agent/src/grid_agent/domain/projection.py`
- Create: `packages/grid-agent/src/grid_agent/domain/authority.py`
- Create: `packages/grid-agent/src/grid_agent/domain/profile.py`
- Create: `packages/grid-agent/tests/domain/__init__.py`
- Create: `packages/grid-agent/tests/domain/test_manifest.py`
- Create: `packages/grid-agent/tests/domain/test_profile.py`

**Interfaces:**

- Consumes: domain metadata, contract/executor/projector/authority structural implementations and run-scoped factories.
- Produces: validated `DomainManifest`, structural protocols and the neutral `DomainRuntimeProfile` composition value.

- [ ] **Step 1: Write failing manifest and profile tests**

```python
# packages/grid-agent/tests/domain/test_manifest.py
from pathlib import Path

import pytest

from grid_agent.domain.manifest import DomainManifest, DomainManifestError


def manifest(tmp_path: Path, **changes: object) -> DomainManifest:
    values: dict[str, object] = {
        "domain_id": "inventory-readonly",
        "version": "1.0.0",
        "display_name": "Inventory",
        "protocol": "inventory-capability",
        "protocol_version": "1.0",
        "executable_name": "inventoryctl",
        "tool_name_prefix": "inventory_",
        "authority_id": "inventory-api",
        "capability_contract_root": tmp_path / "contracts",
        "system_policy_path": tmp_path / "policy.md",
        "guide_root": tmp_path / "guides",
    }
    values.update(changes)
    return DomainManifest(**values)  # type: ignore[arg-type]


def test_manifest_accepts_compatible_environment(tmp_path: Path) -> None:
    value = manifest(tmp_path)
    value.assert_environment_compatible(
        {"protocol": "inventory-capability", "protocol_version": "1.0"}
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"domain_id": "Inventory"}, "domain_id"),
        ({"executable_name": "bin/inventoryctl"}, "executable_name"),
        ({"tool_name_prefix": "inventory"}, "tool_name_prefix"),
    ],
)
def test_manifest_rejects_unsafe_identity_fields(
    tmp_path: Path, changes: dict[str, object], message: str
) -> None:
    with pytest.raises(DomainManifestError, match=message):
        manifest(tmp_path, **changes)


def test_manifest_rejects_runtime_protocol_mismatch(tmp_path: Path) -> None:
    with pytest.raises(DomainManifestError, match="protocol_version"):
        manifest(tmp_path).assert_environment_compatible(
            {"protocol": "inventory-capability", "protocol_version": "2.0"}
        )


def test_manifest_rejects_missing_versioned_resources(tmp_path: Path) -> None:
    with pytest.raises(DomainManifestError, match="capability_contract_root"):
        manifest(tmp_path).assert_resources_present()
```

```python
# packages/grid-agent/tests/domain/test_profile.py
def test_profile_factories_create_run_scoped_dependencies(tmp_path: Path) -> None:
    executor = RecordingExecutor()
    authority = RecordingAuthority(tmp_path / "run")
    profile = DomainRuntimeProfile(
        manifest=manifest(tmp_path),
        contract_source=StubContractSource(),
        executor_factory=lambda executable, workspace, timeout: executor,
        projector_registry=StubProjectorRegistry(),
        authority_factory=lambda workspace: authority,
    )

    assert profile.create_executor(
        tmp_path / "inventoryctl", tmp_path / "run", 30
    ) is executor
    assert profile.create_authority(tmp_path / "run") is authority
```

Define the four test doubles in `test_profile.py` with the exact public protocol methods. They return inert values and perform no filesystem, subprocess or provider work.

- [ ] **Step 2: Run tests and verify the new namespaces are absent**

```bash
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/domain/test_manifest.py \
  packages/grid-agent/tests/domain/test_profile.py -q
```

Expected: FAIL importing `grid_agent.domain`.

- [ ] **Step 3: Implement `DomainManifest` with early compatibility validation**

```python
# packages/grid-agent/src/grid_agent/domain/manifest.py
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


_ID = re.compile(r"^[a-z][a-z0-9.-]*$")
_PROTOCOL = re.compile(r"^[a-z][a-z0-9.-]*$")
_TOOL_PREFIX = re.compile(r"^[a-z][a-z0-9_]*_$")


class DomainManifestError(ValueError):
    """The selected domain profile is incomplete or incompatible."""


@dataclass(frozen=True, slots=True)
class DomainManifest:
    domain_id: str
    version: str
    display_name: str
    protocol: str
    protocol_version: str
    executable_name: str
    tool_name_prefix: str
    authority_id: str
    capability_contract_root: Path
    system_policy_path: Path
    guide_root: Path

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.domain_id):
            raise DomainManifestError("domain_id is invalid")
        if not self.version.strip() or not self.display_name.strip():
            raise DomainManifestError("version and display_name are required")
        if not _PROTOCOL.fullmatch(self.protocol):
            raise DomainManifestError("protocol is invalid")
        if not self.protocol_version.strip():
            raise DomainManifestError("protocol_version is required")
        if (
            not self.executable_name
            or "/" in self.executable_name
            or "\\" in self.executable_name
        ):
            raise DomainManifestError("executable_name must be a basename")
        if not _TOOL_PREFIX.fullmatch(self.tool_name_prefix):
            raise DomainManifestError("tool_name_prefix is invalid")
        if not _ID.fullmatch(self.authority_id):
            raise DomainManifestError("authority_id is invalid")

    def assert_resources_present(self) -> None:
        checks = (
            ("capability_contract_root", self.capability_contract_root, "directory"),
            ("system_policy_path", self.system_policy_path, "file"),
            ("guide_root", self.guide_root, "directory"),
        )
        for field, path, kind in checks:
            present = path.is_dir() if kind == "directory" else path.is_file()
            if not present:
                raise DomainManifestError(f"{field} is missing: {path}")

    def assert_environment_compatible(self, environment: Mapping[str, object]) -> None:
        for field, expected in (
            ("protocol", self.protocol),
            ("protocol_version", self.protocol_version),
        ):
            if environment.get(field) != expected:
                raise DomainManifestError(
                    f"environment {field} does not match domain manifest: {expected}"
                )
```

- [ ] **Step 4: Define structural protocols without importing grid implementations**

Use these public shapes in the neutral namespace:

```python
# grid_agent/domain/contracts.py
class CapabilityContractSource(Protocol):
    def load(self) -> tuple[dict[str, object], ...]: ...


# grid_agent/domain/execution.py
class CapabilityExecutor(Protocol):
    def invoke(
        self, capability: str, arguments: dict[str, object]
    ) -> dict[str, object]: ...


# grid_agent/domain/projection.py
@dataclass(frozen=True, slots=True)
class VerifiedInvocation:
    capability: str
    projector_id: str
    result_kind: str | None
    result: Mapping[str, Any]
    arguments: Mapping[str, Any]
    turn_id: str
    result_paths: Mapping[str, str]
    active_revision_ref: str | None


class DomainStateDelta(Protocol):
    def model_dump(self, *, mode: str = "python") -> dict[str, Any]: ...


class DomainProjector(Protocol):
    projector_id: str
    def project(self, invocation: VerifiedInvocation) -> DomainStateDelta: ...


class DomainProjectorRegistry(Protocol):
    def require(self, projector_id: str) -> DomainProjector: ...
```

`ArtifactAuthority` must expose every operation currently required by run, continuous projection, and turn audit, so core code does not retain a concrete verifier escape hatch:

```python
# grid_agent/domain/authority.py
class VerifiedArtifact(Protocol):
    reference: str
    document: Mapping[str, Any]
    path: Path


class VerifiedReferenceSet(Protocol):
    context: tuple[VerifiedArtifact, ...]
    results: tuple[VerifiedArtifact, ...]
    evidence: tuple[VerifiedArtifact, ...]


class ArtifactAuthority(Protocol):
    authority_id: str
    workspace_root: Path

    def admit(
        self,
        capability: str,
        result: Mapping[str, object],
        evidence_refs: tuple[str, ...],
    ) -> VerifiedReferenceSet: ...

    def verify_result(self, reference: str) -> VerifiedArtifact: ...

    def audit_answer_references(
        self,
        claim_evidence_refs: tuple[str, ...],
        result_refs: tuple[str, ...],
    ) -> tuple[object, ...]: ...
```

- [ ] **Step 5: Implement the profile value object**

`DomainRuntimeProfile` owns factories because executor and authority instances are scoped to a run workspace:

```python
# grid_agent/domain/profile.py
ExecutorFactory = Callable[[Path, Path, float], CapabilityExecutor]
AuthorityFactory = Callable[[Path], ArtifactAuthority]


@dataclass(frozen=True, slots=True)
class DomainRuntimeProfile:
    manifest: DomainManifest
    contract_source: CapabilityContractSource
    executor_factory: ExecutorFactory
    projector_registry: DomainProjectorRegistry
    authority_factory: AuthorityFactory

    def create_executor(
        self, executable: Path, workspace: Path, timeout_seconds: float
    ) -> CapabilityExecutor:
        return self.executor_factory(executable, workspace, timeout_seconds)

    def create_authority(self, workspace: Path) -> ArtifactAuthority:
        return self.authority_factory(workspace)
```

- [ ] **Step 6: Export only stable interfaces**

`grid_agent.domain.__init__` exports the manifest, five protocols/value types and `DomainRuntimeProfile`. Do not export concrete simulator, verifier or projector implementation classes from the neutral namespace.

- [ ] **Step 7: Run focused tests**

```bash
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/domain/test_manifest.py \
  packages/grid-agent/tests/domain/test_profile.py -q
```

Expected: PASS; the neutral namespace imports no existing grid implementation.

- [ ] **Step 8: Commit the neutral SPI and profile value object**

```bash
git add packages/grid-agent/src/grid_agent/domain \
  packages/grid-agent/tests/domain
git commit -m "feat: define neutral domain runtime seams"
```

---

### Task 3: Move capability discovery behind an injected source and parameterize the tool prefix

**Files:**

- Modify: `packages/grid-agent/src/grid_agent/domain/contracts.py`
- Create: `packages/grid-agent/src/grid_agent/domains/__init__.py`
- Create: `packages/grid-agent/src/grid_agent/domains/pandapower.py`
- Modify: `packages/grid-agent/src/grid_agent/tools/catalog.py`
- Create: `packages/grid-agent/tests/domain/test_contracts.py`
- Create: `packages/grid-agent/tests/domain/test_pandapower_profile.py`
- Modify: `packages/grid-agent/tests/tools/test_catalog.py`

**Interfaces:**

- Consumes: manifest contract root, filesystem JSON documents, runtime capability list, manifest tool prefix.
- Produces: deterministic `FilesystemCapabilityContractSource.load()`, prefix-aware `ToolCatalog`, compatibility wrapper `load_packaged_capability_documents(root)` and the built-in `build_pandapower_profile(root)`.

- [ ] **Step 1: Write failing injected-source and prefix tests**

```python
# packages/grid-agent/tests/domain/test_contracts.py
def test_filesystem_contract_source_loads_sorted_json(tmp_path: Path) -> None:
    root = tmp_path / "contracts"
    root.mkdir()
    (root / "b.json").write_text('{"id":"b.read"}', encoding="utf-8")
    (root / "a.json").write_text('{"id":"a.read"}', encoding="utf-8")

    documents = FilesystemCapabilityContractSource(root).load()

    assert [document["id"] for document in documents] == ["a.read", "b.read"]


def test_filesystem_contract_source_rejects_invalid_or_empty_roots(tmp_path: Path) -> None:
    with pytest.raises(CapabilityContractSourceError, match="no capability contracts"):
        FilesystemCapabilityContractSource(tmp_path / "missing").load()
```

```python
# packages/grid-agent/tests/tools/test_catalog.py
def test_catalog_accepts_an_injected_non_grid_tool_prefix() -> None:
    document = valid_document(
        capability="asset.list",
        tool_name="inventory_asset_list",
        projector="inventory-list-v1",
    )

    catalog = ToolCatalog.from_environment(
        [document],
        {"executable_capabilities": [{"id": "asset.list"}]},
        tool_name_prefix="inventory_",
    )

    assert [tool.name for tool in catalog.tools] == [
        "inventory_asset_list",
        "inventory_record_decision",
    ]


def test_catalog_rejects_a_tool_outside_the_selected_prefix() -> None:
    with pytest.raises(ToolCatalogError, match="tool_name_prefix"):
        ToolCatalog.from_documents(
            [valid_document(tool_name="grid_asset_list")],
            tool_name_prefix="inventory_",
        )
```

Use or add a local `valid_document(...)` test helper that returns the complete required contract shape; do not weaken production schema validation.

Add the built-in ownership test in `test_pandapower_profile.py`:

```python
ROOT = Path(__file__).resolve().parents[4]


def test_pandapower_profile_owns_all_grid_runtime_resources() -> None:
    profile = build_pandapower_profile(ROOT)

    assert profile.manifest.domain_id == "pandapower-static-analysis"
    assert profile.manifest.protocol == "grid-capability"
    assert profile.manifest.protocol_version == "1.0"
    assert profile.manifest.executable_name == "gridctl"
    assert profile.manifest.tool_name_prefix == "grid_"
    assert profile.manifest.authority_id == "gridctl"
    assert profile.manifest.capability_contract_root == (
        ROOT / "packages/grid-simulator/src/grid_simulator/capabilities/definitions"
    )
    assert profile.manifest.system_policy_path == ROOT / "configs/agent/system-policy.md"
    assert profile.manifest.guide_root == ROOT / "skills/grid-static-analysis"
```

- [ ] **Step 2: Run the tests and verify source/prefix support is absent**

```bash
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/domain/test_contracts.py \
  packages/grid-agent/tests/domain/test_pandapower_profile.py \
  packages/grid-agent/tests/tools/test_catalog.py -q
```

Expected: FAIL because `FilesystemCapabilityContractSource`, `tool_name_prefix` and the built-in domain namespace do not exist.

- [ ] **Step 3: Implement deterministic filesystem discovery**

```python
class CapabilityContractSourceError(ValueError):
    """Capability contracts cannot be discovered or decoded."""


@dataclass(frozen=True, slots=True)
class FilesystemCapabilityContractSource:
    root: Path

    def load(self) -> tuple[dict[str, object], ...]:
        paths = sorted(Path(self.root).glob("*.json"), key=lambda path: path.name)
        if not paths:
            raise CapabilityContractSourceError(
                f"no capability contracts found under {self.root}"
            )
        documents: list[dict[str, object]] = []
        for path in paths:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise CapabilityContractSourceError(
                    f"invalid capability contract: {path.name}"
                ) from exc
            if not isinstance(value, dict):
                raise CapabilityContractSourceError(
                    f"capability contract must be an object: {path.name}"
                )
            documents.append(value)
        return tuple(documents)
```

- [ ] **Step 4: Parameterize `ToolCatalog` without changing grid defaults**

Change both constructors to accept a keyword-only `tool_name_prefix: str = "grid_"`. Thread the value into `_materialize_tool`, `_validate_document`, the `ToolCatalog` constructor and `_decision_tool`. Validate the prefix before document materialization and require every tool name to begin with it.

```python
@classmethod
def from_documents(
    cls,
    documents: tuple[dict[str, object], ...] | list[dict[str, object]],
    *,
    tool_name_prefix: str = "grid_",
) -> ToolCatalog:
    _validate_tool_name_prefix(tool_name_prefix)
    return cls(
        tuple(_materialize_tool(document, tool_name_prefix) for document in documents),
        tool_name_prefix=tool_name_prefix,
    )
```

`_decision_tool(tool_name_prefix)` must produce both `name` and `capability` as `f"{tool_name_prefix}record_decision"`. The default call must still generate byte-compatible grid catalog JSON.

- [ ] **Step 5: Retain the old loader as a compatibility wrapper only**

```python
def load_packaged_capability_documents(
    repository_root: Path,
) -> tuple[dict[str, object], ...]:
    root = (
        Path(repository_root)
        / "packages/grid-simulator/src/grid_simulator/capabilities/definitions"
    )
    return FilesystemCapabilityContractSource(root).load()
```

Only this compatibility function may retain the old path. New composition code must use `profile.contract_source.load()`.

- [ ] **Step 6: Implement the pandapower compatibility Profile and adapters**

In `domains/pandapower.py`:

- construct all manifest paths from the supplied resolved repository root;
- use `FilesystemCapabilityContractSource(manifest.capability_contract_root)`;
- adapt `GridctlClient` through the executor factory without changing it;
- define `PandapowerArtifactAuthority` that delegates `admit(...)` to `ContentReferenceVerifier.admit_successful_tool_references(...)` and delegates `verify_result(...)` and `audit_answer_references(...)` unchanged;
- define `PandapowerProjectorRegistry` with one adapter per `KNOWN_CONTEXT_PROJECTORS` value;
- have each projector reconstruct the current `CapabilityContextSpec` from `VerifiedInvocation` and call the unchanged `project_domain_result(...)`;
- raise a typed lookup error for an unknown projector ID; do not add a fallback projector.

Use explicit keyword construction for the existing keyword-only client and keep all concrete imports in this domain module:

```python
class PandapowerArtifactAuthority:
    authority_id = "gridctl"

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self._verifier = ContentReferenceVerifier(workspace_root)

    def admit(
        self,
        capability: str,
        result: Mapping[str, object],
        evidence_refs: tuple[str, ...],
    ) -> VerifiedReferenceSet:
        return self._verifier.admit_successful_tool_references(
            capability, result, evidence_refs
        )

    def verify_result(self, reference: str) -> VerifiedArtifact:
        return self._verifier.verify_result(reference)

    def audit_answer_references(
        self,
        claim_evidence_refs: tuple[str, ...],
        result_refs: tuple[str, ...],
    ) -> tuple[ReferenceDiagnostic, ...]:
        return self._verifier.audit_answer_references(
            claim_evidence_refs, result_refs
        )
```

```python
def build_pandapower_profile(repository_root: Path) -> DomainRuntimeProfile:
    root = Path(repository_root).resolve()
    manifest = DomainManifest(
        domain_id="pandapower-static-analysis",
        version="1.0.1",
        display_name="Pandapower Static Analysis",
        protocol="grid-capability",
        protocol_version="1.0",
        executable_name="gridctl",
        tool_name_prefix="grid_",
        authority_id="gridctl",
        capability_contract_root=(
            root
            / "packages/grid-simulator/src/grid_simulator/capabilities/definitions"
        ),
        system_policy_path=root / "configs/agent/system-policy.md",
        guide_root=root / "skills/grid-static-analysis",
    )
    return DomainRuntimeProfile(
        manifest=manifest,
        contract_source=FilesystemCapabilityContractSource(
            manifest.capability_contract_root
        ),
        executor_factory=lambda executable, workspace, timeout: GridctlClient(
            executable=executable,
            workspace=workspace,
            timeout_seconds=timeout,
        ),
        projector_registry=PandapowerProjectorRegistry(),
        authority_factory=PandapowerArtifactAuthority,
    )
```

The projector reconstruction must preserve the fields used by current projection:

```python
spec = CapabilityContextSpec(
    capability=invocation.capability,
    availability="published",
    requires_state=(),
    consumes_state=(),
    produces_state=(),
    invalidates_state=(),
    result_kind=invocation.result_kind,
    projector=invocation.projector_id,
)
return project_domain_result(
    spec,
    result=invocation.result,
    arguments=invocation.arguments,
    turn_id=invocation.turn_id,
    result_paths=invocation.result_paths,
    active_revision_ref=invocation.active_revision_ref,
)
```

`grid_agent.domains.__init__` exports only `build_pandapower_profile`. Do not re-export its concrete adapter classes.

- [ ] **Step 7: Run focused and compatibility tests**

```bash
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/domain/test_contracts.py \
  packages/grid-agent/tests/domain/test_pandapower_profile.py \
  packages/grid-agent/tests/tools/test_catalog.py -q
```

Expected: PASS, including Task 1's exact grid tool/schema characterization.

- [ ] **Step 8: Commit contract injection, catalog generalization and the built-in Profile**

```bash
git add packages/grid-agent/src/grid_agent/domain/contracts.py \
  packages/grid-agent/src/grid_agent/domains \
  packages/grid-agent/src/grid_agent/tools/catalog.py \
  packages/grid-agent/tests/domain/test_contracts.py \
  packages/grid-agent/tests/domain/test_pandapower_profile.py \
  packages/grid-agent/tests/tools/test_catalog.py
git commit -m "feat: add the pandapower domain profile"
```

---

### Task 4: Build provider-free profile composition around an injected executor

**Files:**

- Create: `packages/grid-agent/src/grid_agent/application/composition.py`
- Create: `packages/grid-agent/tests/application/test_composition.py`

**Interfaces:**

- Consumes: `DomainRuntimeProfile`, executable path, workspace root, catalog output path, guide output path.
- Produces: `PreparedDomainRuntime` containing executor, authority, environment description, documents, catalog and guide paths.

- [ ] **Step 1: Write failing composition tests using an in-memory executor**

```python
@dataclass
class RecordingExecutor:
    environment: dict[str, object]
    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def invoke(
        self, capability: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        self.calls.append((capability, arguments))
        return self.environment


def test_prepare_domain_runtime_uses_injected_profile_resources(tmp_path: Path) -> None:
    profile, executor = synthetic_profile(tmp_path)

    prepared = prepare_domain_runtime(
        profile,
        executable=tmp_path / "bin/inventoryctl",
        workspace=tmp_path / "run",
        tool_catalog_path=tmp_path / "run/tool-catalog.json",
        guide_index_path=tmp_path / "run/guide-index.json",
    )

    assert executor.calls == [("environment.describe", {})]
    assert prepared.executor is executor
    assert prepared.authority.authority_id == "inventory-api"
    assert prepared.environment_description["protocol"] == "inventory-capability"
    assert prepared.tool_catalog_path.is_file()
    assert prepared.guide_index_path.is_file()
```

Add a second test where the fake executor returns protocol version `2.0`; an executor factory counter must prove the provider/Pi launcher is never invoked. The expected exception is `DomainManifestError`, not a generic `KeyError`.

- [ ] **Step 2: Run the test and verify shared composition is absent**

```bash
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/application/test_composition.py -q
```

Expected: FAIL importing `grid_agent.application.composition`.

- [ ] **Step 3: Implement a narrow immutable prepared runtime**

```python
@dataclass(frozen=True, slots=True)
class PreparedDomainRuntime:
    profile: DomainRuntimeProfile
    executor: CapabilityExecutor
    authority: ArtifactAuthority
    environment_description: dict[str, object]
    capability_documents: tuple[dict[str, object], ...]
    tool_catalog_path: Path
    guide_index_path: Path
```

Implement `prepare_domain_runtime(...)` in this exact order:

1. call `profile.manifest.assert_resources_present()`;
2. load contracts from `profile.contract_source`;
3. create the executor from `profile.create_executor(...)`;
4. invoke `environment.describe` with `{}`;
5. call `profile.manifest.assert_environment_compatible(...)`;
6. call `ToolCatalog.from_environment(..., tool_name_prefix=profile.manifest.tool_name_prefix)`;
7. materialize the catalog to the supplied path;
8. load/materialize `GuideIndex` from `profile.manifest.guide_root`;
9. create the artifact authority for the same workspace;
10. return `PreparedDomainRuntime`.

Do not resolve LLM providers, install executables, read credentials, create Pi clients or select a default profile in this function.

- [ ] **Step 4: Run focused composition tests**

```bash
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/application/test_composition.py \
  packages/grid-agent/tests/domain \
  packages/grid-agent/tests/tools/test_catalog.py \
  packages/grid-agent/tests/tools/test_guide.py -q
```

Expected: PASS. Inspect generated JSON in the test and assert it contains `inventory_asset_list`, not `grid_asset_list`.

- [ ] **Step 5: Commit the shared composition root**

```bash
git add packages/grid-agent/src/grid_agent/application/composition.py \
  packages/grid-agent/tests/application/test_composition.py
git commit -m "feat: compose domains through injected executors"
```

---

### Task 5: Route continuous projection and evidence through domain adapters

**Files:**

- Modify: `packages/grid-agent/src/grid_agent/analysis/projector.py`
- Modify: `packages/grid-agent/tests/analysis/test_projector.py`
- Modify: `packages/grid-agent/tests/domain/test_pandapower_profile.py`

**Interfaces:**

- Consumes: `ArtifactAuthority`, `DomainProjectorRegistry`, existing `CapabilityContextCatalog` and tool events.
- Produces: unchanged `domain.state.projected`, result/evidence/fact records and fail-closed integrity behavior without concrete verifier/projector imports in orchestration.

- [ ] **Step 1: Write failing adapter-equivalence tests**

Modify the `context_harness` fixture to obtain adapters from the built-in profile and add spy wrappers:

```python
profile = build_pandapower_profile(ROOT)
authority = profile.create_authority(workspace.root_path)
projector = AnalysisContextProjector(
    store,
    authority,
    CapabilityContextCatalog.from_documents(documents),
    profile.projector_registry,
)
```

Add assertions that:

- a successful `analysis.powerflow.ac.run` calls `authority.admit(...)` once with the same evidence refs;
- `powerflow-ac-v1` is resolved through `projector_registry.require(...)`;
- the persisted `DomainStateDelta.model_dump(mode="json")` equals the pre-refactor projection payload;
- missing current-run evidence still raises `SimulatorIntegrityError` before cross-turn state is registered;
- result consumer verification still calls `authority.verify_result(...)`.

- [ ] **Step 2: Run the projector slice and observe constructor/signature failure**

```bash
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/analysis/test_projector.py -q
```

Expected: FAIL because `AnalysisContextProjector` does not accept a registry and calls `ContentReferenceVerifier` methods directly.

- [ ] **Step 3: Replace concrete dependencies in `AnalysisContextProjector`**

The constructor becomes:

```python
def __init__(
    self,
    store: AnalysisContextStore,
    authority: ArtifactAuthority,
    capability_catalog: CapabilityContextCatalog,
    projector_registry: DomainProjectorRegistry,
) -> None:
    self._store = store
    self._authority = authority
    self._capability_catalog = capability_catalog
    self._projector_registry = projector_registry
```

Mechanical replacements:

- `self._verifier.workspace_root` -> `self._authority.workspace_root`;
- `admit_successful_tool_references(...)` -> `self._authority.admit(...)`;
- `verify_result(...)` -> `self._authority.verify_result(...)`;
- keep `SimulatorIntegrityError` import because it is the existing public fail-closed error contract;
- remove the direct import and call of `project_domain_result`.

In `_append_domain_state`, build and dispatch the neutral invocation:

```python
domain_projector = self._projector_registry.require(spec.projector)
delta = domain_projector.project(
    VerifiedInvocation(
        capability=capability,
        projector_id=spec.projector,
        result_kind=spec.result_kind,
        result=projection_result,
        arguments=_start_args(start),
        turn_id=turn_id,
        result_paths=result_paths,
        active_revision_ref=active_revision_ref,
    )
)
```

Persist the same `delta.model_dump(mode="json")` payload. Do not catch projection errors or convert them into accepted facts.

- [ ] **Step 4: Add direct profile adapter tests**

In `test_pandapower_profile.py`, create real current-run artifacts with existing test helpers and prove:

```python
references = authority.admit(capability, result, evidence_refs)
assert references.results == verifier.admit_successful_tool_references(
    capability, result, evidence_refs
).results
```

Also loop over `KNOWN_CONTEXT_PROJECTORS` and assert every ID is resolvable and no unknown ID silently falls back.

- [ ] **Step 5: Run projection, integrity, reducer and turn tests**

```bash
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/domain/test_pandapower_profile.py \
  packages/grid-agent/tests/analysis/test_projector.py \
  packages/grid-agent/tests/analysis/test_domain_projection.py \
  packages/grid-agent/tests/analysis/test_integrity.py \
  packages/grid-agent/tests/analysis/test_reducer.py \
  packages/grid-agent/tests/analysis/test_turns.py -q
```

Expected: PASS with the same projected state and integrity exceptions.

- [ ] **Step 6: Commit the adapter routing**

```bash
git add packages/grid-agent/src/grid_agent/analysis/projector.py \
  packages/grid-agent/tests/analysis/test_projector.py \
  packages/grid-agent/tests/domain/test_pandapower_profile.py
git commit -m "refactor: route projection through domain adapters"
```

---

### Task 6: Route `run` and continuous `analysis` through one profile-driven assembly path

**Files:**

- Modify: `packages/grid-agent/src/grid_agent/cli/app.py`
- Modify: `packages/grid-agent/tests/cli/test_app.py`
- Modify: `packages/grid-agent/tests/application/test_composition.py`

**Interfaces:**

- Consumes: `build_pandapower_profile(_repo_root())`, `prepare_domain_runtime(...)`, existing workspaces and Pi runtime paths.
- Produces: unchanged CLI behavior with no direct `GridctlClient`, `ContentReferenceVerifier`, `load_packaged_capability_documents` or independent guide/policy path construction in CLI orchestration.

- [ ] **Step 1: Add failing CLI composition-routing tests**

Use monkeypatches around a fake `PreparedDomainRuntime` and assert both live paths select the profile and use prepared resources. The tests must not contact a provider. At minimum add:

```python
def test_run_selects_builtin_profile_before_pi_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    selected: list[Path] = []
    monkeypatch.setattr(
        "grid_agent.cli.app.build_pandapower_profile",
        lambda root: selected.append(root) or fake_profile(root),
    )
    # Patch provider/runtime/Pi boundaries with the existing scripted fakes.

    result = CliRunner().invoke(app, ["run", "列出可用网络"])

    assert result.exit_code == 0
    assert len(selected) == 1
    assert set(json.loads(result.stdout)) == {"question_id", "answer_output"}
```

Add an `analysis`-assembly unit test around `_execute_analysis` or its existing runner fakes, and a mismatch test where `prepare_domain_runtime` raises `DomainManifestError`. Assert no `PiRpcClient.start()` call occurs and stdout still has the existing failure envelope.

- [ ] **Step 2: Run CLI tests and verify they fail on direct construction**

```bash
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/cli/test_app.py \
  packages/grid-agent/tests/application/test_composition.py -q
```

Expected: FAIL because `app.py` does not import/select a profile or call `prepare_domain_runtime`.

- [ ] **Step 3: Select the built-in profile once per command before materialization**

At the beginning of the live `run` and `_execute_analysis` paths:

```python
profile = build_pandapower_profile(_repo_root())
```

Construct/install the existing executable exactly as today, then replace the duplicated environment/catalog/guide/verifier assembly with:

```python
domain_runtime = prepare_domain_runtime(
    profile,
    executable=workspace.bin_path / profile.manifest.executable_name,
    workspace=workspace.root_path,
    tool_catalog_path=workspace.root_path / "tool-catalog.json",
    guide_index_path=workspace.root_path / "guide-index.json",
)
```

Use:

- `domain_runtime.executor` wherever `gridctl` was used;
- `domain_runtime.environment_description` for runtime records and environment metadata;
- `domain_runtime.capability_documents` for `CapabilityContextCatalog`;
- `domain_runtime.authority` for run admission and turn audit;
- `profile.projector_registry` for `AnalysisContextProjector`;
- `profile.manifest.system_policy_path` in `RuntimePaths`;
- the two prepared materialized paths for tool catalog and guide index.

- [ ] **Step 4: Generalize the one-shot event admission helper**

Change `_admit_successful_tool_references` to receive `ArtifactAuthority` rather than creating a verifier from `RunWorkspace`:

```python
def _admit_successful_tool_references(
    authority: ArtifactAuthority,
    event: Mapping[str, Any],
) -> None:
    # retain all current event filtering
    authority.admit(capability, result, tuple(evidence_refs))
```

The `on_pi_event` closure must capture `domain_runtime.authority`. Do not weaken its current success/event/ref filtering.

- [ ] **Step 5: Remove concrete core imports and route offline diagnostic execution through the profile factory**

Remove these imports from `app.py`:

```python
ContentReferenceVerifier
GridctlClient
ToolCatalog
load_packaged_capability_documents
GuideIndex
```

For offline diagnostics that require the simulator, resolve the existing executable with `GridctlLocator`, then call `profile.create_executor(executable, workspace.root_path, 60)`. Informational offline answers must still avoid creating a run workspace.

Do not alter `_install_gridctl`, `GridctlLocator`, the Pi extension path or `RuntimePaths.gridctl_dir` in Workstream A; those physical/product renames belong to Workstream B.

- [ ] **Step 6: Preserve environment keys and answer behavior**

Continuous runner environment must still expose keys `provider`, `model`, `pandapower`, and `gridctl`, with the same values. The `run` success callback must still admit refs before reporting progress. Do not add `domain_id` to stdout, answer artifacts or versioned schemas in this increment.

- [ ] **Step 7: Run CLI, runtime, analysis and scripted E2E slices**

```bash
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/cli/test_app.py \
  packages/grid-agent/tests/application/test_composition.py \
  packages/grid-agent/tests/analysis/test_runner.py \
  packages/grid-agent/tests/analysis/test_projector.py \
  packages/grid-agent/tests/e2e/test_continuous_analysis.py -q
```

Expected: PASS. CLI success stdout remains one JSON line; profile errors occur before Pi/provider requests.

- [ ] **Step 8: Verify the CLI no longer owns domain construction**

```bash
rg -n "GridctlClient|ContentReferenceVerifier|load_packaged_capability_documents|GuideIndex\.load|ToolCatalog\.from_environment" \
  packages/grid-agent/src/grid_agent/cli/app.py
```

Expected: no matches.

- [ ] **Step 9: Commit shared CLI assembly**

```bash
git add packages/grid-agent/src/grid_agent/cli/app.py \
  packages/grid-agent/tests/cli/test_app.py \
  packages/grid-agent/tests/application/test_composition.py
git commit -m "refactor: assemble grid commands from domain profile"
```

---

### Task 7: Prove the seams with a provider-free synthetic non-pandapower domain

**Files:**

- Modify: `packages/grid-agent/tests/application/test_composition.py`
- Create: `packages/grid-agent/tests/contract/test_domain_runtime_boundaries.py`

**Interfaces:**

- Consumes: public `grid_agent.domain` interfaces and `prepare_domain_runtime` only.
- Produces: conformance proof that a non-grid contract source/executor/prefix/policy/guide/authority can materialize without production pandapower shortcuts.

- [ ] **Step 1: Write the complete synthetic fixture inside tests**

Create temporary files at runtime:

```text
<tmp>/inventory/contracts/asset.list.json
<tmp>/inventory/guides/SKILL.md
<tmp>/inventory/policy.md
```

The capability document must use:

```json
{
  "id": "asset.list",
  "tool_name": "inventory_asset_list",
  "availability": "published",
  "context_effect": {
    "requires_state": [],
    "consumes_state": [],
    "produces_state": ["inventory.assets"],
    "invalidates_state": [],
    "result_kind": "inventory.asset-list",
    "projector": "inventory-list-v1"
  },
  "purpose": "List versioned inventory assets.",
  "applies_to": ["read-only inventory discovery"],
  "not_for": ["inventory mutation"],
  "input_schema": {
    "type": "object",
    "additionalProperties": false,
    "required": [],
    "properties": {}
  },
  "requires": [],
  "produces": ["versioned asset summaries"],
  "common_next": [],
  "recovery": {}
}
```

Use test-only fake registry and authority classes; do not import `grid_agent.domains.pandapower`.

- [ ] **Step 2: Add the conformance assertion**

```python
def test_synthetic_domain_materializes_through_public_seams(tmp_path: Path) -> None:
    profile, executor = inventory_profile(tmp_path)

    prepared = prepare_domain_runtime(
        profile,
        executable=tmp_path / "inventoryctl",
        workspace=tmp_path / "run",
        tool_catalog_path=tmp_path / "run/tool-catalog.json",
        guide_index_path=tmp_path / "run/guide-index.json",
    )

    payload = json.loads(prepared.tool_catalog_path.read_text(encoding="utf-8"))
    assert [tool["name"] for tool in payload["tools"]] == [
        "inventory_asset_list",
        "inventory_record_decision",
    ]
    assert executor.calls == [("environment.describe", {})]
    assert prepared.profile.manifest.domain_id == "inventory-readonly"
```

Also assert the guide index root and policy path come from the fixture Profile, not repository-relative grid paths.

- [ ] **Step 3: Add source-boundary tests using Python AST**

`test_domain_runtime_boundaries.py` must parse every `grid_agent/domain/*.py` import and fail if a neutral module imports any of:

```python
FORBIDDEN_PREFIXES = (
    "grid_agent.simulator",
    "grid_agent.domains",
    "grid_agent.analysis.domain_projection",
    "grid_agent.analysis.integrity",
)
```

It must also parse `grid_agent/application/composition.py` and assert it does not import `grid_agent.domains.pandapower`; profile selection belongs to the CLI/application entrypoint, not the generic composer.

- [ ] **Step 4: Run the conformance tests and scan for production fixture leakage**

```bash
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/application/test_composition.py \
  packages/grid-agent/tests/contract/test_domain_runtime_boundaries.py -q
rg -n "inventory-readonly|inventory_asset_list|inventory-capability" \
  packages/grid-agent/src configs skills
```

Expected: pytest PASS; `rg` produces no matches in production sources/configuration/guides.

- [ ] **Step 5: Run all grid compatibility slices once more**

```bash
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/domain \
  packages/grid-agent/tests/tools \
  packages/grid-agent/tests/simulator/test_client.py \
  packages/grid-agent/tests/analysis/test_projector.py \
  packages/grid-agent/tests/cli/test_app.py -q
```

Expected: PASS for both the synthetic seam and the unchanged built-in grid product.

- [ ] **Step 6: Commit the conformance proof**

```bash
git add packages/grid-agent/tests/application/test_composition.py \
  packages/grid-agent/tests/contract/test_domain_runtime_boundaries.py
git commit -m "test: prove provider-free domain conformance"
```

---

### Task 8: Document the implemented boundary and run repository gates

**Files:**

- Modify: `docs/architecture/pandapower-capability-composition.md`
- Modify: `docs/RUNBOOK.md`
- Modify: `docs/status/CURRENT-STATE.md`

**Interfaces:**

- Consumes: completed Workstream A code and test evidence.
- Produces: authoritative architecture/runbook/state documentation and full verification record.

- [ ] **Step 1: Update architecture documentation against the implemented symbols**

Add a “Domain runtime profile seam” section to `pandapower-capability-composition.md` containing this ownership flow:

```text
CLI selects build_pandapower_profile(repo_root)
  -> prepare_domain_runtime(profile, workspace, executable)
     -> CapabilityContractSource.load()
     -> CapabilityExecutor.invoke("environment.describe", {})
     -> ToolCatalog + GuideIndex materialization
     -> ArtifactAuthority scoped to current run
  -> Pi invokes the unchanged grid_* tools through gridctl
  -> DomainProjectorRegistry projects admitted results
```

Document explicitly:

- `grid_agent.domain` is neutral and still packaged inside `grid-agent`;
- `grid_agent.domains.pandapower` is the compatibility Domain Pack;
- generic composition never selects a default Profile;
- Workstream A is seam extraction, not independent package or multi-domain completion;
- `GridctlClient`, current evidence verifier and projection functions remain simulator/grid implementations behind adapters.

- [ ] **Step 2: Update operator documentation without changing commands**

In `docs/RUNBOOK.md`, add a short troubleshooting subsection mapping startup failures to:

- invalid Profile/manifest;
- protocol mismatch from `environment.describe`;
- missing capability contract root;
- missing guide or system policy resource;
- existing gridctl transport and evidence-integrity errors.

State that these failures retain the current stderr/error-envelope behavior and occur before model execution where applicable. Do not add a domain-selection command that does not exist.

- [ ] **Step 3: Update structural project state**

In `docs/status/CURRENT-STATE.md`, record only verified facts:

- Workstream A completed or remains incomplete according to actual gate results;
- built-in Profile path and neutral module paths;
- unchanged protocol/tool/evidence/CLI contracts;
- deferred Workstreams B–E.

Do not manually rewrite `docs/status/JOURNAL.md` or `RESUME-NEXT-SESSION.md` as part of the feature commit; use the repository project-state workflow after the commit if its hook requests a journal entry.

- [ ] **Step 4: Verify documentation links, symlink and whitespace**

```bash
test -L CLAUDE.md
test "$(readlink CLAUDE.md)" = "AGENTS.md"
git diff --check
rg -n "DomainRuntimeProfile|prepare_domain_runtime|Workstream A" \
  docs/architecture/pandapower-capability-composition.md \
  docs/RUNBOOK.md \
  docs/status/CURRENT-STATE.md
```

Expected: symlink checks exit 0, no whitespace errors, and each symbol is documented where intended.

- [ ] **Step 5: Run the supported repository gates in order**

```bash
make doctor
make test
make test-e2e
make validate
```

Expected: all commands exit 0. Do not substitute provider-backed validation for these deterministic gates.

- [ ] **Step 6: Run final compatibility and boundary scans**

```bash
rg -n "GridctlClient|ContentReferenceVerifier|load_packaged_capability_documents|GuideIndex\.load|ToolCatalog\.from_environment" \
  packages/grid-agent/src/grid_agent/cli/app.py
rg -n "grid_agent\.(simulator|domains|analysis\.domain_projection|analysis\.integrity)" \
  packages/grid-agent/src/grid_agent/domain
git status --short
```

Expected: first two commands have no matches; status lists only task-owned documentation/source/test changes plus any pre-existing user-owned status files.

- [ ] **Step 7: Commit documentation separately**

```bash
git add docs/architecture/pandapower-capability-composition.md \
  docs/RUNBOOK.md \
  docs/status/CURRENT-STATE.md
git commit -m "docs: describe domain runtime profile boundary"
```

- [ ] **Step 8: Perform completion review before claiming Workstream A complete**

Compare the final diff to all eight success criteria in the approved design. Completion requires concrete evidence for each:

1. one built-in Profile supplies metadata, contracts, executor, projector registry, authority, policy and guides;
2. CLI no longer owns repository-relative contract/guide/policy construction;
3. orchestration type-depends on executor/authority protocols;
4. characterization and E2E tests prove grid compatibility;
5. synthetic non-pandapower fixture passes through neutral seams;
6. fixture adds no production shortcut or generic special case;
7. focused tests and four supported gates pass;
8. no provider-backed validation was required or run.

If any item lacks test or command evidence, leave Workstream A marked incomplete and add the missing focused test before handoff.

---

## Plan Self-Review Checklist

- [ ] Every approved Workstream A task maps to one numbered task above.
- [ ] Every production edit has a preceding failing test or characterization baseline.
- [ ] Every new interface states its consumer and producer.
- [ ] No step moves distributions, renames public grid contracts or adds a production second domain.
- [ ] An incomplete-work marker scan over executable instructions and code snippets returns no matches.
- [ ] `VerifiedInvocation`, `DomainProjector`, `ArtifactAuthority`, `DomainRuntimeProfile` and `PreparedDomainRuntime` signatures are consistent across tasks.
- [ ] Existing user-owned status changes are not staged by feature commits.
- [ ] Final verification includes focused tests, repository gates, boundary scans and the stdout/evidence invariants.
