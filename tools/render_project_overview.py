"""Refresh the standalone product-package view from the canonical register."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
from urllib.request import urlopen
from urllib.parse import urljoin, urlsplit


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "tools/project_overview"


def relative_node_links(text: str) -> list[dict[str, str]]:
    links = []
    for label, href in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text):
        if not href.startswith(("../", "./")) or not re.fullmatch(r"[A-Za-z0-9._/-]+", href):
            continue
        target = (ROOT / "docs/status" / href).resolve()
        if not target.is_relative_to(ROOT):
            continue
        parts = target.relative_to(ROOT).parts
        if (not parts or parts[0] not in {"docs", "runs"}
                or any(part.startswith(".") for part in parts)
                or not href.endswith((".md", ".tar.gz", ".sha256"))):
            continue
        links.append(dict(label=label, href=href))
    return links


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True,
                                   stderr=subprocess.DEVNULL, timeout=10).strip()


def table(document: str, heading: str) -> list[list[str]]:
    match = re.search(r"^## " + re.escape(heading) + r"\s*$", document, re.M)
    if match is None:
        raise ValueError("Missing register section: " + heading)
    section = document[match.end():].split("\n## ", 1)[0]
    rows = [line.strip().strip("|").split("|") for line in section.splitlines()
            if line.startswith("|")]
    return [[cell.strip() for cell in row] for row in rows[2:]]


def plain(value: str) -> str:
    value = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", value)
    return value.replace("`", "")


def bind_user_local_trials(document: str, nodes: list[dict]) -> None:
    """Bind optional self-install records to exact registered Git sources."""
    heading = "用户自安装试用版本"
    for node in nodes:
        node["trial"] = None
    if not re.search(r"^## " + re.escape(heading) + r"\s*$", document, re.M):
        return
    section = re.split(r"^## " + re.escape(heading) + r"\s*$", document, maxsplit=1,
                       flags=re.M)[1].split("\n## ", 1)[0]
    header = next((line for line in section.splitlines() if line.startswith("|")), "")
    if [cell.strip() for cell in header.strip().strip("|").split("|")] != [
        "ID", "精确Git提交", "版本", "发布地址", "安装命令", "验收状态"
    ]:
        raise ValueError("Invalid user-local trial table columns")
    by_id = {node["id"]: node for node in nodes}
    seen = set()
    for row in table(document, heading):
        if len(row) != 6:
            raise ValueError("Invalid user-local trial row")
        identity, sha, version, release_url, command, status = map(plain, row)
        if identity not in by_id or identity in seen:
            raise ValueError("Unknown or duplicate user-local Git node: " + identity)
        seen.add(identity)
        if not re.fullmatch(r"[a-f0-9]{40}", sha) or sha != by_id[identity]["sha"]:
            raise ValueError("User-local source does not match Git node: " + identity)
        match = re.fullmatch(r"user-local-([a-f0-9]{7,40})", version)
        if match is None or not sha.startswith(match[1]):
            raise ValueError("User-local version does not match source: " + identity)
        if release_url != "https://github.com/uukuguy/capstone/releases/tag/" + version:
            raise ValueError("Unsafe or mismatched user-local release URL: " + identity)
        by_id[identity]["trial"] = dict(sha=sha, version=version, release_url=release_url,
                                       command=command, status=status,
                                       installable=status == "已验证可安装")


def snapshot(probe_local: bool, probe_cloud: bool = False) -> dict:
    register = (ROOT / "docs/status/VERSION-CONTROL.md").read_text()
    packages = []
    for row in table(register, "功能包前沿"):
        if len(row) != 10:
            raise ValueError("Invalid package row")
        identity, name, phase, status, scope, branch, next_step, previous, changes, record = map(plain, row)
        source = None
        if branch not in {"—", "线上部署"}:
            try:
                source = git("rev-parse", branch + "^{commit}")
            except subprocess.CalledProcessError:
                pass
        packages.append(dict(id=identity, name=name, phase=int(phase), status=status,
                             scope=scope, branch=branch, source=source, next=next_step,
                             previous=previous, changes=changes.split("；"), record=record))
    environments = []
    for row in table(register, "环境台账"):
        if len(row) != 4:
            raise ValueError("Invalid environment row")
        role_revisions = re.findall(r"`([a-f0-9]{7,40})`", row[1])
        coherent = len({git("rev-parse", value + "^{commit}") for value in role_revisions}) <= 1
        name, source_text, state, detail = map(plain, row)
        revision = re.search(r"\b[a-f0-9]{7,40}\b", source_text)
        stage = dict(name=name, revision=revision.group() if revision else "未记录",
                     source=source_text, state=state, detail=detail,
                     observed=False, origin=None, coherent=coherent, app_revision=None)
        public_url = re.search(r"https://[a-z0-9.-]+/", detail)
        if public_url:
            stage["origin"] = public_url.group()
        if probe_cloud and name in {"cloud-dev", "cloud-demo"} and stage["origin"]:
            try:
                with urlopen(stage["origin"], timeout=8) as response:
                    html = response.read(100000).decode()
                revisions = set()
                for asset in re.findall(r'<script[^>]+src="([^"]+)"', html):
                    address = urljoin(stage["origin"], asset)
                    if urlsplit(address).netloc != urlsplit(stage["origin"]).netloc:
                        continue
                    with urlopen(address, timeout=8) as response:
                        script = response.read(4000000).decode()
                    revisions.update(re.findall(r"revision\s*:\s*[\"'\x60]([a-f0-9]{40})[\"'\x60]", script))
                if len(revisions) == 1:
                    app_revision = revisions.pop()
                    stage.update(app_revision=app_revision, observed=True)
                    if coherent:
                        stage["revision"] = app_revision
            except (OSError, ValueError):
                pass
        if name in {"local-dev", "local-demo"}:
            stage["origin"] = "http://127.0.0.1:" + ("5173/" if name == "local-dev" else "15173/")
            if probe_local:
                try:
                    with urlopen(stage["origin"] + "__capstone-build", timeout=3) as response:
                        build = json.loads(response.read(8192))
                    if (re.fullmatch(r"[a-f0-9]{40}", build.get("revision", ""))
                            and build.get("environment") == name):
                        stage.update(app_revision=build["revision"], version=build.get("version"),
                                     observed=True, dirty=build.get("dirty"))
                        if coherent:
                            stage["revision"] = build["revision"]
                except (OSError, ValueError):
                    pass  # A stopped local service leaves a clearly labelled recorded version.
        environments.append(stage)
    if {stage["name"] for stage in environments} != {"local-dev", "local-demo", "cloud-dev", "cloud-demo"}:
        raise ValueError("Expected four registered environments")
    main = git("rev-parse", "refs/heads/main")
    live = next(package for package in packages if package["id"] == "live")
    live["source"] = next(stage["revision"] for stage in environments if stage["name"] == "cloud-demo")
    nodes = []
    for row in table(register, "全景关键提交"):
        if len(row) != 7:
            raise ValueError("Invalid key commit row")
        identity, revision, lane, title, status, changes, package = map(plain, row)
        sha = git("rev-parse", revision + "^{commit}")
        links = relative_node_links(row[5])
        nodes.append(dict(id=identity, sha=sha, lane="main" if lane == "release" else lane,
                          release_point=lane == "release", title=title,
                          status=status, changes=changes, package=package, links=links,
                          tags=git("tag", "--points-at", sha).splitlines()))
    bind_user_local_trials(register, nodes)
    for stage in environments:
        if not any(node["sha"].startswith(stage["revision"]) for node in nodes):
            raise ValueError("Deployment source missing from key commits: " + stage["name"])
    presentations = {}
    for row in table(register, "Git节点展示规范"):
        if len(row) != 5:
            raise ValueError("Invalid Git node presentation row")
        identity, role, branch, summary, status = map(plain, row)
        if identity in presentations or identity not in {node["id"] for node in nodes}:
            raise ValueError("Unknown or duplicate Git node presentation: " + identity)
        changes = summary.split("；")
        if len(changes) != 2 or not all(changes):
            raise ValueError("Expected two Git node change summaries: " + identity)
        presentations[identity] = dict(role=role, branch=branch, changes=changes, status=status)
    for node in nodes:
        node["presentation"] = presentations.get(node["id"])
    for stage in environments:
        source = next(node for node in nodes if node["sha"].startswith(stage["revision"]))
        if source["presentation"] is None:
            raise ValueError("Deployment source presentation missing: " + stage["name"])
    environment_pairs = []
    for local, cloud, purpose in [
        ("local-dev", "cloud-dev", "开发测试 / 集成 / 开发版发布验证"),
        ("local-demo", "cloud-demo", "线上复现 / 紧急修复 / 用户版发布验证"),
    ]:
        local_stage = next(s for s in environments if s["name"] == local)
        cloud_stage = next(s for s in environments if s["name"] == cloud)
        coherent = local_stage["coherent"] and cloud_stage["coherent"]
        aligned = coherent and (local_stage["revision"].startswith(cloud_stage["revision"])
                                or cloud_stage["revision"].startswith(local_stage["revision"]))
        environment_pairs.append(dict(local=local, cloud=cloud, purpose=purpose,
                                      aligned=aligned,
                                      state="角色升级中，来源未对齐" if not coherent else "来源一致" if aligned else
                                      "来源不同，按发布计划对齐"))
    def ancestor(a, b):
        return subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor",
                               a, b], check=False).returncode == 0
    dev = git("rev-parse", "refs/remotes/origin/dev")
    for node in nodes:
        if (node["lane"] == "feature" and node["package"] == "autonomous"
                and ancestor(node["sha"], dev)):
            node["lane"] = "main"
    relations = {(a["id"], b["id"]) for a in nodes for b in nodes
                 if a["sha"] != b["sha"] and ancestor(a["sha"], b["sha"])}
    edges = sorted((a, b) for a, b in relations
                   if not any((a, c) in relations and (c, b) in relations
                              for c in (n["id"] for n in nodes)))
    # A merge's first-parent spine must remain visible even when its feature
    # parent also descends from the previous mainline node.
    by_sha = {node["sha"]: node for node in nodes if node.get("presentation")}
    for node in nodes:
        if node["lane"] != "main" or node["release_point"] or not node.get("presentation"):
            continue
        for sha in git("rev-list", "--first-parent", node["sha"]).splitlines()[1:]:
            parent = by_sha.get(sha)
            if parent and parent["lane"] == "main" and not parent["release_point"]:
                intermediate = any(
                    other["lane"] == "main" and not other["release_point"]
                    and (parent["id"], other["id"]) in relations
                    and (other["id"], node["id"]) in relations
                    for other in by_sha.values()
                )
                if not intermediate:
                    edges.append((parent["id"], node["id"]))
                break
    edges = sorted(set(edges))
    proposals = [dict(title=plain(row[0]), gap=plain(row[1]), record=plain(row[2]))
                 for row in table(register, "提出但未实施")]
    package_details = []
    for row in table(register, "开发包明细"):
        if len(row) != 6:
            raise ValueError("Invalid package detail row")
        package, item, status, existing, remaining, acceptance = map(plain, row)
        if package not in {p["id"] for p in packages}:
            raise ValueError("Unknown detail package: " + package)
        package_details.append(dict(package=package, item=item, status=status,
                                    existing=existing, remaining=remaining,
                                    acceptance=acceptance))
    prs = [dict(number=int(plain(row[0])), package=plain(row[1]), branch=plain(row[2]),
                target=plain(row[3]), state=plain(row[4]), scope=plain(row[5]))
           for row in table(register, "PR 交付关联")]
    work = []
    dirty_by_branch = {}
    for block in git("worktree", "list", "--porcelain").split("\n\n"):
        fields = dict(line.split(" ", 1) for line in block.splitlines() if " " in line)
        path, branch = fields.get("worktree"), fields.get("branch", "").removeprefix("refs/heads/")
        if path and branch:
            dirty = subprocess.check_output(["git", "-C", path, "status", "--porcelain"],
                                            text=True).splitlines()
            dirty_by_branch[branch] = len(dirty)
            if dirty:
                work.append(dict(branch=branch, sha=git("rev-parse", branch),
                                 paths=dirty, count=len(dirty)))
    branch_rows = {plain(row[0]): row for row in table(register, "全部分支进展")}
    branches = []
    heads = git("for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()
    for branch in sorted(heads, key=lambda name: (name != "main", name.startswith("archive/"), name)):
        row = branch_rows.get(branch)
        branches.append(dict(name=branch, sha=git("rev-parse", branch),
                             status=plain(row[1]) if row else "待登记",
                             progress=plain(row[2]) if row else "未分类的实际 Git 分支",
                             next=plain(row[3]) if row else "补充工作包与验收状态",
                             package=plain(row[4]) if row else None,
                             dirty=dirty_by_branch.get(branch, 0)))
    return dict(schema="capstone-project-overview/1", updated=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
                main=main, packages=packages, environments=environments,
                nodes=nodes, edges=edges, proposals=proposals, uncommitted=work,
                package_details=package_details,
                discussion=[dict(zip(("id", "kind", "status", "title", "description"), map(plain, row)))
                            for row in table(register, "自主智能体演进讨论")],
                environment_pairs=environment_pairs,
                development_lines=[dict(zip(("branch", "role", "status", "next"), map(plain, row)))
                                   for row in table(register, "三线研发组织")],
                branches=branches,
                prs=prs,
                register="docs/status/VERSION-CONTROL.md",
                workflow="功能/实验整理 → dev → 发布候选验证 → main → 精确标签部署",
                hotfix_branches=git("branch", "--list", "hotfix/*", "--format=%(refname:short)").splitlines())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-probe", action="store_true", help="Use recorded local versions without localhost reads")
    parser.add_argument("--probe-cloud", action="store_true", help="Read public cloud App build identities; no Provider or backend execution")
    args = parser.parse_args()
    data = snapshot(not args.no_probe, args.probe_cloud)
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
    template = (ASSETS / "template.html").read_text()
    css = (ASSETS / "tailwind.css").read_text()
    if template.count("__PROJECT_DATA__") != 1 or template.count("__TAILWIND_CSS__") != 1:
        raise ValueError("Invalid standalone template")
    output = template.replace("__PROJECT_DATA__", payload).replace("__TAILWIND_CSS__", css)
    target = ROOT / "docs/status/PROJECT-OVERVIEW.html"
    target.write_text(output)
    print("Project overview refreshed: " + str(target.relative_to(ROOT)))


if __name__ == "__main__":
    main()
