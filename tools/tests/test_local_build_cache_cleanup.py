"""No Docker calls: exercise the destructive-operation selection boundary."""
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest
import tempfile
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "cache_cleanup", ROOT / "deploy/cleanup_local_build_cache.py"
)
cleanup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cleanup)


def image(n, *, project="capstone", tags=None, digests=None):
    return {"Id": "sha256:" + str(n) * 64, "RepoTags": tags or [],
            "RepoDigests": digests or [],
            "Config": {"Labels": {"com.docker.compose.project": project}}}


def record(name, description="generic", parents=(), **extra):
    return {"ID": name * 24, "Description": description,
            "Parents": [p * 24 for p in parents], "Reclaimable": True,
            "Shared": False, **extra}


class SelectionTests(unittest.TestCase):
    def test_images_preserve_all_container_refs_tags_digests_and_other_projects(self):
        images = [image(1), image(2), image(3, tags=["kept:local"]),
                  image(4, project="other"), image(5, digests=["kept@sha256:x"]),
                  image(6, project="capstone-demo"), image(7, project=None)]
        # Stopped and running containers use the same immutable Image field.
        containers = [{"Image": images[1]["Id"], "State": {"Running": False}}]
        self.assertEqual(cleanup.select_images(images, containers), [images[0]["Id"]])

    def test_only_direct_strong_seeds_not_ancestors_or_unproven_descendants(self):
        records = [record("a", "RUN apt-get update"),
                   record("b", "WORKDIR /opt/general", ("a",)),
                   record("c", "COPY packages/capstone-agent/src/ /app/", ("b",)),
                   record("d", "COPY packages/unrelated/ /app/", ("c",)),
                   record("e", "COPY packages/unrelated/ /app/", ("b",)),
                   record("f", "from local "), record("g", "COPY . /app")]
        self.assertEqual(cleanup.select_cache(records), ["c" * 24])

    def test_shared_inuse_and_unknown_reclaimability_are_never_deleted(self):
        records = [record("a", "COPY capstone_agent/a.py /app/", Shared=True),
                   record("b", "RUN capstone-report --help", Reclaimable=False),
                   record("c", "COPY packages/capstone-agent/ /app/")]
        del records[2]["Reclaimable"]
        self.assertEqual(cleanup.select_cache(records), [])

    def test_duplicate_and_unsafe_ids_fail_closed(self):
        with self.assertRaises(ValueError):
            cleanup.select_cache([record("a"), record("a", "changed")])
        bad = record("a", "COPY capstone_agent/a.py /app/")
        bad["ID"] = "a.*|other"
        with self.assertRaises(ValueError):
            cleanup.select_cache([bad])

    def test_exact_id_filter_is_single_anchored_or_and_verified_before_use(self):
        ids = ["a" * 24, "b" * 24]
        selector = cleanup.cache_filter(ids)
        self.assertEqual(selector, "id~=^(" + "|".join(ids) + ")$")
        cleanup.verify_filter_result(ids, [record("a")])
        with self.assertRaises(ValueError):
            cleanup.verify_filter_result(ids, [record("c")])
        with self.assertRaises(ValueError):
            cleanup.cache_filter([])

    def test_json_lines_and_json_array_supported_but_not_partial_bad_output(self):
        self.assertEqual(cleanup.json_records('{"ID":"a"}\n{"ID":"b"}\n'),
                         [{"ID": "a"}, {"ID": "b"}])
        self.assertEqual(cleanup.json_records('[{"ID":"a"}]'), [{"ID": "a"}])
        with self.assertRaises(ValueError):
            cleanup.json_records('{"ID":"a"}\nnot json')

    def test_budget_cannot_expand_scope_or_remove_reserve(self):
        args = cleanup.parse_args([])
        self.assertFalse(args.apply)
        self.assertEqual((args.max_used_space, args.reserved_space), ("40GB", "20GB"))
        with self.assertRaises(ValueError):
            cleanup.check_budgets("10GB", "20GB")
        with self.assertRaises(ValueError):
            cleanup.check_budgets("40GB", "0GB")

    def test_dry_run_never_issues_a_mutating_command(self):
        with patch.object(cleanup, "image_inventory", return_value=([image(1)], [])), \
             patch.object(cleanup, "cache_inventory", return_value=[
                 record("a", "COPY capstone_agent/a.py /app/")]), \
             patch.object(cleanup, "run") as run:
            cleanup.maintain(cleanup.parse_args(["--builder", "orbstack"]))
        run.assert_not_called()

    def test_default_builder_uses_supported_json_list_and_exact_current_entry(self):
        builders = '{"Name":"other","Current":false}\n{"Name":"orbstack","Current":true}\n'
        with patch.object(cleanup, "image_inventory", return_value=([], [])), \
             patch.object(cleanup, "cache_inventory", return_value=[]), \
             patch.object(cleanup, "run", return_value=builders) as run:
            result = cleanup.maintain(cleanup.parse_args([]))
        self.assertEqual(result["builder"], "orbstack")
        run.assert_called_once_with(["docker", "buildx", "ls", "--format=json"])

    def test_missing_or_ambiguous_current_builder_refuses_cleanup(self):
        for builders in ['[]', '[{"Name":"a","Current":true},{"Name":"b","Current":true}]']:
            with self.subTest(builders=builders), patch.object(cleanup, "run", return_value=builders):
                with self.assertRaises(ValueError):
                    cleanup.maintain(cleanup.parse_args([]))

    def test_inventory_includes_intermediate_untagged_images(self):
        with patch.object(cleanup, "run", return_value="") as run:
            cleanup.image_inventory()
        command = run.call_args_list[0].args[0]
        self.assertEqual(command[:3], ["docker", "image", "ls"])
        self.assertIn("--all", command)
        self.assertIn("label=com.docker.compose.project=capstone", command)

    def test_image_removal_never_implicitly_prunes_unselected_parents(self):
        with patch.object(cleanup, "image_inventory", return_value=([image(1)], [])), \
             patch.object(cleanup, "cache_inventory", return_value=[]), \
             patch.object(cleanup, "run", return_value="") as run:
            cleanup.maintain(cleanup.parse_args(["--builder", "orbstack", "--apply"]))
        self.assertEqual(run.call_args.args[0],
                         ["docker", "image", "rm", "--no-prune", image(1)["Id"]])

    def test_apply_rechecks_container_refs_and_only_prunes_exact_verified_ids(self):
        candidate = record("a", "COPY capstone_agent/a.py /app/")
        with patch.object(cleanup, "image_inventory", side_effect=[
                ([image(1)], []), ([image(1)], [{"Image": image(1)["Id"]}])]), \
             patch.object(cleanup, "cache_inventory", return_value=[candidate]), \
             patch.object(cleanup, "run", return_value="") as run:
            cleanup.maintain(cleanup.parse_args(["--builder", "orbstack", "--apply"]))
        self.assertEqual(run.call_count, 1)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["docker", "buildx", "prune"])
        self.assertIn(cleanup.cache_filter(["a" * 24]), command)
        self.assertIn("inuse=false", command)
        self.assertIn("shared=false", command)
        self.assertNotIn("--all", command)

    def test_misbehaving_buildx_filter_aborts_before_any_prune(self):
        candidate = record("a", "COPY capstone_agent/a.py /app/")
        with patch.object(cleanup, "image_inventory", return_value=([], [])), \
             patch.object(cleanup, "cache_inventory", side_effect=[
                 [candidate], [candidate], [record("b")]]), \
             patch.object(cleanup, "run") as run:
            with self.assertRaises(ValueError):
                cleanup.maintain(cleanup.parse_args(["--builder", "orbstack", "--apply"]))
        run.assert_not_called()

    def test_second_helper_does_not_wait_or_overlap_first(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "maintenance.lock"
            with cleanup.maintenance_lock(path) as first:
                self.assertTrue(first)
                with cleanup.maintenance_lock(path) as second:
                    self.assertFalse(second)
            with cleanup.maintenance_lock(path) as later:
                self.assertTrue(later)

    def run_posthealthy_hook(self, directory, enabled):
        root = Path(directory)
        fake_bin = root / "bin"
        fake_bin.mkdir()
        fake_python = fake_bin / "python3"
        fake_python.write_text('#!/bin/sh\nprintf called > "$CAPSTONE_TEST_MARKER"\nexit 19\n')
        fake_python.chmod(0o755)
        source = (ROOT / "deploy/rebuild_local.sh").read_text()
        hook = source[source.index("# Run only after readiness/identity/App checks."):]
        return subprocess.run(
            ["bash", "-c", 'set -Eeuo pipefail\nrepo_root="$CAPSTONE_TEST_REPO"\n' + hook],
            text=True, capture_output=True, env=os.environ | {
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                "CAPSTONE_TEST_REPO": str(root),
                "CAPSTONE_TEST_MARKER": str(root / "called"),
                "CAPSTONE_LOCAL_CACHE_CLEANUP": enabled,
            })

    def test_posthealthy_failure_warns_and_preserves_success(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_posthealthy_hook(directory, "1")
            self.assertEqual(result.returncode, 0)
            self.assertIn("WARNING", result.stderr)
            self.assertIn("deployment remains healthy", result.stderr)
            self.assertTrue((Path(directory) / "called").exists())

    def test_explicit_skip_never_invokes_a_second_maintenance(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_posthealthy_hook(directory, "0")
            self.assertEqual(result.returncode, 0)
            self.assertIn("skipped", result.stdout)
            self.assertFalse((Path(directory) / "called").exists())


if __name__ == "__main__":
    unittest.main()
