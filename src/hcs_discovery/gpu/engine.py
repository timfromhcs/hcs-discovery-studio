"""Native engine: runs the shared WGSL kernel through wgpu-py (Vulkan preferred)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from hcs_discovery.gpu import KERNEL_PATH, WORDS
from hcs_discovery.gpu.device import select_adapter

_WG = 64
_MAX_X = 65535  # per-dimension workgroup limit guaranteed by WebGPU defaults


class GpuUnavailableError(RuntimeError):
    """No hardware adapter (or wgpu missing)."""


@dataclass(frozen=True)
class GpuResult:
    inter: np.ndarray
    union: np.ndarray
    total_ms: float
    adapter: str
    backend: str


class GpuEngine:
    """Holds a device and compiled pipeline; reuse it across calls."""

    def __init__(self) -> None:
        try:
            import wgpu
        except ImportError as exc:
            raise GpuUnavailableError("wgpu is not installed") from exc
        adapter = select_adapter()
        if adapter is None:
            raise GpuUnavailableError("no hardware GPU adapter")
        self._wgpu = wgpu
        self.adapter_name = str(adapter.info.get("device"))
        self.backend = str(adapter.info.get("backend_type"))
        self.device = adapter.request_device_sync()
        shader = self.device.create_shader_module(code=KERNEL_PATH.read_text(encoding="utf-8"))
        self.pipeline = self.device.create_compute_pipeline(
            layout="auto", compute={"module": shader, "entry_point": "main"}
        )
        self.max_chunk = int(adapter.limits["max-storage-buffer-binding-size"]) // (WORDS * 4)

    def counts(self, query: np.ndarray, library: np.ndarray, *, chunk: int | None = None) -> GpuResult:
        lib = np.ascontiguousarray(library, dtype=np.uint32)
        q = np.ascontiguousarray(query, dtype=np.uint32).reshape(-1)
        n = lib.shape[0]
        step = max(1, min(chunk or n or 1, self.max_chunk, _MAX_X * _WG))
        inter = np.empty(n, dtype=np.uint32)
        union = np.empty(n, dtype=np.uint32)
        started = time.perf_counter()
        for start in range(0, n, step):
            part = lib[start : start + step]
            i, u = self._dispatch(q, part)
            inter[start : start + part.shape[0]] = i
            union[start : start + part.shape[0]] = u
        total = (time.perf_counter() - started) * 1000.0
        return GpuResult(inter, union, total, self.adapter_name, self.backend)

    def load_library(self, library: np.ndarray) -> None:
        """Keep a library resident on the GPU (single binding; must fit one storage buffer)."""
        lib = np.ascontiguousarray(library, dtype=np.uint32)
        if lib.shape[0] > self.max_chunk:
            raise ValueError("library exceeds one storage-buffer binding; use counts() with chunking")
        self.release_library()
        self._resident_n = lib.shape[0]
        self._resident = self.device.create_buffer_with_data(
            data=np.ascontiguousarray(lib.T), usage=self._wgpu.BufferUsage.STORAGE
        )

    def release_library(self) -> None:
        if getattr(self, "_resident", None) is not None:
            self._resident.destroy()
        self._resident = None
        self._resident_n = 0

    def query_resident(self, query: np.ndarray) -> GpuResult:
        """Score ``query`` against the resident library (no library upload)."""
        if getattr(self, "_resident", None) is None:
            raise RuntimeError("no resident library; call load_library() first")
        q = np.ascontiguousarray(query, dtype=np.uint32).reshape(-1)
        started = time.perf_counter()
        i, u = self._dispatch(q, None, resident=self._resident, count=self._resident_n)
        total = (time.perf_counter() - started) * 1000.0
        return GpuResult(i, u, total, self.adapter_name, self.backend)

    def _dispatch(
        self,
        q: np.ndarray,
        part: np.ndarray | None,
        *,
        resident: Any | None = None,
        count: int | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        usage = self._wgpu.BufferUsage
        dev = self.device
        if part is not None:
            count = part.shape[0]
        elif resident is None:
            raise ValueError("either a library chunk or a resident buffer is required")
        assert count is not None
        qbuf = dev.create_buffer_with_data(data=q, usage=usage.STORAGE)
        if resident is not None:
            lbuf = resident
        else:
            assert part is not None
            lbuf = dev.create_buffer_with_data(data=np.ascontiguousarray(part.T), usage=usage.STORAGE)
        size = count * 4
        obuf_i = dev.create_buffer(size=size, usage=usage.STORAGE | usage.COPY_SRC)
        obuf_u = dev.create_buffer(size=size, usage=usage.STORAGE | usage.COPY_SRC)
        pbuf = dev.create_buffer_with_data(data=np.array([count, 0, count, 0], dtype=np.uint32), usage=usage.UNIFORM)
        buffers = (qbuf, lbuf, obuf_i, obuf_u, pbuf)
        owned = tuple(b for b in buffers if b is not resident)
        group = dev.create_bind_group(
            layout=self.pipeline.get_bind_group_layout(0),
            entries=[
                {"binding": b, "resource": {"buffer": buf, "offset": 0, "size": buf.size}}
                for b, buf in enumerate(buffers)
            ],
        )
        groups = -(-count // _WG)
        gx = min(groups, _MAX_X)
        gy = -(-groups // gx)
        enc = dev.create_command_encoder()
        compute = enc.begin_compute_pass()
        compute.set_pipeline(self.pipeline)
        compute.set_bind_group(0, group)
        compute.dispatch_workgroups(gx, gy, 1)
        compute.end()
        dev.queue.submit([enc.finish()])
        i = np.frombuffer(dev.queue.read_buffer(obuf_i), dtype=np.uint32).copy()
        u = np.frombuffer(dev.queue.read_buffer(obuf_u), dtype=np.uint32).copy()
        for buf in owned:
            buf.destroy()
        return i, u


def gpu_counts(query: np.ndarray, library: np.ndarray, *, chunk: int | None = None) -> GpuResult:
    return GpuEngine().counts(query, library, chunk=chunk)
