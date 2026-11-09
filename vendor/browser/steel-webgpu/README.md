# Pinned Steel WebGPU engine-only source slice

**Origin:** [skild-ai/steel-webgpu](https://github.com/skild-ai/steel-webgpu/tree/f2f72c1e99aea7192cf2366eb918e630135afcf9)

**Revision:** `f2f72c1e99aea7192cf2366eb918e630135afcf9` (the revision in the main upstream lock). Original `src/*.js` and license files are copied **unchanged**; their upstream Git blob SHA-1 and SHA-256 are recorded in [`PROVENANCE.json`](PROVENANCE.json). Check with `python tools/verify_webgpu_slice.py` from the SteelX root.

**License:** Apache-2.0. Preserve [`LICENSE.md`](LICENSE.md) with the bundled source. The copied upstream [root license and model attribution](UPSTREAM_ROOT_LICENSE.md) is also present for provenance; **model files themselves are not yet included in this slice**. `package.json`, this README, the manifest, and SteelX `src/` adapters are SteelX-authored packaging material, separate from the unchanged upstream files.

This slice includes `Sim`, the WGSL kernel strings, scene builder, browser device initialization, and upstream scene/robot parsing sources. Their ES-module imports are confined to these included files. It **does not** include:

- the full upstream source tree, React/Three viewer, worker scene-loader implementation, or demo models;
- a CPU-only JavaScript physics engine (WebGPU hardware and browser support are required for simulation);
- a prebuilt WebGPU application, numerical qualification, or a disconnected-browser release;
- vendored Newton/Warp native source, binary dependencies, or offline build toolchains.

The raw upstream `loadScene` and `fetchMesh` exports use `fetch`; do not expose them as offline entry points. Use [`src/webgpu.mjs`](../../../src/webgpu.mjs) for the restricted SteelX API, plus [`loadOfflineScene`](../../../src/offline-scene.mjs) for already-loaded SHA-256-bound scene buffers. An actual GPU smoke test in a network-denied browser is still a required release gate.

Do not run npm or any package manager here. This source slice has **no required external npm dependency for its core ES modules**; any later viewer and build-tool additions must have independently vendored, licensed dependencies.
