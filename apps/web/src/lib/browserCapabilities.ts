import { useEffect, useState } from "react";

/**
 * Client-side hardware capability probe.
 *
 * Mirrors the backend Vulkan probe's philosophy: report what the browser can
 * actually do, never imply scientific compute that does not exist. WebGPU and
 * WebAssembly are detected here purely as platform capabilities; no
 * scientific engine in this release executes through either of them.
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
}

export interface BrowserCapabilities {
  webassembly: boolean;
  webgpu: WebGpuInfo;
}

interface MinimalGpu {
  requestAdapter(options?: { powerPreference?: string }): Promise<{
    isFallbackAdapter?: boolean;
    requestAdapterInfo?: () => Promise<{ description?: string; vendor?: string }>;
  } | null>;
}

function getGpu(): MinimalGpu | undefined {
  if (typeof navigator === "undefined" || !("gpu" in navigator)) return undefined;
  return (navigator as unknown as { gpu: MinimalGpu }).gpu;
}

/**
 * Probe WebAssembly and WebGPU support. Safe to call in any browser; every
 * branch degrades to `false` rather than throwing. WebGPU adapter request is
 * fire-and-forget with no persistent handle, so it never holds the device open.
 */
export async function probeBrowserCapabilities(): Promise<BrowserCapabilities> {
  const webassembly = typeof WebAssembly === "object" && typeof WebAssembly !== "undefined";

  const gpu = getGpu();
  if (!gpu) {
    return {
      webassembly,
      webgpu: { supported: false, adapterAvailable: false, fallbackAdapter: false, adapterName: null },
    };
  }

  try {
    const adapter = await gpu.requestAdapter({ powerPreference: "low-power" });
    if (!adapter) {
      return {
        webassembly,
        webgpu: { supported: true, adapterAvailable: false, fallbackAdapter: false, adapterName: null },
      };
    }
    let adapterName: string | null = null;
    try {
      const info = await adapter.requestAdapterInfo?.();
      adapterName = info ? (info.description || info.vendor || null) : null;
    } catch {
      adapterName = null;
    }
    return {
      webassembly,
      webgpu: {
        supported: true,
        adapterAvailable: true,
        fallbackAdapter: Boolean(adapter.isFallbackAdapter),
        adapterName,
      },
    };
  } catch {
    return {
      webassembly,
      webgpu: { supported: true, adapterAvailable: false, fallbackAdapter: false, adapterName: null },
    };
  }
}

/**
 * Run {@link probeBrowserCapabilities} once on mount. Returns `null` until the
 * (async) probe resolves so callers can render a neutral "checking…" state.
 */
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
