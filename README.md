# Nathe

Nathe is an independently developed language-model project. This repository contains the public, standalone browser release.

## Run Nathe

Open the live GitHub Pages website or the downloaded `index.html`. The application embeds Nathe's C/WebAssembly inference engine, trained model checkpoint and local project-reference index. Its optional Web Research feature loads a compact, same-site index of public web pages. No local Python server, hosted AI model or third-party search API is required.

For the GitHub Pages website, `research-index.json` is fetched from the same site. The research index is automatically refreshed by GitHub Actions and is not fetched live for every question.

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

The workflow publishes the root application, research client, research index and benchmark. The expected site address is:

`https://isan88438.github.io/Nathe-Site/`

## Known limitations

Nathe's neural model is experimental and is **not yet a reliable general-purpose assistant**. On its 12-prompt held-out generation benchmark, it generated text for all 12 prompts but recorded **0% expected-keyword coverage**. The benchmark is a simple lexical diagnostic, not a measure of factuality or intelligence. The local reference layer is more dependable when a question matches its approved project material.

A later full build (#153) completed corpus preparation, native training, checkpoint loading, native generation, WebAssembly compilation and bundling, but its final held-out paraphrase retrieval test failed on the `variable-purpose` prompt. That newer build was not treated as a passing release.

## Project separation

- **Nathe-Private** contains the private engine, training pipeline and project-owned training material.
- **Nathe-Site** contains the public standalone application release.

Copyright Ethan Angstetra.


## Nathe Web Research

Web Research is enabled by default in the chat. For an ordinary question, Nathe searches the published research index first, passes up to two short excerpts into its own C model as untrusted source context, and displays links to the matching pages. The **Web On / Web Off** control lets you switch to local-only answers.

The index is built by Nathe's own Python-standard-library crawler in GitHub Actions. It starts from \`research-seeds.txt\`, follows relevant public HTTPS links, checks each site's \`robots.txt\`, blocks private-network addresses, and stores short text extracts with source URLs and dates. The workflow refreshes it approximately every six hours and automatically triggers a GitHub Pages deployment when the index changes.

**You do not need to run Python or start a localhost server.** The crawler runs on GitHub's build runners, not on your computer. The browser searches the latest published snapshot. This is not a live search of every web page: it covers the pages the crawler has discovered and indexed so far, and the index can be several hours behind.

The index contains short text extracts for searching and model context, not complete copies of the source websites. Retrieved web text is not silently added to Nathe's model-training corpus. Nathe's neural model remains experimental, so check the cited pages for important facts.
