import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import render_project_overview as renderer


class LiveSnapshotTests(unittest.TestCase):
    def invoke(self, root, data):
        with patch.object(renderer, 'ROOT', root), patch.object(renderer, 'snapshot', return_value=data), \
                patch('sys.argv', ['render_project_overview.py', '--live', '--no-probe']), \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                renderer.main()
            except SystemExit as error:
                self.fail(f'--live must be accepted by the renderer (exit {error.code})')

    def test_live_mode_preserves_tracked_snapshot_and_escapes_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html = root / 'docs/status/PROJECT-OVERVIEW.html'
            html.parent.mkdir(parents=True)
            html.write_bytes(b'committed offline snapshot')
            data = {'schema': 'capstone-project-overview/1', 'generated_at': 200,
                    'nodes': [], 'edges': [], 'text': '</script>& evidence'}
            self.invoke(root, data)
            target = root / 'runs/project-overview/live-state.js'
            source = target.read_text()
            prefix = 'window.CAPSTONE_PROJECT_OVERVIEW_LIVE='
            self.assertTrue(source.startswith(prefix))
            self.assertEqual(json.loads(source[len(prefix):].rstrip(';\n')), data)
            self.assertNotIn('</script>', source)
            self.assertNotIn('&', source)
            self.assertEqual(html.read_bytes(), b'committed offline snapshot')
            self.assertEqual(list(target.parent.iterdir()), [target])

    def test_failed_atomic_replace_preserves_previous_live_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'runs/project-overview/live-state.js'
            target.parent.mkdir(parents=True)
            target.write_bytes(b'previous complete state')
            with patch.object(Path, 'replace', side_effect=OSError('replace failed')):
                with self.assertRaises(OSError):
                    self.invoke(root, {'generated_at': 200})
            self.assertEqual(target.read_bytes(), b'previous complete state')
            self.assertEqual(list(target.parent.iterdir()), [target])


if __name__ == '__main__':
    unittest.main()
