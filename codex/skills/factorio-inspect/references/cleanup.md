# Transport cleanup

Freeze a working layout before cleanup. Use engine snapshots and scripted graph analysis instead of re-solving placement or reading thousands of entities in the model. `scripts/cleanup.py SNAPSHOT --area X1 Y1 X2 Y2 --output PLAN.json` is a read-only planner.

It keeps the intersection of forward reachability from output loaders, drill drops and external feeds with reverse reachability from input loaders, inserter pickups and external delivery links. It preserves whole underground pairs. This identifies dead transport, not the globally smallest network; lane behavior still requires engine verification. Export beyond the cleanup area so boundary links can be identified.

After pruning, rerun on the resulting engine graph. Clear underground spans can become surface belts only when every intermediate surface tile is free, no inserter pickup/drop is exposed, no new side-loading connection appears, and jointly chosen replacements do not intersect. The tool conservatively rejects such interactions. It proposes coordinates; use a separate authorized Lua patch with placement assertions, not direct binary edits. Natural resources do not obstruct belts, but terrain and engine placement must still pass.

Treat removal-only and cosmetic conversion as explicit edit sets. Preserve all other configuration, inventories, research and terrain. Compare actual underground partners after rebuilding; removing endpoints can change pairings. Verify the clean converted scenario's production and destination delivery before publishing with a backup. A productive graph does not prove sufficient lane capacity.

Equal splitter division can starve unequal production banks. Prioritizing a consumer branch lets it take its demand and pass the remainder onward. Diagnose with per-machine shortages, capacities and stock changes; extending warmup did not fix this imbalance in the retained Yellow cleanup.

Validated Yellow cleanup: 1,135 ordinary belts and 174 underground endpoints removed; six science-input splitters given consumer priority. The converted map produced 120.9 packs/min and delivered 120.6 over twenty minutes after sixty minutes of warmup. Other science counters matched the prior map. Local evidence: `/Users/kp/gh/factorio-artifacts/2026-10-05-yellow-prune`.
