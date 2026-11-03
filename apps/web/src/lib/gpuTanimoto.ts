import wgsl from "../../../../src/hcs_discovery/gpu/kernels/tanimoto.wgsl?raw";
import { loadRDKit } from "./rdkit";

/**
 * Bit-packed Tanimoto similarity on WebGPU, using the *same* WGSL file as the native
 * Vulkan engine (src/hcs_discovery/gpu). Counts are integer popcounts, so GPU results
 * must equal the CPU reference exactly; the benchmark reports parity before speed.
 * Fingerprints come from RDKit WebAssembly (Morgan r=2, 2048 bit).
 */

export const WORDS = 64;
const BITS = WORDS * 32;
const WG = 64;
const MAX_X = 65535;

/* eslint-disable @typescript-eslint/no-explicit-any */
type Gpu = any;

const STORAGE = 0x80;
const COPY_SRC = 0x04;
const COPY_DST = 0x08;
const MAP_READ = 0x01;
const UNIFORM = 0x40;

const BASE_SMILES = [
  "CC(=O)Oc1ccccc1C(=O)O",
  "CN1CCC[C@H]1c1cccnc1",
  "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
  "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
  "O=C(O)c1ccccc1O",
  "CC(=O)Nc1ccc(O)cc1",
  "CCN(CC)CCNC(=O)c1ccc(N)cc1",
  "c1ccc2c(c1)cc[nH]2",
  "COc1ccc2[nH]cc(CCNC(C)=O)c2c1",
  "CC1=CC=C(C=C1)S(=O)(=O)N",
];

/** Pack a '0'/'1' string (RDKit get_morgan_fp) into 64 little-endian u32 words. */
export function packBitString(bits: string): Uint32Array {
  const out = new Uint32Array(WORDS);
  for (let k = 0; k < BITS && k < bits.length; k++) {
    if (bits.charCodeAt(k) === 49) out[k >>> 5] |= 1 << (k & 31);
  }
  return out;
}

