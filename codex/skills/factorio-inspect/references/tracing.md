# Production tracing and measurement

First establish the question: installed capacity, sustained production, delivery, consumption, startup time, or operation during attacks. Avoid changing research, power, supply, enemies or output sinks just to obtain a favorable result. If a controlled variant is useful, preserve the unmodified baseline and report the changed conditions.

## Graph

`analyze.py` builds directed item edges from belt outputs, underground input/output pairs, loader container/direction, inserter source/target, and drill discharge. Where an inserter or drill lacks a direct engine target, point/bounding-box matches are explicitly marked geometric candidates. Initial snapshots may lack recipes, mining targets, or inserter targets before the first useful updates; the warm baseline/final snapshot often provides better information.

Trace recursively through intermediate crafting machines. Count equipment reachable through this graph, not every nearby machine with the same recipe. Look for downstream branches off upstream nodes: those may share supply with other lines. The trace includes output edges from target assemblers as well, so not every reported branch is competing upstream demand.

`outside_export` means the current area is insufficient. Expand it and export again, or inspect those endpoints before claiming a complete chain. A zero-length list means all traversed references are in scope, not that every possible transport mechanic was modeled. A missing target or an unsupported mechanism can still terminate a trace.

This graph deliberately does not solve lane-level splitter filtering, inserter filters or circuit conditions, train schedules, fluids, logistic robot requests or custom scripted transfers. Inspect lane contents and relevant controls or use a runtime test when these affect the result. Never invent connectivity from visual proximity alone.

## Capacity

Recipe cycles/minute = `60 × effective crafting_speed / recipe.energy`.

For a deterministic single-output recipe without productivity, items/minute = cycles/minute × recipe output amount. Derive recipe times and machine speeds from the actual loaded game; modded names do not guarantee vanilla properties. Treat productivity, quality, probabilities, catalysts, ignored-productivity amounts and caps explicitly. The analyzer leaves ambiguous cases for further accounting rather than silently applying a generic multiplier.

For ordinary solid resources, base mining cycles/minute = `60 × prototype.mining_speed × (1 + speed_bonus) / mining_time`. Apply actual resource yield, force productivity, quality and power constraints as appropriate. Fluid/infinite resource yield requires its own accounting. A furnace's theoretical rate is not its supplied rate; chain capacity is limited by the minimum stage after conversion ratios and shared demand.

Verify required ingredient rates per recipe. For red science at 120/min in the validated example: 120 copper plates/min and 120 gears/min, requiring 240 iron plates/min. Belt speed alone does not guarantee usable per-lane throughput or that inserters can access the needed lane.

## Belts, buffering, fluids and power

Derive belt capacity from exported speed. For ordinary unstacked belts in this engine, total items/minute = `belt_speed × 480 × 60`; each lane carries half. A turbo belt at `0.125` carries 60 items/s (3,600/min), not 90. Stacked transport requires its actual stack size. Check merges and side-loading: a full lane can stall upstream machines while the other lane has space. A container with input/output loaders can balance lanes, but is a layout choice rather than a universal remedy.

Direct loaders can fill assembler inputs with whole stacks instead of a few recipe cycles. Cascaded splitter feeds then favor lower machines while upper ones wait for stock; surplus intermediate production can also consume scarce shared ingredients while filling long belts. Inspect inventory growth before diagnosing a disconnected or undersized chain. For slower steps, properly sized inserters can reduce buffering. Verify their throughput with the actual stack bonus, quality, pickup belt and recipe demand: this build's ordinary bulk arms could not reliably supply processors' 20 green circuits per craft; legendary arms did. Keep loaders where the ingredient rate warrants them.

Export each fluidbox's locked fluid, contents and `get_pipe_connections` target positions. Empty pipes do not identify their intended fluid. Check actual `pipe-to-ground` open faces and pairings; a route cannot connect to a closed side just because it reaches the same tile. In 2.0.77, an overlong connected pipeline reports `pipeline_overextended`; the observed 320-tile extent limit required a powered pump to split the long gas supply. Verify every resulting segment rather than treating the pump's mere presence as proof. Copied oil machinery still needs its networks checked after translation and connection to new trunks.

Check electric-network membership as well as pole spacing. Solar output alone does not prove overnight operation: a large new block may need additional generation and storage even on a map with modded solar. Measure relevant day/night cycles and confirm earlier science lines retain their rates.

## Measurements

The runner warms up, records individual `products_finished` counters, samples selected crafting-machine statuses every tick, and stops at an exact tick boundary. Status totals must sum to the measurement length. Destruction and recipe changes invalidate simple counter comparisons. Newly built machines are not automatically added mid-measurement; if construction changes the line, export and select a new baseline.

The analyzer converts completion deltas to item rates only for deterministic recipes producing one item per cycle with zero productivity. For multi-output or productivity recipes, retain raw completion counters and obtain item-production statistics or validate counter semantics for the exact engine version. Completion counters in this build already reflected productivity completions; multiplying them by productivity again would overcount. Verify exact semantics before using a conversion. Per-force item statistics include other producers; do not attribute a force-wide total to one line without establishing scope.

Full throughput over an interval supports a claim about that interval. Per-tick `working` statuses strengthen the evidence but are not continuous power-grid telemetry. Check whole relevant power cycles for nighttime claims; check output sinks before claiming delivery or research consumption. Buffered inventories can conceal long-term shortfalls, so compare input buffers and investigate shared supply when the measured interval is too short.

Do not add universal testing requirements to every question. A location query needs only an export; a throughput claim merits the relevant graph and measurement. Keep conclusions labeled as calculated, directly connected, inferred, or measured.
