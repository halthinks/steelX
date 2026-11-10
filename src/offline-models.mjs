// SPDX-License-Identifier: Apache-2.0
// Network-denied mesh resolution for the pinned Steel WebGPU URDF/MJCF loaders.
// Upstream accepts loadMesh callbacks; supplying one avoids its fetchMesh API.

import { parseSTL, parseOBJ, loadURDF, loadMJCF } from '../vendor/browser/steel-webgpu/src/loaders.js';

const PREFIX = '/_steelx_assets/';
const ORIGIN = 'https://steelx.invalid'; // URL resolver only, never contacted.
const HEX = /^[a-f0-9]{64}$/i;
const decoder = new TextDecoder('utf-8', { fatal: true });

function canonical(path, allowEmpty = false) {
  if (typeof path !== 'string' || (!path && !allowEmpty) || path.startsWith('/') ||
      /[\\:?#%\u0000-\u001f]/.test(path) ||
      (path && path.split('/').some(part => !part || part === '.' || part === '..'))) {
    throw new Error(`unsafe offline model path: ${String(path)}`);
  }
  return path;
}

function copyBytes(value, name) {
  if (value instanceof ArrayBuffer) return new Uint8Array(value.slice(0));
  if (ArrayBuffer.isView(value)) {
    return Uint8Array.from(new Uint8Array(value.buffer, value.byteOffset, value.byteLength));
  }
  throw new TypeError(`offline asset ${name} must be binary bytes`);
}

async function sha256(input) {
  if (!globalThis.crypto?.subtle) throw new Error('Web Crypto SHA-256 is required for offline mesh integrity');
  const digest = await globalThis.crypto.subtle.digest('SHA-256', input);
  return [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2, '0')).join('');
}

/**
 * Build an audited local mesh callback for the real pinned WebGPU importers.
 * The synthetic URL authority is only a path namespace: no fetch is used.
 *
 * @param {object} input
 * @param {string} [input.baseDir=''] - Model's folder within the logical root.
 * @param {Map<string,ArrayBuffer|ArrayBufferView>} input.files - STL/OBJ content by root-relative path.
 * @param {Map<string,string>} input.integrity - Exact file SHA-256 hashes.
 * @param {Map<string,string>} [input.packages] - ROS package names to local root-relative folders.
 */
export async function createOfflineMeshResolver({ baseDir = '', files, integrity, packages = new Map() } = {}) {
  canonical(baseDir, true);
  if (!(files instanceof Map) || !(integrity instanceof Map) || !(packages instanceof Map)) {
    throw new TypeError('files, integrity and packages must be explicit Maps');
  }
  if (files.size !== integrity.size || [...integrity.keys()].some(path => !files.has(path))) {
    throw new Error('offline model integrity must enumerate exactly the supplied files');
  }
  const owned = new Map();
  const expectedHashes = new Map();
  for (const [path, value] of files) {
    canonical(path);
    if (!/\.(obj|stl)$/i.test(path)) throw new Error(`unsupported offline model mesh: ${path}`);
    const expected = integrity.get(path);
    if (typeof expected !== 'string' || !HEX.test(expected)) throw new Error(`invalid SHA-256 for ${path}`);
    expectedHashes.set(path, expected.toLowerCase());
    owned.set(path, copyBytes(value, path));
  }
  await Promise.all([...owned].map(async ([path, value]) => {
    if (await sha256(value) !== expectedHashes.get(path)) throw new Error(`SHA-256 mismatch for ${path}`);
  }));

  const baseUrl = `${ORIGIN}${PREFIX}${baseDir ? `${baseDir}/` : ''}`;
  const packageUrls = Object.create(null);
  for (const [name, dir] of packages) {
    if (typeof name !== 'string' || !/^[a-zA-Z][a-zA-Z0-9_-]*$/.test(name)) {
      throw new Error(`invalid local ROS package name: ${String(name)}`);
    }
    canonical(dir, true);
    packageUrls[name] = `${ORIGIN}${PREFIX}${dir ? `${dir}/` : ''}`;
  }

  const loadMesh = async url => {
    if (typeof url !== 'string' || /[%\\\u0000-\u001f]/.test(url)) {
      throw new Error(`offline model URL escapes asset root: ${String(url)}`);
    }
    let parsed;
    try {
      parsed = new URL(url, baseUrl);
    } catch {
      throw new Error(`invalid offline model URL: ${String(url)}`);
    }
    if (parsed.origin !== ORIGIN || !parsed.pathname.startsWith(PREFIX) ||
        parsed.search || parsed.hash || parsed.username || parsed.password || parsed.pathname.includes('%')) {
      throw new Error(`offline model URL escapes asset root: ${String(url)}`);
    }
    const path = canonical(parsed.pathname.slice(PREFIX.length));
    const content = owned.get(path);
    if (!content) throw new Error(`missing local model mesh: ${path}`);
    const mesh = path.toLowerCase().endsWith('.stl') ? parseSTL(content) : parseOBJ(decoder.decode(content));
    const v = mesh.vertices, i = mesh.indices;
    let invalid = v.length < 9 || v.length % 3 !== 0 || i.length % 3 !== 0;
    for (const x of v) invalid ||= !Number.isFinite(x);
    for (const x of i) invalid ||= !Number.isSafeInteger(x) || x >= v.length / 3;
    if (invalid) {
      throw new Error(`invalid local model mesh geometry: ${path}`);
    }
    return mesh;
  };
  return { baseUrl, packages: packageUrls, loadMesh };
}

function importOptions(value, allowed) {
  if (value == null) return {};
  if (typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(key => !allowed.includes(key))) {
    throw new Error('unsupported offline model import option');
  }
  return { ...value };
}

/** Import text URDF using a caller-supplied, source-bound local mesh archive. */
export async function loadOfflineURDF(builder, text, { modelOptions, ...input } = {}) {
  const extra = importOptions(modelOptions, ['xform', 'floating', 'density', 'material']);
  const { baseUrl, packages, loadMesh } = await createOfflineMeshResolver(input);
  return loadURDF(builder, text, { ...extra, baseUrl, packages, loadMesh });
}

/** Import text MJCF using a caller-supplied, source-bound local mesh archive. */
export async function loadOfflineMJCF(builder, text, { modelOptions, ...input } = {}) {
  const extra = importOptions(modelOptions, ['xform', 'material']);
  const { baseUrl, loadMesh } = await createOfflineMeshResolver(input);
  return loadMJCF(builder, text, { ...extra, baseUrl, loadMesh });
}
