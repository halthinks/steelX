// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadOfflineScene } from '../src/offline-scene.mjs';

const encoder = new TextEncoder();

test('actual vendored WebGPU core imports without a network call or external package', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = () => { throw new Error('unexpected fetch in core module import'); };
  try {
    const api = await import('../src/webgpu.mjs');
    assert.equal(typeof api.Sim.create, 'function');
    assert.equal(typeof api.initDevice, 'function');
    assert.equal(api.loadOfflineScene, loadOfflineScene);
    assert.equal('loadScene' in api, false);
    assert.equal('fetchMesh' in api, false);
  } finally {
    globalThis.fetch = original;
  }
});

function bytes(data) {
  if (typeof data === 'string') return encoder.encode(data);
  if (data instanceof ArrayBuffer) return new Uint8Array(data);
  return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
}

async function digest(data) {
  const hash = await crypto.subtle.digest('SHA-256', bytes(data));
  return Buffer.from(hash).toString('hex');
}

async function sceneInputs(meshRecord = { v: { off: 0, n: 9 }, i: { off: 36, n: 3 } }, meshes = new Map(), sceneDir = '') {
  const json = JSON.stringify({ visuals: [{ mesh: meshRecord }] });
  const bin = new ArrayBuffer(48);
  new Float32Array(bin, 0, 9).set([0, 0, 0, 1, 0, 0, 0, 1, 0]);
  new Uint32Array(bin, 36, 3).set([0, 1, 2]);
  const integrity = new Map([
    [sceneDir ? `${sceneDir}/scene.json` : 'scene.json', await digest(json)],
    [sceneDir ? `${sceneDir}/scene.bin` : 'scene.bin', await digest(bin)],
  ]);
  for (const [path, value] of meshes) integrity.set(path, await digest(value));
  return { json, bin, meshes, integrity, sceneDir };
}

test('decodes an inline Steel WebGPU mesh without fetch or dependencies', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = () => { throw new Error('network access attempted'); };
  try {
    const scene = await loadOfflineScene(await sceneInputs());
    const mesh = scene.mesh(scene.json.visuals[0].mesh);
    assert.deepEqual([...mesh.idx], [0, 1, 2]);
    assert.deepEqual([...mesh.pos], [0, 0, 0, 1, 0, 0, 0, 1, 0]);
    assert.equal(mesh.uv, null);
    assert.equal(scene.base, '');
  } finally {
    globalThis.fetch = original;
  }
});

test('decodes referenced mesh with 16-bit indices, padded UVs, and a borrowed byte slice', async () => {
  const path = 'shared/meshes/mesh.bin';
  const content = new ArrayBuffer(68);
  new Float32Array(content, 0, 9).set([0, 0, 0, 1, 0, 0, 0, 1, 0]);
  new Uint16Array(content, 36, 3).set([2, 1, 0]);
  new Float32Array(content, 44, 6).set([0, 0, 1, 0, 0, 1]);
  const wrapped = new Uint8Array(80);
  wrapped.set(new Uint8Array(content), 4);
  const asset = wrapped.subarray(4, 72); // nonzero byte offset, unrelated trailing bytes
  const record = { file: path, nv: 3, ni: 3, index: 'u16', uv: true };
  const scene = await loadOfflineScene(await sceneInputs(record, new Map([[path, asset]])));
  const mesh = scene.mesh(scene.json.visuals[0].mesh);
  assert.deepEqual([...mesh.idx], [2, 1, 0]);
  assert.deepEqual([...mesh.uv], [0, 0, 1, 0, 0, 1]);
  // Validated data is detached from mutable caller storage.
  asset.fill(0);
  assert.deepEqual([...mesh.idx], [2, 1, 0]);
});

test('resolves authentic upstream ../shared mesh paths only within a declared scene root', async () => {
  const file = 'shared/meshes/00fee148233e297a328d.bin';
  const record = { file: `../${file}`, nv: 0, ni: 0 }; // u32 is the upstream default
  const scene = await loadOfflineScene(await sceneInputs(record, new Map([[file, new Uint8Array()]]), 'bolt_sweep'));
  assert.equal(scene.mesh(record).idx.length, 0);
  const escaping = { ...record, file: `../../${file}` };
  await assert.rejects(loadOfflineScene(await sceneInputs(escaping, new Map([[file, new Uint8Array()]]), 'bolt_sweep')), /unsafe offline asset path/);
});

