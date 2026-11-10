# steelX offline and vendoring contract

Status: **required architecture, NOT IMPLEMENTED/VERIFIED** (2026-11-09).

## Non-negotiable requirements

1. steelX vendors the complete source required by its supported physics-engine functionality. No git submodules, runtime fetchers, CDN scripts, hosted model/mesh fetches, pip/npm registry dependency, or remote execution service is permitted for an offline release.
2. All runtime and build dependencies are version-pinned, archived in redistribution-approved form, integrity-checked, and covered by a machine-readable software bill of materials and complete license/NOTICE inventory. A permissive license for a top-level project **does not** authorize unrelated components or bundled media.
3. A **release operator** must be able to install, build, run, simulate, load supported models and assets, inspect results, and replay tests without a network connection on every explicitly supported target. This includes a customer-controlled machine **only if a separately authorized downloadable/offline edition is offered**. Prebuilt, integrity-checked platform bundles may supplement vendored source. Offline GPU prerequisites must be provided through a documented lawful offline installation path.
4. A build that works only because of an existing developer package cache, cached compiled kernel, home-directory configuration, online registry, or preexisting asset download is a **failure**.
5. Model-import paths (`package://`, `model://`, local URDF/MJCF/USD, textures, meshes) must resolve within an explicit package root and must not silently fall back to HTTP. Missing material produces a deterministic diagnostic.
6. Source changes retain upstream attribution and carry change notices. Every import pins a source commit, archives its own license/NOTICE files, and records hashes of every imported file.
7. No release may be called *offline-ready*, *physically validated*, *numerically validated*, or *licensed for redistribution* without the corresponding recorded acceptance evidence.

## Commercial deployment and offline execution are separate questions

TextPCB's currently approved commercial model is **served-only proprietary engineering software**. The default product installs the complete vendored Steel runtime on TextPCB-controlled, isolated engineering workers. A worker must run its physics simulation, local model import and replay with outbound network denied; the hosted portal/API, account/payment layer and encrypted customer artifact transport are separate, explicitly authenticated services. The Steel engine's *offline compute capability* does **not** require handing a customer private TextPCB binaries, prompts, solver adapters, image layers or service credentials.

The browser WebGPU option is a distinct delivery target: code shipped to the browser is visible to the customer. A separately reviewed client-side bundle may contain appropriately licensed open-source Steel WebGPU code and public data, but cannot embed private TextPCB internals or customer-specific secret assets. Offline use of such a client bundle requires its own asset, license, security and disconnected-browser acceptance evidence. A customer-installable **private full TextPCB edition** is out of scope until a deliberate commercial/IP policy change. Do not imply customer licensing merely because an Apache-2.0 upstream dependency can lawfully be redistributed.

The [pinned WebGPU core subset](../vendor/browser/steel-webgpu/README.md) is now vendored byte-for-byte with its Apache license records, explicit provenance and a fail-closed verifier. SteelX [`loadOfflineScene`](../src/offline-scene.mjs) accepts preloaded, SHA-256-bound WebGPU scene bytes without a fetch API. It resolves upstream `../shared/meshes/*` references only within a declared logical asset root. The restricted [`webgpu.mjs`](../src/webgpu.mjs) entry point deliberately excludes upstream network scene/mesh loaders, and [`offline-models.mjs`](../src/offline-models.mjs) injects local hash-verified STL/OBJ mesh callbacks into URDF/MJCF instead of accepting HTTP downloads. These are **source and data-path milestones**, not a verified offline browser release: the upstream renderer worker still has separate fetch routes, browser XML import integration is not yet tested, and neither WebGPU simulations nor packaged native runtimes have been qualified offline.

## Platform envelope (initial candidates, not a claim of current support)

