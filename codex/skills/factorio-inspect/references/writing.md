# Editing and publishing Factorio scenarios

Read this for an authorized map edit, rather than ordinary inspection. The bundled runner is an inspection tool, not a general editor. Use a task-specific Lua build/patch module in an isolated copy and keep the original scenario handlers intact.

## Plan from the loaded map

Read actual recipes, ingredient quantities, output amounts, module compatibility, quality, resource yield and fluid ports from the installed game with its active mods. Vanilla assumptions can change the entire design: this map's flying robot frame recipe uses plates, gears and green circuits, rejects productivity, and needs no battery/engine chain.

Use exported entity bounds and terrain to plan placement. A grid planner should model rotated footprints and existing entities, then let `surface.can_place_entity` and the engine verify it. Before scaling out, test one complete representative column with its input/output collection, power and fluid connections. Static collision checks cannot prove that every row is collected or that lanes carry the required rate.

Prefer a declarative plan, a short Lua application pass with assertions, and local JSON analysis. Archive the raw snapshots required to regenerate the plan; avoid dependencies on disposable `/tmp` files. Do not promote a map-specific layout generator into a generic editing tool without removing its coordinate, recipe and routing assumptions.

For a request to compact a factory, read [the packing guide](packing.md) before choosing the layout. It covers packing complete production groups, routing and visual density checks.

## Fragile Lua details observed in 2.0.77

Check the installed API when adapting these calls:

- Load `require('plan')` while `control.lua` is parsed. Calling `require` from a tick handler fails.
- Create underground belts with `type='input'` or `'output'`. `belt_to_ground_type` is read-only. A loader's `loader_type` is writable.
- `set_recipe` can reset an assembler's direction. Set its intended direction afterwards, then export actual fluid connections rather than assuming rotated ports.
- Inserter direction faces its pickup side; a west-side arm feeding an assembler to the east used direction `west`. Verify `pickup_position` and `drop_position` in the engine. Loader flow direction follows different semantics.
- Preserve whole-tile translation offsets when cloning half-tile-centered machinery. Copy the shoreline tiles when moving an offshore pump; placing the entity alone is insufficient.
- Clone or insert module inventories explicitly and assert inserted counts. A familiar recipe name does not guarantee productivity compatibility. The tier-one item is `speed-module`, not `speed-module-1`.
- In a resumed disposable save, reset only the inspection mod's private measurement state so it creates a new initial/baseline/measurement sequence. The bundled runner already does this; retain that behavior in custom exporters.

## Verify before replacing the playable scenario

1. **Build and diagnose on disposable copies.** Assert placements, recipes, modules and directions. Keep recipe unlocks, injected stocks, drained outputs or other test-only changes explicit. Validate upstream supply and warehouse delivery separately. Do not publish an advanced throughput-test save as a fresh scenario.
2. **Produce a clean candidate.** Apply the final edit to a fresh source copy with a snapshot-only run. Export before/after state and research. Keep test unlocks and ingredient seeding out of this build. Pausing at the first inspection tick avoids simulated production, but normal mod initialization has still run.
3. **Convert with the inspection mod disabled.** In the candidate's isolated `mods/mod-list.json`, disable only the inspection module. On this Mac, the command below reads `<run>/saves/inspection-source.zip` and writes `<run>/scenarios/inspection-source`. Use the basename without `.zip`; confirm paths in the engine log.

   ```sh
   <factorio-binary> --config <run>/config.ini \
     --mod-directory <run>/mods --map2scenario inspection-source
   ```

4. **Reload the converted scenario.** First export its locked state, then apply any declared test-only recipe unlocks in the disposable verification copy. Compare recipes/technologies, map generation settings, terrain, existing machinery/inventories and all intended additions with the clean candidate. Measure the final converted map, not just the pre-conversion build.
5. **Publish within the user's authorization.** Check source hashes again so a new user save is not overwritten. Archive the previous playable scenario and evidence. Stage the converted directory beside the target, verify hashes, and rename it into place with rollback if replacement fails. Check installed hashes and original-source preservation afterwards.

Compare stable fields: names, positions, directions, force, quality, recipes, modules, inventories, resource amounts and inserter/loader configuration. Entity IDs and electric-network IDs are run-local. Account separately for known mod-created helpers and transient visual effects; do not allow unexplained structural additions/removals under a broad exception. Initial `no_power` or missing targets can reflect an entity not having received its first update; use runtime observations for operational claims.

## Retained example

`/Users/kp/gh/factorio-artifacts/2026-10-05-yellow-build` contains the declarative plan, build/export preparation, static/roundtrip validation, source snapshots, publication script, hashes and previous Ribbon-AI backup. It is a map-specific worked example, not a generic API. The converted scenario produced and delivered 1,203 utility packs over 36,000 measured ticks after 72,000 warmup ticks. Research and the existing factory were preserved. The user chose belt-fed production, rich top-edge resources and a shallow eastward footprint; those are task preferences, not universal requirements.