test('rejects network URLs and unsafe traversal in an asset reference', async () => {
  for (const path of ['https://cdn.example/file.bin', '//host/file.bin', '../up.bin', 'a/../../b.bin',
    '/absolute.bin', 'C:/drive.bin', 'a\\b.bin', 'a//b.bin', 'a/%2e%2e/b.bin', 'a?q=1']) {
    const input = await sceneInputs({ file: path, nv: 0, ni: 0, index: 'u32' });
    await assert.rejects(loadOfflineScene(input), /unsafe offline asset path/, path);
  }
  await assert.rejects(loadOfflineScene(await sceneInputs({ file: 'scene.bin', nv: 0, ni: 0, index: 'u32' })), /reserved offline asset path/);
});

test('rejects missing and unexpected mesh assets and unlisted manifest entries', async () => {
  const path = 'meshes/a.bin';
  const input = await sceneInputs({ file: path, nv: 0, ni: 0, index: 'u32' },
    new Map([[path, new ArrayBuffer(0)]]));
  await assert.rejects(loadOfflineScene({ ...input, meshes: new Map() }), /offline mesh map/);
  await assert.rejects(loadOfflineScene({ ...input, meshes: new Map([...input.meshes, ['extra.bin', new ArrayBuffer(0)]]) }), /offline mesh map/);
  await assert.rejects(loadOfflineScene({ ...input, integrity: new Map([...input.integrity, ['extra.bin', '0'.repeat(64)]]) }), /integrity manifest/);
});

test('rejects tampered scene bytes and mesh bytes before exposing a scene', async () => {
  const input = await sceneInputs();
  const changed = new Uint8Array(input.bin.slice(0));
  changed[0] ^= 0x7f;
  await assert.rejects(loadOfflineScene({ ...input, bin: changed }), /SHA-256 mismatch for scene.bin/);
  const path = 'mesh.bin';
  const withMesh = await sceneInputs({ file: path, nv: 0, ni: 0, index: 'u32' }, new Map([[path, new Uint8Array([1, 2])]]));
  await assert.rejects(loadOfflineScene({ ...withMesh, meshes: new Map([[path, new Uint8Array([3, 4])]]) }), /SHA-256 mismatch for mesh.bin/);
});

test('rejects malformed hashes, binary text, JSON, and non-Map manifests', async () => {
  const input = await sceneInputs();
  await assert.rejects(loadOfflineScene({ ...input, integrity: {} }), /explicit Maps/);
  await assert.rejects(loadOfflineScene({ ...input, bin: 'not binary' }), /binary bytes/);
  await assert.rejects(loadOfflineScene({ ...input, json: 'not json' }), SyntaxError);
  await assert.rejects(loadOfflineScene({ ...input, integrity: new Map([['scene.json', 'invalid'], ['scene.bin', input.integrity.get('scene.bin')]]) }), /invalid SHA-256/);
});

test('rejects misaligned and out-of-bounds typed views before GPU use', async () => {
  const scene = await loadOfflineScene(await sceneInputs());
  assert.throws(() => scene.f32({ off: 1, n: 1 }), /invalid f32/);
  assert.throws(() => scene.u32({ off: 44, n: 2 }), /invalid u32/);
  assert.throws(() => scene.f32({ off: -4, n: 1 }), /invalid f32/);
  assert.throws(() => scene.f32({ off: Number.MAX_SAFE_INTEGER, n: 1 }), /invalid f32/);
  assert.throws(() => scene.f32({ off: 0, n: Infinity }), /invalid f32/);
});

test('rejects truncated referenced meshes, unsupported indices, and undeclared mesh reads', async () => {
  const path = 'meshes/a.bin';
  const record = { file: path, nv: 3, ni: 3, index: 'u16', uv: true };
  const scene = await loadOfflineScene(await sceneInputs(record, new Map([[path, new ArrayBuffer(48)]])));
  assert.throws(() => scene.mesh(record), /invalid mesh UV/);
  assert.throws(() => scene.mesh({ ...record, index: 'u8' }), /unsupported mesh index/);
  assert.throws(() => scene.mesh({ ...record, file: 'meshes/not-allowed.bin' }), /undeclared offline mesh/);
});
