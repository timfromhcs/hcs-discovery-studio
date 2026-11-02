import { useEffect, useState } from "react";

/**
 * Client-side hardware capability probe.
 *
 * Mirrors the backend Vulkan probe's rule: report what the browser can actually
 * do, never imply scientific compute that does not exist. WebGPU is probed with a
 * real, trivial compute-pipeline self-test (one storage buffer incremented once)
 * so "compute verified" means the GPU pipeline ran, not that an adapter exists.
 * No scientific engine executes through WebGPU in this release; the self-test
 * only proves the pipeline is usable.
 */

export interface WebGpuInfo {
  /** The browser exposes the WebGPU API (`navigator.gpu`). */
  supported: boolean;
  /** A compatible GPU adapter was successfully requested. */
  adapterAvailable: boolean;
  /** The browser fell back to a software (SwiftShader) adapter. */
  fallbackAdapter: boolean;
  /** Human-readable adapter name, when the browser exposes it without prompting. */
  adapterName: string | null;
  /** Maximum compute invocations per workgroup, when the adapter reports it. */
  maxComputeInvocations: number | null;
  /** A trivial WGSL compute pipeline actually executed and produced the expected result. */
  computeVerified: boolean;
  /** Short reason when the self-test did not run or failed. */
  computeDetail: string | null;
}

export interface BrowserCapabilities {
  webassembly: boolean;
  webgpu: WebGpuInfo;
}

/* Structural view of the WebGPU objects we use, so this module compiles against
 * any DOM lib (the concrete types have moved between TypeScript versions). */
interface GpuAdapterLike {
  isFallbackAdapter?: boolean;
  limits?: { maxComputeInvocationsPerWorkgroup?: number };
  requestAdapterInfo?: () => Promise<{ description?: string; vendor?: string }>;
  requestDevice?: () => Promise<GpuDeviceLike>;
}
interface GpuShaderModuleLike {
  destroy?: () => void;
}
interface GpuBufferLike {
  destroy?: () => void;
  mapAsync?: (mode: number) => Promise<void>;
  getMappedRange?: () => ArrayBuffer;
  unmap?: () => void;
}
interface GpuDeviceLike {
  createShaderModule(args: { code: string }): GpuShaderModuleLike;
  createBuffer(args: { size: number; usage: number }): GpuBufferLike;
  createBindGroup(args: Record<string, unknown>): unknown;
  createBindGroupLayout(args: Record<string, unknown>): unknown;
  createPipelineLayout(args: Record<string, unknown>): unknown;
  createComputePipeline(args: Record<string, unknown>): unknown;
  createCommandEncoder(): {
    beginComputePass(): {
      setPipeline(pipeline: unknown): void;
      setBindGroup(index: number, group: unknown): void;
      dispatchWorkgroups(x: number): void;
      end(): void;
    };
    copyBufferToBuffer(src: unknown, s: number, dst: unknown, d: number, size: number): void;
    finish(): unknown;
  };
  queue: { submit(commandBuffers: unknown[]): void };
  destroy?: () => void;
}
interface GpuLike {
  requestAdapter?: () => Promise<GpuAdapterLike | null>;
}

const STORAGE = 0x80; // GPUBufferUsage.STORAGE
const COPY_SRC = 0x04; // GPUBufferUsage.COPY_SRC
const COPY_DST = 0x08; // GPUBufferUsage.COPY_DST
const MAP_READ = 0x01; // GPUBufferUsage.MAP_READ

function getGpu(): GpuLike | undefined {
  if (typeof navigator === "undefined" || !("gpu" in navigator)) return undefined;
  return (navigator as unknown as { gpu: GpuLike }).gpu;
}

async function adapterInfo(adapter: GpuAdapterLike): Promise<{ name: string | null; fallback: boolean }> {
  let name: string | null = null;
  try {
    const info = await adapter.requestAdapterInfo?.();
    name = info ? (info.description || info.vendor || null) : null;
  } catch {
    name = null;
  }
  return { name, fallback: Boolean(adapter.isFallbackAdapter) };
}

