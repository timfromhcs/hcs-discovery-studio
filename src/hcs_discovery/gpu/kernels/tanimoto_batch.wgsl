// Batched Bit-packed Tanimoto kernel: Q queries against N library fingerprints in
// one dispatch. Integer arithmetic only; the caller divides (union == 0 -> 0.0).
// Fingerprint = 2048 bits packed into 64 little-endian u32 words.
// Library layout is word-major (transposed): library[w * stride + col].
// Query layout is query-major: queries[q * 64 + w].
// Output layout is query-major: out[q * count + col].
const WORDS: u32 = 64u;

struct Params {
  count: u32,    // library fingerprints in this dispatch
  offset: u32,   // first fingerprint (column) of the library buffer
  stride: u32,   // columns in the library buffer
  queries: u32  // number of queries in this dispatch
}

@group(0) @binding(0) var<storage, read> queries: array<u32>;
@group(0) @binding(1) var<storage, read> library: array<u32>;
@group(0) @binding(2) var<storage, read_write> out_inter: array<u32>;
@group(0) @binding(3) var<storage, read_write> out_union: array<u32>;
@group(0) @binding(4) var<uniform> params: Params;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x;
  let q = gid.y;
  if (i >= params.count || q >= params.queries) {
    return;
  }
  let col = params.offset + i;
  var inter = 0u;
  var uni = 0u;
  for (var w = 0u; w < WORDS; w = w + 1u) {
    let a = queries[q * WORDS + w];
    let b = library[w * params.stride + col];
    inter = inter + countOneBits(a & b);
    uni = uni + countOneBits(a | b);
  }
  let slot = q * params.count + i;
  out_inter[slot] = inter;
  out_union[slot] = uni;
}
