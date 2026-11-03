import { useState } from "react";
import { compareEngines, type GpuCompareResult } from "../lib/gpuTanimoto";
import { Badge, Button, Card, CardHeader, InlineNotice, KeyValue } from "./ui";

/**
 * Parity-first WebGPU benchmark: the shared WGSL Tanimoto kernel against a JavaScript
 * CPU reference. Opt-in (button). Speed is only shown after exact parity and is a
 * measurement on this device, not a promise. Integer popcounts are exact, so a browser
 * run either matches the reference or reports a failure — there is no tolerance.
 */
export function GpuBenchmark() {
  const [state, setState] = useState<"idle" | "running" | "done">("idle");
  const [result, setResult] = useState<GpuCompareResult | null>(null);

  const run = async () => {
    setState("running");
    setResult(null);
    setResult(await compareEngines(100_000, 5));
    setState("done");
  };

  const round = (value: number | null, digits = 1) => (value === null ? "—" : value.toFixed(digits));

  return (
    <Card>
      <CardHeader
        title="WebGPU similarity benchmark"
        subtitle="Bit-packed Tanimoto on the GPU (the same WGSL kernel as the native Vulkan engine), checked against a CPU reference."
        icon="run"
        actions={
          <Button size="sm" variant="secondary" icon="play" onClick={() => void run()} loading={state === "running"}>
            Run benchmark
          </Button>
        }
      />
      {state === "idle" ? (
        <p className="muted small">
          Scores one query against 100,000 synthetic Morgan fingerprints (RDKit WebAssembly). Integer popcounts must
          match the CPU exactly before any timing is shown. Nothing leaves this browser. The local backend reports the
          same measurement with <code>hcs-discovery gpu bench</code>.
        </p>
      ) : null}
      {state === "running" ? <p className="muted small">Building fingerprints and running on the GPU…</p> : null}
      {state === "done" && result?.status === "unavailable" ? (
        <InlineNotice tone="info" title="WebGPU hardware not available">
          {result.detail} The local backend (<code>hcs-discovery gpu bench</code>) is the measured Vulkan path.
        </InlineNotice>
      ) : null}
      {state === "done" && result?.status === "failed" ? (
        <InlineNotice tone="danger" title="Parity check failed">
          {result.detail} No speed-up is reported.
        </InlineNotice>
      ) : null}
      {state === "done" && result?.status === "passed" ? (
        <>
          <KeyValue
            items={[
              { label: "Adapter", value: result.adapter ?? "—", mono: true },
              { label: "Library size", value: result.n.toLocaleString() },
              { label: "CPU reference (JavaScript)", value: `${round(result.cpuMs)} ms` },
              { label: "WebGPU, library resident", value: `${round(result.gpuMs)} ms` },
              { label: "CPU throughput", value: `${round(result.cpuMps, 2)} M/s` },
              { label: "GPU throughput", value: `${round(result.gpuMps, 2)} M/s` },
              { label: "Speed-up (measured)", value: `${round(result.speedup)}×` },
            ]}
          />
          <div className="row-actions">
            <Badge tone="ok" dot>
              Parity: bit-exact
            </Badge>
          </div>
        </>
      ) : null}
    </Card>
  );
}