const WGSL = `@group(0) @binding(0) var<storage, read_write> data: array<u32>;
@compute @workgroup_size(1)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
  data[id.x] = data[id.x] + 1u;
}`;

/** Run a one-workgroup, one-invocation storage-buffer increment and read it back. */
async function verifyCompute(adapter: GpuAdapterLike): Promise<{ verified: boolean; detail: string | null }> {
  if (!adapter.requestDevice) return { verified: false, detail: "requestDevice unsupported" };
  let device: GpuDeviceLike;
  try {
    device = await adapter.requestDevice();
  } catch {
    return { verified: false, detail: "could not request a device" };
  }
  try {
    const shader = device.createShaderModule({ code: WGSL });
    const input = device.createBuffer({ size: 4, usage: STORAGE | COPY_SRC });
    const output = device.createBuffer({ size: 4, usage: COPY_DST | MAP_READ });
    const bindGroupLayout = device.createBindGroupLayout({
      entries: [{ binding: 0, visibility: 0x04 /* COMPUTE */, buffer: { type: "storage" } }],
    });
    const bindGroup = device.createBindGroup({ layout: bindGroupLayout, entries: [{ binding: 0, resource: { buffer: input } }] });
    const pipeline = device.createComputePipeline({
      layout: device.createPipelineLayout({ bindGroupLayouts: [bindGroupLayout] }),
      compute: { module: shader, entryPoint: "main" },
    });
    const encoder = device.createCommandEncoder();
    const pass = encoder.beginComputePass();
    pass.setPipeline(pipeline);
    pass.setBindGroup(0, bindGroup);
    pass.dispatchWorkgroups(1);
    pass.end();
    encoder.copyBufferToBuffer(input, 0, output, 0, 4);
    device.queue.submit([encoder.finish()]);

    if (output.mapAsync) {
      await output.mapAsync(MAP_READ);
      const view = new Uint32Array(output.getMappedRange?.() ?? new ArrayBuffer(4));
      const value = view[0];
      output.unmap?.();
      return { verified: value === 1, detail: value === 1 ? null : `unexpected result ${value}` };
    }
    return { verified: false, detail: "buffer mapping unsupported" };
  } catch (error) {
    return { verified: false, detail: error instanceof Error ? error.message : "compute self-test failed" };
  } finally {
    try {
      device.destroy?.();
    } catch {
      /* best-effort cleanup */
    }
  }
}

/** Probe WebAssembly and WebGPU support; every branch degrades rather than throws. */
export async function probeBrowserCapabilities(): Promise<BrowserCapabilities> {
  const webassembly = typeof WebAssembly === "object" && typeof WebAssembly !== "undefined";
  const empty = { supported: false, adapterAvailable: false, fallbackAdapter: false, adapterName: null, maxComputeInvocations: null, computeVerified: false, computeDetail: null };

  const gpu = getGpu();
  if (!gpu || !gpu.requestAdapter) return { webassembly, webgpu: empty };

  let adapter: GpuAdapterLike | null;
  try {
    adapter = await gpu.requestAdapter();
  } catch {
    return { webassembly, webgpu: { ...empty, supported: true, computeDetail: "requestAdapter failed" } };
  }
  if (!adapter) {
    return { webassembly, webgpu: { ...empty, supported: true, computeDetail: "no compatible adapter" } };
  }

  const info = await adapterInfo(adapter);
  const compute = await verifyCompute(adapter);
  return {
    webassembly,
    webgpu: {
      supported: true,
      adapterAvailable: true,
      fallbackAdapter: info.fallback,
      adapterName: info.name,
      maxComputeInvocations: adapter.limits?.maxComputeInvocationsPerWorkgroup ?? null,
      computeVerified: compute.verified,
      computeDetail: compute.detail,
    },
  };
}

/** Run {@link probeBrowserCapabilities} once on mount; returns `null` while pending. */
export function useBrowserCapabilities(): BrowserCapabilities | null {
  const [result, setResult] = useState<BrowserCapabilities | null>(null);

  useEffect(() => {
    let cancelled = false;
    void probeBrowserCapabilities().then((capabilities) => {
      if (!cancelled) setResult(capabilities);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return result;
}
