# Local models and LLM providers

HCS Discovery Studio is CPU-first and does not bundle model weights or engine
binaries. RDKit and two literature property estimates always run. AutoDock Vina
runs when its official binary is installed. Other engines are listed in the
model registry as `planned` metadata.

## What works today

- `science:rdkit` — parsing, standardisation, descriptors, fingerprints,
  similarity and depictions on CPU.
- `science:autodock-vina` — CPU docking through the official Vina 1.2.x binary,
  found via `HCS_VINA_BINARY`, `bin/` or `PATH`. It is reported available only
  when `vina --version` succeeds. Receptors are read from
  `<HCS_DATA_DIR>/receptors`. Ligand preparation and its comparison with Meeko
  are described in `docs/validation/ligand-prep-meeko.md`.
- `science:property-predict` — a reduced ESOL logS equation and a CNS MPO
  approximation. These are literature formulas, not learned models; see
  `SCIENTIFIC_LIMITATIONS.md`.
- `llm:openai-compatible` — configuration metadata and an optional `/models`
  probe for a local OpenAI-compatible server.
- `doctor --check-vulkan` — reports Vulkan devices exposed by `vulkaninfo`.
- `models list --probe` / `models inspect <id> --probe` — live status for the
  configured provider.

The research agent's Ask mode sends the question and read-only context to a
configured provider. If none is configured, or it fails, Ask answers from
built-in rules and says so (`source: local_rules`, `provider_error`). Plan and
Run do not use the LLM, and there is no LLM workflow node.

## Planned engines

The registry currently lists these as `planned`, with `implemented=false`:

| ID | Category | Why it is not runnable |
|---|---|---|
| `science:openmm` | simulation | No simulation engine bundled |
| `science:chemprop` | property | Needs validated weights per endpoint |
| `science:boltz2` | structure | Large weights and GPU-class hardware |
| `science:chai1` | structure | High hardware requirements |

Planned cards are never offered as workflow nodes. They are visible so users can
see the roadmap without mistaking it for capability.

## Configure a local OpenAI-compatible provider

Start a local server such as llama.cpp's server or LM Studio, then set:

```bash
export HCS_LLM_BASE_URL=http://127.0.0.1:1234/v1
export HCS_LLM_MODEL=your-local-model
# Optional, only if your server requires a key:
export HCS_LLM_API_KEY=...
```

Probe it:

```bash
hcs-discovery models list --probe
hcs-discovery models inspect llm:openai-compatible --probe
hcs-discovery doctor --check-providers
```

The probe calls `GET /models` with a 20-second timeout. A key is sent as a
bearer token and is never logged. The settings API reports only `configured` or
`missing`.

## Network policy

The default is `HCS_NETWORK_POLICY=local`.

- A loopback endpoint (`127.0.0.1`, `::1`, `localhost`) is allowed.
- A non-loopback endpoint is blocked with `policy_blocked` even if a URL is set.
- Remote use requires **both** `HCS_NETWORK_POLICY=remote` and
  `HCS_REMOTE_LLM_ENABLED=true`, plus a deliberate data-sharing decision.
- The application does not contact a provider unless you explicitly probe or
  call it.

Remote LLM use can send your prompts and data to another party. Review that
provider's terms, retention and jurisdiction before enabling it. This project
does not provide a remote proxy or a hosted service.

## Vulkan and GPUs

`doctor --check-vulkan` runs `vulkaninfo --summary` if it is installed and
reports device names and the instance version. It deliberately reports
`model_support: "unknown"`.

A Vulkan device does **not** mean:

- a scientific model supports Vulkan,
- the model will be faster,
- the model has been validated on that device,
- CUDA is available.

No CUDA dependency is required or tested. No GPU acceleration is claimed for
RDKit or any planned engine.

## Adding a real local model

Before integrating weights:

1. Record the code license, weight license and training-data terms separately.
2. Pin the exact weight revision and checksum.
3. Define the scientific task and output units.
4. Add an adapter card with an honest status.
5. Add deterministic fixture tests that do not require the weights.
6. Add a hardware and memory requirement, and fail clearly when unmet.
7. Do not claim accuracy without following
   `docs/scientific-validation/VALIDATION_PROTOCOL.md`.

Model weights should not be committed to Git. Use a documented download step or
a release asset, and keep large files out of the repository history.

## Resource guidance

| Workload | Suggested hardware |
|---|---|
| Import and descriptors for ≤50k rows | 4 CPU cores, 8 GB RAM |
| RDKit similarity and ranking | 4 CPU cores, 8 GB RAM |
| Local LLM probe | The provider's own requirements |
| AutoDock Vina docking | CPU threads via the node's `cpu_threads`; runtime per ligand depends on exhaustiveness and was not benchmarked |
| MD / structure models | Not supported in this release |

The manifest records CPU count and platform. It does not claim a benchmark.
