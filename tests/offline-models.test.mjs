// SPDX-License-Identifier: Apache-2.0
import test from 'node:test';
import assert from 'node:assert/strict';
import { createOfflineMeshResolver, loadOfflineURDF, loadOfflineMJCF } from '../src/offline-models.mjs';

const obj = new TextEncoder().encode('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n');
const FILE = 'robots/meshes/triangle.obj';

async function hash(value) {
  const bytes = value instanceof ArrayBuffer ? new Uint8Array(value) : value;
  return Buffer.from(await crypto.subtle.digest('SHA-256', bytes)).toString('hex');
}

async function input(files = new Map([[FILE, obj]]), baseDir = 'robots/urdf') {
  return {
    baseDir,
    files,
    integrity: new Map(await Promise.all([...files].map(async ([p, content]) => [p, await hash(content)]))),
  };
}

test('resolves genuine OBJ meshes from a local robot directory with zero fetch', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = () => { throw new Error('network requested'); };
  try {
    const borrowed = Uint8Array.from(obj);
    const local = await createOfflineMeshResolver(await input(new Map([[FILE, borrowed]])));
    const mesh = await local.loadMesh(new URL('../meshes/triangle.obj', local.baseUrl).href);
    assert.deepEqual([...mesh.vertices], [0, 0, 0, 1, 0, 0, 0, 1, 0]);
    assert.deepEqual([...mesh.indices], [0, 1, 2]);
    assert.equal(local.baseUrl, 'https://steelx.invalid/_steelx_assets/robots/urdf/');
    // Mutating the caller's bytes cannot change what was authenticated.
    borrowed[0] ^= 0xff;
    assert.deepEqual([...((await local.loadMesh('../meshes/triangle.obj')).indices)], [0, 1, 2]);
  } finally {
    globalThis.fetch = original;
  }
});

test('resolves valid packed binary STL geometry without a download', async () => {
  const stl = new ArrayBuffer(84 + 50);
  const data = new DataView(stl);
  data.setUint32(80, 1, true);
  for (const [k, v] of [0, 0, 0, 1, 0, 0, 0, 1, 0].entries()) data.setFloat32(96 + 4 * k, v, true);
  const path = 'robots/meshes/triangle.stl';
  const local = await createOfflineMeshResolver(await input(new Map([[path, stl]])));
  const mesh = await local.loadMesh('../meshes/triangle.stl');
  assert.deepEqual([...mesh.indices], [0, 1, 2]);
  assert.deepEqual([...mesh.vertices], [0, 0, 0, 1, 0, 0, 0, 1, 0]);
});

test('rejects remote, file, data and root-escaping mesh URLs', async () => {
  const local = await createOfflineMeshResolver(await input());
  for (const url of ['https://cdn.example/mesh.obj', 'file:///tmp/mesh.obj', 'data:text/plain,a',
    '//other.example/mesh.obj', '../../../../../../secret.obj',
    'https://steelx.invalid/_steelx_assets/robots/meshes/triangle.obj?token=1',
    'https://steelx.invalid/_steelx_assets/robots/meshes/%2e%2e/triangle.obj']) {
    await assert.rejects(local.loadMesh(url), /offline model URL escapes asset root|missing local model mesh/, url);
  }
});

test('requires complete byte integrity and exact mesh inventory', async () => {
  const good = await input();
  await assert.rejects(createOfflineMeshResolver({ ...good, files: new Map() }), /integrity must enumerate/);
  await assert.rejects(createOfflineMeshResolver({ ...good, integrity: new Map() }), /integrity must enumerate/);
  await assert.rejects(createOfflineMeshResolver({ ...good, files: new Map([[FILE, new Uint8Array([1])]]) }), /SHA-256 mismatch/);
  await assert.rejects(createOfflineMeshResolver({ ...good, integrity: new Map([[FILE, 'invalid']]) }), /invalid SHA-256/);
});

test('requires root-confined canonical source keys and local package mappings', async () => {
  for (const bad of ['../escape.obj', 'robots/../../escape.obj', '/root/file.obj',
    'https://example.org/file.obj', 'robots\\bad.obj', 'robots/%2e%2e/bad.obj']) {
    await assert.rejects(createOfflineMeshResolver(await input(new Map([[bad, obj]]))), /unsafe offline model path/, bad);
  }
  const local = await createOfflineMeshResolver({
    ...(await input()),
    packages: new Map([['my_robot', 'robots']]),
  });
  assert.equal(local.packages.my_robot, 'https://steelx.invalid/_steelx_assets/robots/');
  await assert.rejects(createOfflineMeshResolver({ ...(await input()), packages: new Map([['../../bad', 'robots']]) }), /invalid local ROS package name/);
});

test('rejects malformed and empty mesh geometry without contacting anything', async () => {
  const bad = new TextEncoder().encode('v NaN 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n');
  const local = await createOfflineMeshResolver(await input(new Map([[FILE, bad]])));
  await assert.rejects(local.loadMesh('../meshes/triangle.obj'), /invalid local model mesh geometry/);
  const noFaces = await createOfflineMeshResolver(await input(new Map([[FILE, new Uint8Array()]])));
  await assert.rejects(noFaces.loadMesh('../meshes/triangle.obj'), /invalid local model mesh geometry/);
});

test('model wrapper options cannot replace or bypass the local mesh callback', async () => {
  await assert.rejects(loadOfflineURDF({}, '<robot/>', {
    ...(await input()), modelOptions: { loadMesh: () => fetch('https://example.org/mesh') },
  }), /unsupported offline model import option/);
  await assert.rejects(loadOfflineMJCF({}, '<mujoco/>', {
    ...(await input()), modelOptions: { baseUrl: 'https://example.org' },
  }), /unsupported offline model import option/);
});
