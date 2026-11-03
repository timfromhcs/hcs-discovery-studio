// Bit-packed Tanimoto kernel shared by the browser (WebGPU) and the native
// Vulkan/D3D12/Metal engine (wgpu-py). Integer arithmetic only: intersection and
// union popcounts are exact; the caller divides (union == 0 -> similarity 0.0).
// Fingerprint = 2048 bits packed into 64 little-endian u32 words.
// Library layout is word-major (transposed): library[w * stride + i], so neighbouring
// invocations read neighbouring addresses (coalesced). `stride` = fingerprints in this buffer.
const WORDS: u32 = 64u;

struct Params {
  count: u32,   // number of library fingerprints in this dispatch
  offset: u32,  // first fingerprint (column) of the buffer this dispatch scores
  stride: u32,  // columns in the buffer (row length of the transposed matrix)
  _pad1: u32,
}

@group(0) @binding(0) var<storage, read> query: array<u32>;
@group(0) @binding(1) var<storage, read> library: array<u32>;
@group(0) @binding(2) var<storage, read_write> out_inter: array<u32>;
@group(0) @binding(3) var<storage, read_write> out_union: array<u32>;
@group(0) @binding(4) var<uniform> params: Params;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>,
        @builtin(num_workgroups) nwg: vec3<u32>) {
  let i = gid.x + gid.y * nwg.x * 64u;
  if (i >= params.count) {
    return;
  }
  let col = params.offset + i;
  var inter = 0u;
  var uni = 0u;
  for (var w = 0u; w < WORDS; w = w + 1u) {
    let a = query[w];
    let b = library[w * params.stride + col];
    inter = inter + countOneBits(a & b);
    uni = uni + countOneBits(a | b);
  }
  out_inter[i] = inter;
  out_union[i] = uni;
}
