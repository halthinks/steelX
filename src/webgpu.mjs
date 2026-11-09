// SPDX-License-Identifier: Apache-2.0
// Offline-capable public surface for the pinned vendored Steel WebGPU core.
// Do NOT re-export upstream loadScene or fetchMesh: those call fetch().
// Robot-model loaders need a separately injected local mesh resolver and are
// withheld until the offline importer is completed and tested.

export { Sim, KERNELS, SceneBuilder, convexHull } from '../vendor/browser/steel-webgpu/src/sim.js';
export { initDevice, UnsupportedError } from '../vendor/browser/steel-webgpu/src/device.js';
export { loadOfflineScene } from './offline-scene.mjs';