export async function fingerprintsFromSmiles(smiles: string[]): Promise<{ packed: Uint32Array; valid: boolean[] }> {
  const rdkit = await loadRDKit();
  const packed = new Uint32Array(smiles.length * WORDS);
  const valid: boolean[] = [];
  smiles.forEach((smi, i) => {
    const mol = rdkit.get_mol(smi);
    if (!mol) {
      valid.push(false);
      return;
    }
    try {
      packed.set(packBitString(mol.get_morgan_fp(JSON.stringify({ radius: 2, nBits: BITS }))), i * WORDS);
      valid.push(true);
    } finally {
      mol.delete();
    }
  });
  return { packed, valid };
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Deterministic ECFP-like library (row-major, n × 64): real base fingerprints + sparse bit flips. */
export async function syntheticLibrary(n: number, seed = 0): Promise<Uint32Array> {
  const { packed: base } = await fingerprintsFromSmiles(BASE_SMILES);
  const rand = mulberry32(seed);
  const word = () => (rand() * 4294967296) >>> 0;
  const lib = new Uint32Array(n * WORDS);
  for (let i = 0; i < n; i++) {
    const b = Math.floor(rand() * BASE_SMILES.length) * WORDS;
    for (let w = 0; w < WORDS; w++) lib[i * WORDS + w] = base[b + w] ^ (word() & word() & word());
  }
  return lib;
}

export function transpose(rowMajor: Uint32Array, n: number): Uint32Array {
  const out = new Uint32Array(rowMajor.length);
  for (let i = 0; i < n; i++) for (let w = 0; w < WORDS; w++) out[w * n + i] = rowMajor[i * WORDS + w];
  return out;
}

function popcount32(v: number): number {
  v -= (v >>> 1) & 0x55555555;
  v = (v & 0x33333333) + ((v >>> 2) & 0x33333333);
  return (Math.imul((v + (v >>> 4)) & 0x0f0f0f0f, 0x01010101) >>> 24) & 0xff;
}

export interface Counts {
  inter: Uint32Array;
  union: Uint32Array;
}

/** CPU reference (JavaScript). Same integer semantics as the shader. */
export function cpuCounts(query: Uint32Array, rowMajor: Uint32Array, n: number): Counts {
  const inter = new Uint32Array(n);
  const union = new Uint32Array(n);
  for (let i = 0; i < n; i++) {
    let a = 0;
    let u = 0;
    const base = i * WORDS;
    for (let w = 0; w < WORDS; w++) {
      const x = query[w];
      const y = rowMajor[base + w];
      a += popcount32(x & y);
      u += popcount32(x | y);
    }
    inter[i] = a;
    union[i] = u;
  }
  return { inter, union };
}

/** Empty union is defined as 0.0, matching RDKit and the native engine. */
export function ratio(c: Counts): Float32Array {
  const out = new Float32Array(c.inter.length);
  for (let i = 0; i < out.length; i++) out[i] = c.union[i] > 0 ? Math.fround(c.inter[i] / c.union[i]) : 0;
  return out;
}

export class WebGpuTanimoto {
  private resident: Gpu | null = null;
  private residentN = 0;
  private constructor(
    private readonly device: Gpu,
    private readonly pipeline: Gpu,
    readonly adapterName: string,
  ) {}

  static async create(): Promise<WebGpuTanimoto | null> {
    const gpu = (typeof navigator !== "undefined" ? (navigator as any).gpu : undefined) as Gpu | undefined;
    if (!gpu) return null;
    const adapter = await gpu.requestAdapter();
    if (!adapter || adapter.isFallbackAdapter) return null; // software adapters never back a speed claim
    let name = "unknown adapter";
    try {
      const info = adapter.info ?? (await adapter.requestAdapterInfo?.());
      name = info?.description || info?.device || info?.vendor || name;
    } catch {
      /* name stays unknown */
    }
    const device = await adapter.requestDevice();
    const module = device.createShaderModule({ code: wgsl });
    const pipeline = device.createComputePipeline({ layout: "auto", compute: { module, entryPoint: "main" } });
    return new WebGpuTanimoto(device, pipeline, name);
  }

  /** Keep a library (word-major layout) resident on the GPU. */
  loadLibrary(transposed: Uint32Array, n: number): void {
    const limit = Number(this.device.limits?.maxStorageBufferBindingSize ?? 134_217_728);
    if (transposed.byteLength > limit) {
      throw new Error(
        `A ${transposed.byteLength}-byte library exceeds this adapter's ${limit}-byte storage-buffer binding.`,
      );
    }
    this.resident?.destroy();
    this.residentN = n;
    this.resident = this.device.createBuffer({ size: transposed.byteLength, usage: STORAGE | COPY_DST });
    this.device.queue.writeBuffer(this.resident, 0, transposed);
  }

  async queryResident(query: Uint32Array): Promise<Counts> {
    if (!this.resident) throw new Error("no resident library");
    const dev = this.device;
    const n = this.residentN;
    const mk = (size: number, usage: number) => dev.createBuffer({ size, usage });
    const q = mk(query.byteLength, STORAGE | COPY_DST);
    dev.queue.writeBuffer(q, 0, query);
    const oi = mk(n * 4, STORAGE | COPY_SRC);
    const ou = mk(n * 4, STORAGE | COPY_SRC);
    const params = mk(16, UNIFORM | COPY_DST);
    dev.queue.writeBuffer(params, 0, new Uint32Array([n, 0, n, 0]));
    const ri = mk(n * 4, COPY_DST | MAP_READ);
    const ru = mk(n * 4, COPY_DST | MAP_READ);
    const group = dev.createBindGroup({
      layout: this.pipeline.getBindGroupLayout(0),
      entries: [q, this.resident, oi, ou, params].map((buffer, binding) => ({ binding, resource: { buffer } })),
    });
    const groups = Math.ceil(n / WG);
    const gx = Math.min(groups, MAX_X);
    const gy = Math.ceil(groups / gx);
    const enc = dev.createCommandEncoder();
    const pass = enc.beginComputePass();
    pass.setPipeline(this.pipeline);
    pass.setBindGroup(0, group);
    pass.dispatchWorkgroups(gx, gy, 1);
    pass.end();
    enc.copyBufferToBuffer(oi, 0, ri, 0, n * 4);
    enc.copyBufferToBuffer(ou, 0, ru, 0, n * 4);
    dev.queue.submit([enc.finish()]);
    await Promise.all([ri.mapAsync(1), ru.mapAsync(1)]);
    const inter = new Uint32Array(ri.getMappedRange().slice(0));
    const union = new Uint32Array(ru.getMappedRange().slice(0));
    for (const b of [q, oi, ou, params, ri, ru]) b.destroy();
    return { inter, union };
  }

  destroy(): void {
    this.resident?.destroy();
    this.device.destroy?.();
  }
}

export interface GpuCompareResult {
  status: "passed" | "failed" | "unavailable";
  detail: string;
  adapter: string | null;
  n: number;
  parityExact: boolean | null;
  cpuMs: number | null;
  gpuMs: number | null;
  cpuMps: number | null;
  gpuMps: number | null;
  speedup: number | null;
}

const median = (xs: number[]) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];

