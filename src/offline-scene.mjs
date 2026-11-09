// SPDX-License-Identifier: Apache-2.0
// steelX adapter for the scene layout consumed by pinned Steel WebGPU's Sim.
// This is intentionally separate from upstream files so modifications and
// copyright attribution remain explicit.

const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', { fatal: true });
const HEX_SHA256 = /^[0-9a-f]{64}$/i;

function bytes(value, label) {
  if (typeof value === 'string') return encoder.encode(value);
  if (value instanceof ArrayBuffer) return new Uint8Array(value);
  if (ArrayBuffer.isView(value)) {
    return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
  }
  throw new TypeError(`${label} must be UTF-8 text, ArrayBuffer, or bytes`);
}

function localAssetPath(path, sceneDir = '') {
  if (typeof path !== 'string' || !path || path.includes('\\') || /[\u0000-\u001f]/.test(path)) {
    throw new Error(`unsafe offline asset path: ${String(path)}`);
  }
  // Paths are resolved purely inside a named logical asset root, not against
  // the browser URL or the host filesystem. Parent segments are permitted
  // only while they remain inside that root: upstream demos refer to shared
  // geometry as ../shared/meshes/*.bin from sceneDir='bolt_sweep'.
  if (path.startsWith('/') || /[:?#%]/.test(path)) {
    throw new Error(`unsafe offline asset path: ${path}`);
  }
  const parts = sceneDir ? sceneDir.split('/') : [];
  for (const segment of path.split('/')) {
    if (!segment || segment === '.') throw new Error(`unsafe offline asset path: ${path}`);
    if (segment === '..') {
      if (!parts.length) throw new Error(`unsafe offline asset path: ${path}`);
      parts.pop();
    } else {
      parts.push(segment);
    }
  }
  if (!parts.length) throw new Error(`unsafe offline asset path: ${path}`);
  return parts.join('/');
}

function exactSha(value, path) {
  if (typeof value !== 'string' || !HEX_SHA256.test(value)) {
    throw new Error(`missing or invalid SHA-256 for ${path}`);
  }
  return value.toLowerCase();
}

async function verify(bytesValue, expected, path) {
  if (!globalThis.crypto?.subtle) throw new Error('Web Crypto SHA-256 is required for offline asset integrity');
  // loadOfflineScene already snapshots every input into owned Uint8Arrays.
  const hash = await globalThis.crypto.subtle.digest('SHA-256', bytesValue);
  const actual = [...new Uint8Array(hash)].map(x => x.toString(16).padStart(2, '0')).join('');
  if (actual !== exactSha(expected, path)) throw new Error(`SHA-256 mismatch for ${path}`);
}

function typedView(buffer, record, Type, label) {
  const off = record?.off;
  const count = record?.n;
  if (!Number.isSafeInteger(off) || off < 0 || off % Type.BYTES_PER_ELEMENT !== 0 ||
      !Number.isSafeInteger(count) || count < 0 || count > (buffer.byteLength - off) / Type.BYTES_PER_ELEMENT) {
    throw new RangeError(`invalid ${label} buffer view`);
  }
  return new Type(buffer, off, count);
}

/**
 * Decode a Steel WebGPU scene without fetch(), service workers, filesystems,
 * package registries or any external runtime dependencies.
 *
 * @param {object} input
 * @param {string|ArrayBuffer|ArrayBufferView} input.json - Exact scene.json bytes.
 * @param {ArrayBuffer|ArrayBufferView} input.bin - Exact scene.bin bytes.
 * @param {Map<string,ArrayBuffer|ArrayBufferView>} input.meshes - Local relative mesh keys and bytes.
 * @param {Map<string,string>} input.integrity - SHA-256 for scene.json, scene.bin, and each mesh.
 * @param {string} [input.sceneDir=''] - Scene folder relative to a logical bundle root.
 * @returns {Promise<object>} Scene compatible with pinned Steel WebGPU's Sim.
 */
export async function loadOfflineScene({ json, bin, meshes = new Map(), integrity, sceneDir = '' } = {}) {
  if (!(meshes instanceof Map) || !(integrity instanceof Map)) {
    throw new TypeError('meshes and integrity must be explicit Maps');
  }
  if (typeof sceneDir !== 'string' || (sceneDir && localAssetPath(sceneDir) !== sceneDir)) {
    throw new Error('invalid offline scene directory');
  }
  const jsonPath = sceneDir ? `${sceneDir}/scene.json` : 'scene.json';
  const binPath = sceneDir ? `${sceneDir}/scene.bin` : 'scene.bin';
  const jsonBytes = Uint8Array.from(bytes(json, 'scene.json'));
  if (typeof bin === 'string') throw new TypeError('scene.bin must contain binary bytes');
  const binBytes = Uint8Array.from(bytes(bin, 'scene.bin'));
  const metadata = JSON.parse(decoder.decode(jsonBytes));
  if (!metadata || typeof metadata !== 'object' || !Array.isArray(metadata.visuals)) {
    throw new Error('scene.json must contain a visuals array');
  }

  const needed = new Set([jsonPath, binPath]);
  for (const visual of metadata.visuals) {
    if (visual?.mesh?.file != null) {
      const path = localAssetPath(visual.mesh.file, sceneDir);
      if (path === jsonPath || path === binPath) throw new Error(`reserved offline asset path: ${path}`);
      needed.add(path);
    }
  }
  if (integrity.size !== needed.size || [...integrity.keys()].some(path => !needed.has(path))) {
    throw new Error('offline integrity manifest must enumerate exactly the scene files');
  }
  if (meshes.size !== needed.size - 2 || [...meshes.keys()].some(path => localAssetPath(path) !== path || !needed.has(path))) {
    throw new Error('offline mesh map must contain exactly the referenced local assets');
  }
  for (const path of needed) {
    if (path !== jsonPath && path !== binPath && !meshes.has(path)) {
      throw new Error(`missing offline mesh asset: ${path}`);
    }
  }

  // Snapshot all caller-provided buffers before the first await: hashes must
  // cover exactly the bytes the GPU will later consume, even if a caller
  // mutates the original arrays during asynchronous digest operations.
  const meshBytes = new Map([...meshes].map(([path, value]) => [path, Uint8Array.from(bytes(value, path))]));
  await Promise.all([
    verify(jsonBytes, integrity.get(jsonPath), jsonPath),
    verify(binBytes, integrity.get(binPath), binPath),
    ...[...needed].filter(path => path !== jsonPath && path !== binPath)
      .map(path => verify(meshBytes.get(path), integrity.get(path), path)),
  ]);

  // Copy exact bytes so borrowed Buffer slices, offsets, later caller mutation,
  // and SharedArrayBuffer ownership cannot change the validated scene.
  const binary = binBytes.buffer;
  const files = new Map([...meshBytes].map(([path, value]) => [path, value.buffer]));
  const f32 = record => typedView(binary, record, Float32Array, 'f32');
  const u32 = record => typedView(binary, record, Uint32Array, 'u32');

  const mesh = record => {
    if (!record || typeof record !== 'object') throw new Error('invalid mesh record');
    if (!record.file) {
      return { pos: f32(record.v), idx: u32(record.i), uv: record.uv ? f32(record.uv) : null };
    }
    const data = files.get(localAssetPath(record.file, sceneDir));
    if (!data) throw new Error(`undeclared offline mesh: ${record.file}`);
    const nv = record.nv;
    const ni = record.ni;
    if (!Number.isSafeInteger(nv) || nv < 0 || !Number.isSafeInteger(ni) || ni < 0) {
      throw new RangeError('invalid offline mesh dimensions');
    }
    // The pinned upstream decoder defaults omitted index formats to u32.
    const indexFormat = record.index ?? 'u32';
    if (indexFormat !== 'u16' && indexFormat !== 'u32') {
      throw new Error('unsupported mesh index format');
    }
    const pos = typedView(data, { off: 0, n: nv * 3 }, Float32Array, 'mesh positions');
    const io = nv * 12;
    const Index = indexFormat === 'u16' ? Uint16Array : Uint32Array;
    const idx = typedView(data, { off: io, n: ni }, Index, 'mesh indices');
    const uo = io + Math.ceil((ni * Index.BYTES_PER_ELEMENT) / 4) * 4;
    const uv = record.uv ? typedView(data, { off: uo, n: nv * 2 }, Float32Array, 'mesh UV') : null;
    return { pos, idx, uv };
  };

  // base is deliberately not a remote URL; the caller already provided assets.
  return { json: metadata, bin: binary, f32, u32, mesh, base: '' };
}
