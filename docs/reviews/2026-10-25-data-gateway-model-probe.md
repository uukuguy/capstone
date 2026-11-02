# Data gateway model delivery: Capstone-side client probe

Date: 2026-10-25. Scope: north only, two formats. Passed topology delivery.
This is an independent MCP client check, not Capstone task integration.

## Method

Read the gateway's model service guide and acceptance record. Used the gateway's
existing validate_network_models.py with the operator connection file, HTTP
transport, --scopes north, --timeout 180 and Capstone-owned output storage.
The command did not print credentials or pass them in CLI arguments.

The client initialized the real MCP connection, discovered tools, requested both
topology formats, polled completion, downloaded base64 chunks through MCP and
checked the full ZIP size and SHA256. It loaded each native model using its SDK,
checked counts and disabled equipment, and tested strict power-flow refusal.
It did not access the server's artifact directory or share model files with it.
The check ran on the same physical host; another-machine access was not tested.

## Results

| Format | Received bytes | Measured seconds | Nodes | Lines | Full hash | SDK load |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| pandapower JSON | 4,795,992 | 1.704 | 14,017 | 878 | passed | passed |
| PyPSA NetCDF | 5,158,331 | 1.733 | 14,017 | 878 | passed | passed |

These durations include the observed build/cache and client path; they are not
fresh-build performance claims. The figures describe the selected source-node
topology, not in-service assets or electrically reduced buses.

Both artifacts declare power_flow_ready=false. A purpose=power_flow request
failed with model_not_calculation_ready, as required. No electrical calculation
was attempted. The SDKs accepted the current formats; compatibility with
Capstone's separately pinned simulator versions is not verified by this probe.

The current gateway documentation states that electrical parameters, trusted
switch positions and consistent injections remain incomplete. An importable
model file does not resolve those gaps.

## Receipts and next scope

Ignored ROOT receipts:
- outputs/data-gateway-20261025/discovery.json
- outputs/data-gateway-20261025/network-models/report.json

Operator log: /tmp/capstone-gateway-model-probe.log. Process exit code: 0.
No sibling-project source, configuration, deployment or backend selection changed.
Gateway build calls can populate its ordinary model-job cache through MCP.

Later work must verify Capstone autonomous download, versioned registration,
Authority admission and pinned SDK compatibility. First delivery remains
enterprise-research data exploration and retrieval through MCP.
