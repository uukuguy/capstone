"""UTF-8 document inputs shared by admission, projection and native launch.

These types are read-only task data. A text type grants no execution rights.
"""

MAX_MATERIAL_BYTES = 8 * 1024 * 1024
# Four uploaded inputs plus four explicitly selected historical products.
MAX_NATIVE_MATERIALS = 8
MAX_NATIVE_CONTEXT_BYTES = 12 * 1024 * 1024
MAX_NATIVE_TASK_BYTES = 16 * 1024 * 1024

TEXT_DOCUMENT_TYPES = {'.txt': 'text/plain', '.md': 'text/markdown', '.csv': 'text/csv',
    '.html': 'text/html', '.htm': 'text/html', '.svg': 'image/svg+xml', '.json': 'application/json'}
