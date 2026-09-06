# Check price, availability and available credit

Run these read-only queries from the repository root after privately configuring
`.env`. They neither rent a GPU nor require MCP. The independent live handoff
trial exposed these details on September 6, 2026; recheck the official contracts
when fields change.

## GPU quote and stock

This example selects the exact GPU used in the recorded reference production.
Check the returned stock and price today; another GPU needs its exact catalog ID
and the hardware requirements in `runpod-runbook.md`.

```python
import json
from urllib.parse import quote, urlencode
from director.credentials import value
from director.runpod import RunPod

client = RunPod(value("RUNPOD_API_KEY"))
gpu_id = "NVIDIA RTX PRO 6000 Blackwell Server Edition MIG 2g.48gb"
filters = urlencode({"include": "AVAILABILITY", "product": "POD",
                     "cloud": "SECURE", "count": 1, "minCudaVersion": "13.0"})
gpu = client.http.request("GET", "/catalog/gpus/" + quote(gpu_id, safe="") + "?" + filters)
print(json.dumps({key: gpu.get(key) for key in
                  ("id", "memory", "price", "availability", "dataCenters", "cudaVersions")}, indent=2))
```

Use `price.secure` for this Secure Cloud request. `availability` and
`dataCenters[].availability` must show stock; missing availability is unknown.
Catalog `memory` is GPU VRAM in GB; the allocated pod's `gpu.memory` is system
RAM in GB. The trial returned 48 and 125 respectively. Verify both requirements
with the remote hardware check rather than treating those fields as equivalent.
Requesting `/catalog/gpus` without the expansion omits availability. To discover
other GPUs, use that list endpoint with the same filters and inspect its `gpus`
array. The catalog is a quote, not a reservation: check the allocated pod's
`cost` and actual hardware before installation. Stop if the allocation falls
outside the authorized budget or requirements.

## Account balance

REST v2 `/billing` returns historical spending. It has no balance field in the
checked contract. Use this minimal query from the official
[GraphQL specification](https://graphql-spec.runpod.io/#query-myself):

```python
import json
from director.common import DirectorError
from director.credentials import value
from director.http import HTTP

api = HTTP("https://api.runpod.io", value("RUNPOD_API_KEY"))
result = api.request("POST", "/graphql", {
    "query": "query { myself { clientBalance currentSpendPerHr } }"
})
account = (result.get("data") or {}).get("myself")
if result.get("errors") or not account or not isinstance(account.get("clientBalance"), (int, float)):
    raise DirectorError("Account balance could not be verified; check it in the RunPod console.")
print(json.dumps(account, indent=2))
```

This HTTP POST executes a read-only GraphQL **query**. It requests only available
credit and the account's current hourly spend; keep this account output in
private session records. The credential stays in an Authorization header and
is never printed. A scoped key may allow Pods but deny GraphQL; in that case
confirm balance in the console rather than inferring it from a successful GET.
Account-wide spend and balance changes can include pre-existing storage or other
work. Attribute this session's cost to its owned pod.

Record the current quote, storage allowance, total authorized budget, start
time and shutdown deadline before creation. Available credit alone is not
spending authorization. Reserve time and money for downloading outputs and
verified cleanup, and launch the watchdog described in the runbook.

## Inspect the contract and reconcile spending

The [current OpenAPI schema](https://api.runpod.io/v2/openapi.json) uses paths such
as `/v2/catalog/gpus`; the repository client's base already includes `/v2`, so
its relative paths start at `/catalog/gpus`. Plain `urllib.request.urlopen`
received HTTP 403 during the trial. The repository HTTP client (which sets a
User-Agent) and this credential-free curl command both worked:

```sh
mkdir -p runs
curl -fsSL --max-time 30 https://api.runpod.io/v2/openapi.json -o runs/runpod-openapi.json
```

After cleanup, query `/billing/pods` with `podId`, `bucketSize=hour` and a suitable
`startTime`/`endTime`, or `lastN`, using `client.http.request`. Sum the returned
`records[].totalAmount` for the owned pod. Billing buckets can lag: an empty
result is not proof of zero cost. Until charges post, label elapsed allocation
time multiplied by the verified rate, plus the applicable
[storage charge](https://docs.runpod.io/pods/storage/types), as an estimate.
