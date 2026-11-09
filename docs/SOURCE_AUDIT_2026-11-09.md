# SteelX pinned-source audit: solver, loader, build, redistribution

Status: **code inspected, release gates open**. This is a review of the **exact pinned upstream trees**, not a benchmark or a claim of production functionality. Every source link below is pinned to the SHA in [`vendor/upstreams.lock.json`](../vendor/upstreams.lock.json).

## Scope and source inventory

| Repository | Pinned revision | Git-tracked blobs | Declared blob bytes | What was inspected |
| --- | --- | ---: | ---: | --- |
| [Newton](https://github.com/newton-physics/newton/tree/2134db9cd0354019061d36a2762f886d59e88306) | `2134db9c` | 1,855 | 47,582,721 | `SolverSteel`, CPU fallback, test modules, Python packaging and asset downloader |
| [Steel WebGPU](https://github.com/skild-ai/steel-webgpu/tree/f2f72c1e99aea7192cf2366eb918e630135afcf9) | `f2f72c1e` | 649 | 41,348,401 | `Sim`, scene/mesh loaders, worker renderer loader, device creation, package metadata and model licenses |
| [Warp](https://github.com/NVIDIA/warp/tree/f2eaed82d8d03b37bf1014cc975954067fefcf16) | `f2eaed82` | 1,217 | 22,629,413 | Python build metadata, CUDA/LLVM license inventory and native tooling |

These counts come from the GitHub recursive Git tree metadata and exclude external transitive dependencies. The **111.6 MB of tracked blob data is not an offline dependency closure**. No Git submodule entries were found in these pinned tree inventories, but importer checks remain mandatory. Git LFS and individual asset rights still require per-file inspection.

## Dynamics and solver coverage: Newton Steel

- [Public solver class](https://github.com/newton-physics/newton/blob/2134db9cd0354019061d36a2762f886d59e88306/newton/_src/solvers/steel/solver_steel.py): `SolverSteel` (line 1351), constructor at line 1837, `notify_model_changed`, `notify_state_changed`, `reset`, observables, and coupling interfaces. Its state depends on the Newton `Model`, collision pipeline, and Warp kernels. The folder is **not** a self-contained importable physics engine.
- [Solver mode validation](https://github.com/newton-physics/newton/blob/2134db9cd0354019061d36a2762f886d59e88306/newton/_src/solvers/steel/solver_steel.py): `serial` and `colored`; articulated response `immediate` or `propagation`. `colored` requires `propagation`. Older `matrix_free`, `split`, and `propagation_colored` spellings carry explicit deprecation behavior; SteelX must **not** treat these aliases as equivalent algorithms or promise old numerical results.
- [CPU fallback](https://github.com/newton-physics/newton/blob/2134db9cd0354019061d36a2762f886d59e88306/newton/_src/solvers/steel/cpu_fallback.py): uses world-serial counterparts for CUDA cooperative matrix-free row kernels, with different floating-point reduction order. The CPU path only supports fixed-normal friction and rejects contact compliance, non-fixed-normal friction, joint friction, and colored sleeping. Torsional contact is also rejected for CPU elsewhere. Therefore the initial CPU product **must be a capability-limited target**, not a feature-complete CUDA replacement.
- [CPU/GPU comparison test](https://github.com/newton-physics/newton/blob/2134db9cd0354019061d36a2762f886d59e88306/newton/tests/steel/test_cpu_fallback.py): contains finite CPU rollout tests and CUDA comparison with explicit tolerance (`atol=2e-4` for positions in one case). This is upstream test logic, **not an independently rerun SteelX qualification result**.
- [Determinism tests](https://github.com/newton-physics/newton/blob/2134db9cd0354019061d36a2762f886d59e88306/newton/tests/steel/test_determinism.py): explicitly set `SolverSteel(..., deterministic=RUN_TO_RUN, ...)` and request deterministic collision when not using warm-start matching. Tests include repeated state hashes and CUDA graph scenarios. Do not infer cross-CPU/GPU bitwise identity or default deterministic behavior from these targeted tests.
- The [Newton solver test directory](https://github.com/newton-physics/newton/tree/2134db9cd0354019061d36a2762f886d59e88306/newton/tests/steel) includes articulation, capacity, contact, reduction, compliance, warm start, joint drives and limits, friction, propagation, sleeping, torsion and coupled cases. Each supported subset needs an actual pinned-source test matrix; unsupported physics gets a clear diagnostic.

## WebGPU API and network dependency paths

- [Simulation entry point](https://github.com/skild-ai/steel-webgpu/blob/f2f72c1e99aea7192cf2366eb918e630135afcf9/packages/steel-webgpu/src/sim.js): exported `Sim(device, scene, opts)` and `Sim.create` take an already-decoded scene. Simulation itself is not a hosted API. `loadScene(base)` is separately responsible for fetching `scene.json`, `scene.bin`, and referenced shared meshes (lines 35–60).
- [Scene and robot importers](https://github.com/skild-ai/steel-webgpu/blob/f2f72c1e99aea7192cf2366eb918e630135afcf9/packages/steel-webgpu/src/loaders.js): `fetchMesh` defaults to network `fetch`; both `loadURDF` and `loadMJCF` accept injected `loadMesh` callbacks and `baseUrl`. The default path is **not** disconnected-safe. SteelX must supply path-confined in-memory/local resolvers before exposing these importers. USDA is a text parser with explicitly incomplete USD features (references, payloads, variants and time samples are not resolved).
- [Viewer scene worker](https://github.com/skild-ai/steel-webgpu/blob/f2f72c1e99aea7192cf2366eb918e630135afcf9/packages/steel-webgpu/src/three/sceneLoader.ts): its `geometryWorker` independently calls `fetch` for scene and meshes, while its non-worker fallback calls `loadScene`; a GPU solver with an offline scene loader does **not** make the interactive viewer offline by itself. Both branches need byte-supplied entry points and tests.
- [Browser device initialization](https://github.com/skild-ai/steel-webgpu/blob/f2f72c1e99aea7192cf2366eb918e630135afcf9/packages/steel-webgpu/src/device.js): requires `navigator.gpu`, requests an adapter and device with GPU resource limits, has a subgroup fallback, and surfaces absence through `UnsupportedError`. There is no JavaScript CPU physics fallback in this API. A browser without usable WebGPU is **unsupported** for simulation; the native Newton CPU target is a different implementation.
- [Dependency metadata](https://github.com/skild-ai/steel-webgpu/blob/f2f72c1e99aea7192cf2366eb918e630135afcf9/packages/steel-webgpu/package.json): optional peers include `react`, `three`, `@react-three/fiber`, `typegpu`; the repository root uses `bun@1.3.14`, `vite-plus@1.5.0`, TypeScript 7.0.2 and a committed `bun.lock`. An engine-only browser bundle should avoid optional viewer frameworks if unused; the full viewer has a separately audited dependency closure.

### SteelX implementation now available

[`src/offline-scene.mjs`](../src/offline-scene.mjs) implements a **network-free, SHA-256-checked decoder** for the pinned `loadScene` scene object shape, supplying the same `{json, bin, f32, u32, mesh, base}` fields to `Sim`. It accepts byte arrays and a manifest, requires an exact referenced mesh set, rejects URLs and traversal **outside the logical asset root**, and detects corrupted or truncated asset reads. The pinned `bolt_sweep` scene uses references such as `../shared/meshes/*.bin` from its own directory, which the adapter correctly resolves *inside* the bundle. `tests/offline-scene.test.mjs` uses Node's built-in test runner with no npm packages and verifies this adapter without `fetch`. This does **not** integrate the complete WebGPU engine or worker viewer yet; release remains blocked.

## Offline build graph: known mandatory closures

| Target | Code-backed dependency or risk | Release consequence |
| --- | --- | --- |
| Newton Python | [`pyproject.toml`](https://github.com/newton-physics/newton/blob/2134db9cd0354019061d36a2762f886d59e88306/pyproject.toml) requires `uv_build>=0.11.0` as build backend and runtime `warp-lang>=1.17.0`. `tool.uv.sources` configures a separate NVIDIA index for Warp. | Pin real per-platform compatible versions; place build backends, wheels and all transitives in offline wheelhouse. Force `--no-index`; don't silently fetch from NVIDIA/PyPI. |
| Newton imports/viewers | Importer extras include HTTP `requests`, `scipy`, `trimesh`, USD libraries and robotics URI resolvers; example/viewer extras include `GitPython`, `pyglet`, `imgui_bundle`. | Deliberately select a minimal CPU capability set; asset imports, viewer and extra formats each have separate dependency/license gates. |
| Newton assets | [`download_assets.py`](https://github.com/newton-physics/newton/blob/2134db9cd0354019061d36a2762f886d59e88306/newton/_src/utils/download_assets.py) contains pinned Git download logic for `newton-assets` and MuJoCo Menagerie. | Disable implicit download execution and supply local, independently licensed assets. The asset SHAs are recorded in `vendor/asset-sources.lock.json`. |
| Warp native | [`pyproject.toml`](https://github.com/NVIDIA/warp/blob/f2eaed82d8d03b37bf1014cc975954067fefcf16/pyproject.toml) uses `setuptools`, `build`, `wheel`, and `numpy`; [`build_lib.py`](https://github.com/NVIDIA/warp/blob/f2eaed82d8d03b37bf1014cc975954067fefcf16/build_lib.py) plus `tools/cmake`, `tools/packman`, LLVM and CUDA configurations are separate build inputs. | A Python `warp` source checkout alone cannot produce every native runtime binary offline. Audit/offline-bundle platform toolchains or specify lawful offline prerequisites. |
| WebGPU JS | Root `bun.lock`, `package.json`, `vite-plus`, `@voidzero-dev/vite-plus-core` alias and package peers. | An offline JS release needs actual bundled JS and build tools; a lockfile plus source tree is insufficient. |

## License and commercial release decisions

| Material | Current source-backed classification | Decision |
| --- | --- | --- |
| Newton, Warp, Steel WebGPU source | Each project declares Apache-2.0 | **Candidate for vendored source** with original license, notices, attribution and modified-file notices retained. Not an approval of all nested assets/binaries. |
| WebGPU robot scene models | [Root LICENSE](https://github.com/skild-ai/steel-webgpu/blob/f2f72c1e99aea7192cf2366eb918e630135afcf9/LICENSE.md) lists UR10e/UR5e, Kinova, Unitree G1 under BSD-3-Clause-related grants and Wuji Hand under MIT | **Hold model-by-model release** until provenance and required copyright/notices are included in scene bundles. |
| Newton examples/test assets | Includes `newton/licenses/CC-BY-4.0.txt`, fonts, sample USD/URDF and `.pt` policy data | **Hold assets independently**; don't assume source Apache-2.0 covers all files. |
| Warp native toolchains | Includes separate `licenses/cuda-LICENSE.txt`, `nvrtc`, `llvm`, `libmathdx`, etc. | **Hold redistributable binaries and SDK** pending exact artifact/license review; server operator may separately install lawful offline prerequisites. |
| Private TextPCB/VibeMechanica integration | Served-only engineering worker software, not part of upstream Apache licensed engine | **Keep server-side** by default; don't bundle proprietary code or credentials in the optional public browser assets. |

## Explicit next acceptance tests (not yet passed)

1. Import the full exact upstream source snapshots plus their license/NOTICE records. `verify_vendor.py` must prove file inventory and hashes.
2. Build a minimal CPU-only Newton+Warp wheelhouse, then install it in a clean, network-denied environment with empty caches and execute pinned Steel CPU tests. Record supported modes and exceptions.
3. Build a framework-minimal WebGPU JS bundle from vendored sources, feed `loadOfflineScene` directly into `Sim.create`, and run the actual GPU simulation with outbound network blocked.
4. Modify the worker scene renderer and `loadURDF`/`loadMJCF` local-mesh adapters; verify **all** `fetch` routes stay unreachable in offline mode.
5. Validate scene hash/typed-array decoder against authentic pinned WebGPU scene files; add benchmarks and numerical comparisons across hardware/driver versions with explicit tolerances.
6. Generate per-bundle SPDX SBOM, license/NOTICE aggregation, binary provenance, and release evidence. Only then lift the strict offline gate.

Any browser claim also requires a verified supported-browser/WebGPU matrix. None of this audit reproduces launch throughput claims or proves physical accuracy.