/** Millions of Tanimoto comparisons per second. */
const throughput = (n: number, ms: number | null) => (ms && ms > 0 ? n / (ms / 1000) / 1e6 : null);

/** Parity first, then speed: JS CPU reference vs the resident WebGPU kernel. */
export async function compareEngines(n = 100_000, repeats = 5): Promise<GpuCompareResult> {
  const none = {
    adapter: null,
    n,
    parityExact: null,
    cpuMs: null,
    gpuMs: null,
    cpuMps: null,
    gpuMps: null,
    speedup: null,
  } as const;
  let engine: WebGpuTanimoto | null = null;
  try {
    engine = await WebGpuTanimoto.create();
  } catch (error) {
    return { ...none, status: "unavailable", detail: error instanceof Error ? error.message : "WebGPU init failed" };
  }
  if (!engine) {
    return {
      ...none,
      status: "unavailable",
      detail: "No hardware WebGPU adapter (software adapters are ignored).",
    };
  }
  try {
    const lib = await syntheticLibrary(n);
    const query = lib.slice(0, WORDS);
    let t0 = performance.now();
    const ref = cpuCounts(query, lib, n);
    const cpuMs = performance.now() - t0;

    engine.loadLibrary(transpose(lib, n), n);
    await engine.queryResident(query); // warm-up
    const times: number[] = [];
    let got: Counts = { inter: new Uint32Array(0), union: new Uint32Array(0) };
    for (let r = 0; r < repeats; r++) {
      t0 = performance.now();
      got = await engine.queryResident(query);
      times.push(performance.now() - t0);
    }
    const exact =
      got.inter.length === n &&
      got.inter.every((v, i) => v === ref.inter[i]) &&
      got.union.every((v, i) => v === ref.union[i]);
    const gpuMs = median(times);
    return {
      status: exact ? "passed" : "failed",
      detail: exact ? "GPU counts are bit-exact against the JavaScript reference." : "Parity violated.",
      adapter: engine.adapterName,
      n,
      parityExact: exact,
      cpuMs,
      gpuMs,
      cpuMps: throughput(n, cpuMs),
      gpuMps: throughput(n, gpuMs),
      speedup: cpuMs / gpuMs,
    };
  } catch (error) {
    return {
      ...none,
      status: "failed",
      adapter: engine.adapterName,
      detail: error instanceof Error ? error.message : "The WebGPU kernel could not run.",
    };
  } finally {
    engine.destroy();
  }
}
