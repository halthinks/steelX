# First source-level audit findings

Date: 2026-11-09. Scope: initial targeted inspection, **not** a completed numerical or architecture audit. Links are immutable commit URLs matching `vendor/upstreams.lock.json`. All findings are open until addressed and retested in steelX.

## Findings affecting the offline release

| ID | Observed source behavior | Consequence / required fix |
| --- | --- | --- |
| SX-A01 | WebGPU `loadScene(base)` fetches `scene.json`, `scene.bin`, and content-addressed visual mesh files using `fetch`. | Vendoring code alone does not make scene load offline. Add a strict local-package or in-memory loader API, reject remote schemes in offline mode, and test disconnected render/import paths. |
| SX-A02 | WebGPU `fetchMesh(url)` calls `fetch(url)`; `package://` is translated to a URL relative to a base. | Vendor mesh assets, constrain package roots, support provided bytes/File/Blob or local bundle resources, and reject unexpected network/path traversal. |
| SX-A03 | The WebGPU React robot loader and viewer/demo asset index also call `fetch`. | Audit every entry point, not just the simulation core. Bundle every selected robot/demo; no CDN or online fallback. |
| SX-A04 | Newton's asset loader pins external `newton-assets` and `mujoco_menagerie` repositories and may use git downloads/cache. | Copy all **used** and legally redistributable model dependencies into the offline bundle. Replace network download paths with local asset resolution; test on empty caches. Track model-by-model licenses. |
| SX-A05 | Native Steel CPU fallback explicitly rejects compliance, non-`fixed_normal` friction modes, joint friction, and sleeping with colored solve mode. | Do not advertise CPU/GPU feature parity without work. Create a capability matrix, deterministic unsupported-feature errors, and cross-device numerical tests. |
| SX-A06 | WebGPU solver rejects some joint types/solver options and limits the articulation count for a workgroup. | Record exact supported model/options matrix and tests before using browser/CPU/GPU interchangeably. |
| SX-A07 | Newton's Python project declares a mandatory `warp-lang>=1.17.0` and many optional sim/importer/example dependencies; WebGPU has a Bun lockfile and package-specific JS peers. | Source copies are not dependency-complete. Lock and vendor exact transitive versions, install/build toolchains and native platform artifacts per target, then run zero-network clean-cache builds. |

## Exact source evidence

- **SX-A01:** [`sim.js` loading `scene.json` and `scene.bin`](https://github.com/skild-ai/steel-webgpu/blob/f2f72c1e99aea7192cf2366eb918e630135afcf9/packages/steel-webgpu/src/sim.js#L33-L50).
- **SX-A02:** [`loaders.js` `fetchMesh` and `package://` resolution](https://github.com/skild-ai/steel-webgpu/blob/f2f72c1e99aea7192cf2366eb918e630135afcf9/packages/steel-webgpu/src/loaders.js#L67-L88).
- **SX-A03:** [React robots loader](https://github.com/skild-ai/steel-webgpu/blob/f2f72c1e99aea7192cf2366eb918e630135afcf9/packages/steel-webgpu/src/react/robots.tsx), [viewer](https://github.com/skild-ai/steel-webgpu/blob/f2f72c1e99aea7192cf2366eb918e630135afcf9/apps/viewer/src/demo/App.tsx).
- **SX-A04:** [Newton pinned external assets and downloader](https://github.com/newton-physics/newton/blob/2134db9cd0354019061d36a2762f886d59e88306/newton/_src/utils/download_assets.py#L20-L29). Model licenses are individual, as described by [Newton assets](https://github.com/newton-physics/newton-assets/blob/f8fb7abcbeba2318814a74f3eeb02780ad7925d6/README.md) and [Menagerie](https://github.com/google-deepmind/mujoco_menagerie/blob/da76818e269b82289eba39808e2fb91d679d6994/README.md).
- **SX-A05:** [`cpu_fallback.py` runtime rejection](https://github.com/newton-physics/newton/blob/2134db9cd0354019061d36a2762f886d59e88306/newton/_src/solvers/steel/cpu_fallback.py#L31-L50).
- **SX-A06:** [`sim.js` joint and articulation constraints](https://github.com/skild-ai/steel-webgpu/blob/f2f72c1e99aea7192cf2366eb918e630135afcf9/packages/steel-webgpu/src/sim.js#L120-L170) and [solver-option checks](https://github.com/skild-ai/steel-webgpu/blob/f2f72c1e99aea7192cf2366eb918e630135afcf9/packages/steel-webgpu/src/sim.js#L407-L420).
- **SX-A07:** [Newton Python dependencies](https://github.com/newton-physics/newton/blob/2134db9cd0354019061d36a2762f886d59e88306/pyproject.toml) and [WebGPU package lock](https://github.com/skild-ai/steel-webgpu/blob/f2f72c1e99aea7192cf2366eb918e630135afcf9/bun.lock).

## Audit tasks still required

Read actual solver kernels and test assertions; derive contact/friction/constraint equations; compare CPU, CUDA and WebGPU numerical behavior on identical source-bound fixtures; build an SPDX license matrix of all direct/transitive dependencies; test artifact provenance, binary redistribution, performance and driver requirements. The 3.8×/13× performance claims have **not** been reproduced here.
