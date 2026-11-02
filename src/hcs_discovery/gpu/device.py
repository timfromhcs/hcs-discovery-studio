"""Adapter selection. Prefers a real Vulkan device; never reports software as a GPU."""

from __future__ import annotations

from typing import Any

PREFERRED_BACKENDS = ("Vulkan", "D3D12", "Metal")
HARDWARE_KINDS = ("DiscreteGPU", "IntegratedGPU", "VirtualGPU")


def select_adapter() -> Any | None:
    """Best hardware adapter: Vulkan first, then D3D12/Metal. ``None`` if only software."""
    try:
        import wgpu

        adapters = list(wgpu.gpu.enumerate_adapters_sync())
    except Exception:
        return None
    for backend in PREFERRED_BACKENDS:
        for kind in HARDWARE_KINDS:  # discrete before integrated
            for adapter in adapters:
                info = adapter.info
                if info.get("backend_type") == backend and info.get("adapter_type") == kind:
                    return adapter
    return None


def probe_gpu() -> dict[str, Any]:
    """Describe what the host exposes; a Vulkan device alone is not a speed claim."""
    try:
        import wgpu  # noqa: F401
    except ImportError:
        return {
            "status": "unavailable",
            "detail": "wgpu is not installed (pip install 'hcs-discovery[gpu]').",
            "adapter": None,
            "backend": None,
        }
    adapter = select_adapter()
    if adapter is None:
        return {
            "status": "software_only",
            "detail": "No hardware GPU adapter was found; only software or no adapters.",
            "adapter": None,
            "backend": None,
        }
    info = adapter.info
    limits = adapter.limits
    return {
        "status": "available",
        "detail": "Hardware adapter selected.",
        "adapter": info.get("device"),
        "backend": info.get("backend_type"),
        "adapter_type": info.get("adapter_type"),
        "max_storage_buffer_binding_size": limits.get("max-storage-buffer-binding-size"),
    }
