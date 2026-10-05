---
name: factorio-inspect
description: Inspect Factorio scenarios and saves, trace and test production chains, and validate authorized map edits using isolated headless simulations.
---

# Factorio inspection and production tracing

Use Factorio itself to decode map state. Scenario Lua/JSON is readable, but `blueprint.zip/blueprint.dat`, `script.dat`, and save map data are binary; they are not ordinary blueprint-string JSON. ZIP contents and metadata alone do not establish what is on the map.

## Choose the amount of work

- File discovery or metadata: inspect the filesystem and ZIP listings without starting Factorio.
- Layout, locations, recipe configuration, or connectivity: make one scoped snapshot with `scripts/run.py`, then query the JSON locally.
- Sustained throughput: use the same runner with warmup and measurement intervals; analyze the graph and actual output together.
- Authorized map edits: read [the writing guide](references/writing.md) for the build, clean conversion, roundtrip validation and publication workflow. The bundled runner supplies inspection; a task-specific patch is still needed. Inspection alone does not authorize changing playable files.

## Run an isolated inspection

Read [the runner guide](references/runner.md) for options, artifacts, version differences, and failure handling. Locate the installed binary, data directory, scenario/save, and active mods. Check the binary's `--help` and version; installed `doc-html` is the best API reference for that exact build.

The bundled runner uses a separate inspection mod and a fresh run directory. It preserves scenario handlers, hashes source files, copies mod settings, links mod packages for reading, disables server discovery and auto-pause, binds to localhost, and stops the process after export. It never intentionally generates new chunks or enables recipes/technologies. Loading still runs the source scenario's and mods' initialization; the initial snapshot is at the first inspection tick, not a byte-for-byte depiction of pre-initialization state.

Example (replace paths and bounds for the actual task):

```sh
python3 <skill>/scripts/run.py \
  --scenario '/path/to/scenarios/MyScenario' \
  --run-dir /tmp/factorio-inspection-unique \
  --area -630 -100 -580 100
```

Choose the interval explicitly. Add `--recipe automation-science-pack --profile sustained` for ten minutes of warmup plus ten measured minutes. Use `--profile diagnostic` for one minute of each when only a quick diagnostic is needed. For an already-warmed save, `--warmup-ticks 0 --measure-ticks 3600` measures one minute without another warmup. That is not equivalent to testing startup from a fresh scenario.

There are 3,600 ticks per simulated minute. The default simulation speed is 64×; use `--speed 32` if needed. Speed changes wall time, not the measurement interval or per-tick checks. Extend the interval when the question concerns power cycles, depletion, attacks, or downstream saturation.

Use a new directory for every run. Reuse an existing snapshot for follow-up questions when the source and relevant conditions have not changed. Start comparisons from the same fresh source, not an already-advanced test save. Do not work around a localhost sandbox denial; request the normal execution escalation for the isolated command.

## Trace and verify a production line

```sh
python3 <skill>/scripts/analyze.py <run>/script-output/factorio-inspect/final.json \
  --recipe automation-science-pack \
  --measurement <run>/script-output/factorio-inspect/measurement.json \
  --output <run>/analysis.json
```

Read [the tracing guide](references/tracing.md) for graph limits and throughput accounting. Analyze upstream from the requested recipe through inserter endpoints, belt neighbors, paired undergrounds, loader containers, intermediate recipes, and drill discharge points. A point-overlap inference is labeled separately from a direct engine-reported connection. Expand scope if required nodes lie outside the export.

Inspect shared branches, item filters, lanes and power before calling a chain sufficient. Entity-level graph reachability does not prove an item can traverse a particular lane or filtered splitter. Fluid networks, bots, trains, and scripted transport require additional task-specific exports; the bundled graph does not model them.

Report separately:

- **Capacity:** recipe time, effective crafting speed, output quantity, bonuses and actual resource supply. Distinguish furnace capacity from ore-limited delivery.
- **Connectivity:** engine links versus geometric candidates, scope gaps, filters/lanes still unverified.
- **Measured production:** exact interval, per-machine deltas and sampled statuses. Do not convert ambiguous craft counters into item rates.
- **Delivery/consumption:** only when separately measured at the requested destination; production alone is not lab consumption.

Lead with the answer and the evidence needed to assess it. Say what remains unverified without adding an unsolicited general factory critique. Keep maps and user preferences as task context rather than universal rules.

## Validation reference

On macOS Steam Factorio 2.0.77, `Ribbon-AI` at `~/Library/Application Support/factorio/scenarios/Ribbon-AI` was inspected with its enabled mods. Bounds `-630 -100 -580 100`, red-science recipe, 36,000 warmup ticks and 36,000 measurement ticks yielded eight machines × 150 packs = 120/min. The upstream graph contained 24 drills, 24 furnaces and two gear assemblers plus eight science assemblers. This is a regression example, not an expected answer for other maps or future versions. Preserve `Ribbon-2026-10` as the user's original when working in this context.
