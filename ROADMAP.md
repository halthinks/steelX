# steelX roadmap: audit → vendored engine → integration

Status: **active plan; no phases declared complete**. Updated 2026-11-09.

The defining product requirement is a **fully vendored, properly licensed, fully offline physics engine**, usable without a hosted service, third-party package registry, CDN or online asset server. See [offline contract](docs/OFFLINE_CONTRACT.md).

## Phase 3 — inspect, model and baseline the upstream code (first)

- [x] Identify canonical Newton Steel and Steel WebGPU source locations and repository licenses.
- [x] Pin initial upstream source revisions (`vendor/upstreams.lock.json`).
- [ ] Trace SolverSteel public API, dynamics, memory management, collisions, contacts, constraints, joints, actuation, determinism and numerical algorithms to the actual implementation and tests.
- [ ] Audit WebGPU feature parity, unsupported model features, precision limits, file/URL loaders, shaders, browser capabilities and renderer/runtime coupling.
- [ ] Review Newton/Warp Python/native build graph and exact JavaScript transitive dependency graph, not only declared top-level dependencies.
- [ ] Establish numerical reference problems, fixed seeds, tolerance budget, throughput/memory benchmarks, sensitivity and error handling, with measured evidence.
- [ ] Classify all asset/binary/code licenses and redistribution restrictions, including NVIDIA driver and CUDA toolkit terms.
- [ ] Record supported platform matrix and acceptance evidence for each target.

Gate **A**: code-level dependency diagram, reproducible benchmark protocol, issue ledger, source-bound test plan, initial dependency SBOM and redistribution decision register are reviewed. Marketing performance claims are not treated as reproduced results.

## Phase 1 — steelX as a standalone, offline engine (second)

- [ ] Import complete pinned Newton, Steel WebGPU and compatible Warp source into `vendor/sources/`, preserving licenses/notices and SHA-256 inventories.
- [ ] Complete any additional source dependency vendors discovered by Phase 3; no source checkout/network operation during build.
- [ ] Produce locked, licensed, per-target Python wheelhouses and JS package/build-tool bundles; eliminate network-backed installers and implicit downloads.
- [ ] Provide deterministic CPU runtime, NVIDIA GPU runtime, and in-browser WebGPU runtime as separate locally installable targets, with common model/result semantics wherever physics implementations permit.
- [ ] Resolve all supported local model/asset imports without remote URI fetches; reject missing/out-of-root assets safely.
- [ ] Define stable data interchange for model, controls, state, time step, diagnostics, contact and provenance metadata.
- [ ] Add CLI/API and offline interactive viewer, with actual verified simulation examples and saved/replayable results.
- [ ] Validate native and browser parity to documented tolerances. Track unsupported physics explicitly rather than silently approximating it.
- [ ] Add license/NOTICE/SBOM generators and a redistribution gate for every bundle.
- [ ] Test clean install/build/launch/simulate/import/render/replay/benchmark on genuinely disconnected, empty-cache machines for each supported target.
- [ ] Cut source-bound signed/hashed releases with rollback-safe provenance and recorded offline proof.

Gate **B**: packaged releases pass the [strict offline acceptance criteria](docs/OFFLINE_CONTRACT.md#strict-release-acceptance) for each advertised target. The source importer/validator alone does **not** establish offline capability.

## Phase 2 — engineering integration (third)

- [ ] Inspect actual VibeMechanica, Aero, TextPCB and HardwareClosure code/roadmaps before writing adapters; map ownership and avoid duplicate solvers.
- [ ] Define exchange formats and unit conventions, geometry provenance, tolerances, and solver selection/limitations.
- [ ] Integrate mechanism/robot and ground-contact workloads into VibeMechanica; use Aero only for physics domains Steel actually models.
- [ ] Integrate applicable assembly/mechatronic workflows into TextPCB without substituting dynamics for geometric DRC or aero/FEA.
- [ ] Connect relevant control/test validation workflows to HardwareClosure with replayable input/result archives.
- [ ] Run end-to-end offline, source-pinned integration regressions and document performance on actual hardware.

Gate **C**: every supported integration works end-to-end offline and is demonstrated with verified code, tests and recorded reproducible results. No product-integration status is inferred from this plan.

## Immediate working queue

1. Audit exact numerical solver and browser API against source and tests.
2. Complete dependency and license inventory, resolving redistributability individually.
3. Import and verify pinned upstream source trees (vendor importer/validator provided).
4. Design and produce first CPU-only offline release bundle, then GPU and browser bundles.
5. Establish offline network-denial regression suite and license acceptance gates before exposing release artifacts.
