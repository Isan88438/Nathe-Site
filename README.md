# Nathe

Nathe is an independently developed language-model project. This repository contains the public, standalone browser release.

## Run Nathe

Open **[index.html](./index.html)** in a modern browser. The page is self-contained: it embeds the Nathe C inference engine compiled to WebAssembly, the trained model checkpoint, and the local project-reference index. It does not use hosted AI providers, online search, external knowledge APIs, or runtime network connections.

The model checkpoint and inference engine are packaged into the page. No separate model download or server is required.

## Release contents

- `index.html` — standalone Nathe chat application.
- `benchmarks/nathe-generation-benchmark.json` — held-out generation benchmark output.
- `LICENSE.md` — project copyright notice.

## Model provenance

The embedded checkpoint comes from the successful Nathe project-training run **#28** in [Nathe-Private](https://github.com/Isan88438/Nathe-Private/actions/runs/45361721805), trained from the project's own approved training corpus. The checkpoint is 2,245,164 bytes; SHA-256:

```
5d8173fb9a3e74765a36409af171087a0dd15acd9eba1fd57797214d0001d86c
```

The standalone C/WebAssembly runtime was produced by successful standalone build **#134** in Nathe-Private. This public release bundles that tested runtime with the later run #28 checkpoint. Its embedded reference index contains **1,222** locally authored project references.

## Enable the live GitHub Pages website

The application files are committed, but GitHub Pages was not enabled in the repository when this release was committed. To publish the live website:

1. Open **Settings → Pages** in this repository.
2. Set **Build and deployment → Source** to **GitHub Actions**.
3. Open **Actions → Deploy Nathe website → Run workflow**.

The workflow publishes the root application and benchmark. The expected site address is:

`https://isan88438.github.io/Nathe-Site/`

## Known limitations

Nathe's neural model is experimental and is **not yet a reliable general-purpose assistant**. On its 12-prompt held-out generation benchmark, it generated text for all 12 prompts but recorded **0% expected-keyword coverage**. The benchmark is a simple lexical diagnostic, not a measure of factuality or intelligence. The local reference layer is more dependable when a question matches its approved project material.

A later full build (#153) completed corpus preparation, native training, checkpoint loading, native generation, WebAssembly compilation and bundling, but its final held-out paraphrase retrieval test failed on the `variable-purpose` prompt. That newer build was not treated as a passing release.

## Project separation

- **Nathe-Private** contains the private engine, training pipeline and project-owned training material.
- **Nathe-Site** contains the public standalone application release.

Copyright Ethan Angstetra.
