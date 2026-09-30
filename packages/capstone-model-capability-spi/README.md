# Model Capability Profile SPI

This separately installable package contains four contracts:

- `ModelCapabilityDescriptor`: exact profile identity, version, and SPI version.
- `ModelCapabilitySelection`: ordered exact profile references, including an empty set.
- `ModelCapabilityFactory`: creates a new context-owned handle.
- `ModelCapabilityRegistry`: source-approved registration followed by explicit sealing.

The package has no runtime dependencies. Model catalogs, implementation-family
eligibility, display labels, tools, Authority admission, credentials, and Pi/DSH
execution belong to the Capstone host and selected adapters.

## Bootstrap and context preparation

```python
from capstone_model_capability_spi import (
    ModelCapabilityDescriptor, ModelCapabilityRegistry, ModelCapabilitySelection,
)

descriptor = ModelCapabilityDescriptor("static-analysis", "1.0.0")

class Handle:
    def __init__(self):
        self.descriptor = descriptor

    def close(self):
        pass  # A real implementation releases its own context resources idempotently.

registry = ModelCapabilityRegistry()
registry.register(descriptor, Handle, trust_source="approved-source-manifest")
registry.seal()
handles = registry.resolve_selection(ModelCapabilitySelection((descriptor.reference,)))
try:
    # The trusted Capstone adapter prepares contributions using host-supplied
    # model/revision, policy, and scoped Authority clients.
    handle = handles[0]
finally:
    for handle in reversed(handles):
        handle.close()
```

Each factory must return a fresh handle and clean up its own partial allocation
if it raises before returning. A handle implements `descriptor` and idempotent
`close()`; implementation-private state remains private to its trusted adapter.
Handles are never serialized into Thread history. The Context owner releases
successful handles on retirement or Run close.

Resolution never chooses a latest version, substitutes a missing profile,
imports plugins, or infers semantic overlap. A whole selection is checked before
any factory runs. Factory or descriptor validation failure closes returned handles
in reverse order; every close is attempted even when another close fails.
Preparation and cleanup failures are retained together in an exception group.
Development tests may resolve an unsealed isolated registry; deployed bootstrap
must seal before publishing it to workers.

## Verification

```sh
make test-model-capability-spi
python tools/check_package_boundaries.py
```
