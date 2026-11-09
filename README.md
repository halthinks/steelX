# steelX — offline, vendored Steel physics engine

> **Development status (2026-11-09):** The repository currently contains upstream
> Steel launch documentation and media. A complete offline engine has **not** yet
> been imported, built, or verified. The roadmap and vendor verification tools
> are the first implementation step.

steelX's target is a **fully vendored, properly licensed, offline-capable physics
engine** encompassing Newton's Steel solver, Warp dependencies, and the WebGPU
implementation. No customer build or simulation may require a cloud service,
package registry, hosted asset, or online license check.

- [Engineering roadmap](ROADMAP.md) — code audit → standalone vendored engine → product integration.
- [Offline and licensing contract](docs/OFFLINE_CONTRACT.md) — supported targets,
  dependency closure, redistribution rules, and strict release evidence.
- [Source-level audit findings](docs/AUDIT_BASELINE.md) — observed network loaders,
  CPU/GPU limitations, and the next code changes required.
- [Pinned upstream sources](vendor/upstreams.lock.json) — exact revisions.
- [Source importer](tools/vendor_sources.py) and [validator](tools/verify_vendor.py)
  — maintenance groundwork; they do **not** establish an offline release.

## Original Steel launch information

[![Watch the Steel launch video](assets/launch-poster.jpg)](https://github.com/user-attachments/assets/be138f43-7852-40dc-a7ab-de1b2aa49cde)






Steel is Skild's physics solver for scalable simulation of manipulation, built with NVIDIA and open-sourced as part of Newton. Across 20 robot-learning benchmarks it delivers 3.8× PhysX's simulation throughput (geometric mean), and up to 13× on heterogeneous batches that mix different robots and tasks, while using less GPU memory.

We are actively accepting contributions from you and your agents, and are committed to maintaining Steel as a shared foundation for diverse, scalable simulation.

## Updates

- **November 9, 2026** — The open-source launch of Steel.

## Code and demos

- [Steel in Newton](https://github.com/newton-physics/newton/tree/main/newton/_src/solvers/steel) — the solver implementation.
- [WebGPU implementation](https://github.com/skild-ai/steel-webgpu) — the browser implementation.
- [Playground](https://www.skild.ai/steel/playground) — interactive demos.
- [Blog](https://www.skild.ai/steel) — the launch write-up.

## License

Steel is licensed under the [Apache License, Version 2.0](LICENSE). The solver is distributed as part of [Newton](https://github.com/newton-physics/newton), which is also licensed under Apache-2.0.

Third-party assets and media retain their own licenses.
