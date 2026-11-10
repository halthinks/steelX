// SPDX-License-Identifier: Apache-2.0
// Offline-capable public surface for the pinned vendored Steel WebGPU core.
// Do NOT re-export upstream loadScene or fetchMesh: those call fetch().
// Raw upstream robot-model loaders remain withheld. Only wrappers that force
// SteelX's local mesh callback are exported; browser XML tests remain pending.

export { Sim, KERNELS, SceneBuilder, convexHull } from '../vendor/browser/steel-webgpu/src/sim.js';
export { initDevice, UnsupportedError } from '../vendor/browser/steel-webgpu/src/device.js';
export { loadOfflineScene } from './offline-scene.mjs';
export { createOfflineMeshResolver, loadOfflineURDF, loadOfflineMJCF } from './offline-models.mjs';