| Target | Engine | Offline acceptance needed |
| --- | --- | --- |
| Linux x86-64 CPU | Newton/Steel | Fresh offline install, physics smoke, deterministic replay, import and tests |
| Linux x86-64 NVIDIA GPU | Newton/Steel + Warp | Driver/runtime availability, GPU kernels, GPU smoke and CPU comparison |
| Windows x86-64 CPU/GPU | Newton/Steel | Fresh offline install, native toolchain and GPU capability checks |
| macOS CPU | Newton/Steel | CPU-only installation and smoke; no unsupported CUDA claims |
| Desktop/mobile browser with WebGPU | Steel WebGPU | Locally hosted or file-installed assets, no CDN/service-worker network fallback, simulation and scene import |

Additional operating systems, architectures, browser versions and accelerator types are not supported merely because an upstream README mentions them. Each needs an explicit packaged target and offline proof.

## Supply-chain packaging layers

- `vendor/sources/`: complete, pinned upstream source trees (Newton, Steel WebGPU, Warp, and additional source dependencies as analysis finds them).
- `vendor/python/`: per-target wheelhouses, sdists when needed, Python build backend/toolchain material, metadata and hashes. Installing must use `--no-index`, an isolated environment, and local paths only.
- `vendor/javascript/`: vendored JavaScript package tarballs and package-manager/runtime tooling needed for reproducible offline builds; the lockfile alone is insufficient.
- `vendor/toolchains/`: redistributed compiler/build inputs where lawful, with platform-specific install instructions. NVIDIA drivers and SDK components require separate redistribution review and may be external offline prerequisites.
- `vendor/assets/`: source-backed robot, geometry, shader, texture and test assets with individual licenses and checksums.
- `vendor/attestations/`: SBOM, licenses, NOTICE aggregation, provenance, build manifest and offline-test receipts.

The folders above describe the intended **release bundle** and need not all be committed as large binaries to the GitHub source repository. Git LFS or a versioned, checksum-verified offline bundle may carry oversized content, but a release must include it, with no network required after delivery. The actual source code will be vendored in the steelX repository.

## Strict release acceptance

1. Every source entry in `vendor/upstreams.lock.json` is imported and passes the byte-for-byte manifest check (`python tools/verify_vendor.py`).
2. Exact transitive dependency closure for each target is archived and licensed; source and binary provenance, SPDX SBOM, upstream notices and modification notices are present.
3. Fresh-install tests on **operator-controlled target machines** in disconnected environments, empty user caches, and isolated temporary homes. Verify no socket/connect attempts and no fetches on startup, simulation, build, import, render, and replay. Test separately authorized browser/offline distribution in a customer-equivalent environment if offered.
4. CPU reference cases and GPU/browser comparisons pass explicit numerical error tolerances, regression and determinism suites, and hardware/driver compatibility checks. Record exact devices, drivers and source commits.
5. Robot models and mechanical assets carry independent license and attribution review; launch video, brand marks and music cannot be assumed redistributable because the solver is Apache-2.0.
6. Offline tests and license gate fail closed in CI and release packaging. Versioned artifacts, logs, test evidence, hashes and a reproducible rebuild procedure accompany each release.

## Maintenance versus operation

An *online maintainer import* is permitted only when deliberately updating pinned upstream sources or assembling a future release. It is not part of installation, build, simulation or customer operation. `tools/vendor_sources.py` accepts existing clean local checkouts; it neither contacts GitHub nor installs packages.

## License facts and unresolved review

- Newton and its Steel solver: Apache-2.0 source; third-party licenses occur under `newton/licenses/` and other assets. Packaging must preserve those records.
- Skild Steel WebGPU: Apache-2.0 source; its LICENSE explicitly lists bundled robot model licenses separately.
- NVIDIA Warp: Apache-2.0 source; published source licensing **must not** be conflated with CUDA toolkit, driver or third-party binary redistribution terms.
- Python/JS transitive closure, fonts, models, image/video/audio, drivers and optional features are **pending per-artifact review**. No blanket approval has been inferred.

Apache-2.0 section 4 requires retaining applicable notices, distributing its license, and flagging modified files. See https://www.apache.org/licenses/LICENSE-2.0 . CUDA toolkit redistribution is separately governed by https://docs.nvidia.com/cuda/eula/index.html . A legal review is needed before shipping a bundle that includes proprietary components.
