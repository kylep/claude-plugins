# Running and inspecting artifacts

`scripts/run.py` requires Python 3 and an installed Factorio 2.x executable. It was exercised with macOS Steam 2.0.77; use the shipped documentation and adapt the exporter for incompatible versions. No Python packages are required.

macOS defaults:

- Binary: `~/Library/Application Support/Steam/steamapps/common/Factorio/factorio.app/Contents/MacOS/factorio`
- User data: `~/Library/Application Support/factorio`
- Scenarios: `<user-data>/scenarios/<name>`
- Saves: `<user-data>/saves/<name>.zip`

Override with `--binary`, `--data`, and `--user-data`. The `--scenario` input is a folder; `--save` is a ZIP. Exactly one is required. `--run-dir` must not exist and must be outside the source and user-data directories. The desktop UI is not needed: `--start-server-load-scenario` and `--start-server` start the engine headlessly.

`--surface` defaults to `nauvis`. `--area X1 Y1 X2 Y2` bounds entity export; entities overlapping its edge may be included. Without an area, the runner exports all entities on the selected generated surface, which can be expensive. `--tiles` additionally exports terrain tiles and requires bounds covering at most one million tiles. No deliberate chunk generation is performed. Other surfaces require separate runs or an exporter extension.

Without interval options, the runner takes a snapshot only. Select a profile or provide explicit intervals:

| Profile | Warmup | Measurement | Use |
|---|---:|---:|---|
| `snapshot` | 0 | 0 | Locations, layout, static connections |
| `diagnostic` | 3,600 ticks | 3,600 ticks | Quick production diagnostic |
| `sustained` | 36,000 ticks | 36,000 ticks | Ten-minute steady production test after ten-minute warmup |

`--warmup-ticks` and `--measure-ticks` override profile values. A positive explicit measurement without a profile requires explicit warmup (including 0), avoiding a hidden ten-minute warmup. `--measure-ticks 0` always means snapshot-only. Positive measurements select crafting machines by optional `--recipe` and the same spatial scope. An already-warmed save can use `--warmup-ticks 0 --measure-ticks 3600`; this does not validate cold startup.

Speed defaults to 64; `(0,64]` is the bundled runner's accepted range, not an established engine maximum. Values above 64 were tried in this session without a clear speed benefit; keep 64 unless a controlled benchmark supports changing it. Speed preserves simulated intervals and per-tick sampling; actual throughput depends on available CPU. `--timeout` bounds engine wall time (default 300 seconds). A failed run retains its logs and manifest and returns nonzero. A measurement matching no machines is an error, not zero throughput.

The runner uses the current user mod list and settings. Do not assume these match every old save: inspect load logs for migrations, missing prototypes, or removed entities before interpreting results. Compare `active_mods` with the intended source environment when available. It does not download mods or call `--sync-mods` on the user's installation. Adding an inspection mod can trigger configuration-change handlers in existing mods; disclose effects if they matter to the question.

## Keep repeated runs cheap

Reuse snapshots for layout and graph questions. Scope ordinary exports to the relevant chain. For a large build, perform one broad source snapshot, then use targeted diagnostic exports; reserve full factory/terrain comparisons for the clean candidate and final conversion check. Force item statistics and destination inventory counts can monitor the other sciences without exporting the entire map on every iteration, provided producer scope is established.

`--tiles` can dominate export size and memory when repeated over a wide area. The Yellow roundtrip test with 320,000 terrain tiles at each snapshot took 169.28 seconds, compared with 48.86 seconds for its pre-conversion production test without tiles. These were different runs, not a controlled tile-only benchmark, but they show why full terrain exports should be reserved for static validation. Where useful, separate a terrain snapshot from an operational test rather than repeatedly serializing unchanged terrain.

Use a short placement/API diagnostic before a sustained test. Distinguish slow buffer filling from insufficient chain capacity by comparing inventory growth and production across warm intervals. Change one diagnosed cause per iteration; do not simply add equipment or extend warmup until a favorable interval appears.

## Outputs

At the run root:

- `manifest.json`: source hashes, version, binary path, exporter/config hashes, actual loaded mods and local package hashes, operational changes, completion status, and source/mod-setting preservation checks. `total_seconds` includes preparation; `phase_seconds` separates preparation, engine, validation, shutdown, and preservation checks. `engine_log_seconds` records startup, initial export, measurement-start and completion milestones from engine logs. The older `wall_seconds` field remains for comparison and excludes preparation.
- `console.log`: complete engine output; inspect on failure or suspicious results.
- `mods`, `scenarios`/`saves`, config files: isolated execution environment. Mod package symlinks point at source packages for reading; mod lists and settings are copied.

Under `script-output/factorio-inspect`:

- `initial.json`: first inspection tick after loading and initialization.
- `baseline.json`: state at the start of measurement, after warmup.
- `measurement.json`: exact start/end ticks, completion counters, recipe-change flags, and per-tick machine status totals.
- `final.json`: state at measurement completion or snapshot-only completion.
- `done.json`: success marker, written after the final snapshot, with snapshot build/reuse counts.
- `error.json`: exporter failure; never treat a partial snapshot as successful evidence.

The runner pauses at completion then uses SIGINT to exit; Factorio may save its working copy on exit. This does not overwrite the input. It does not modify source scripts, place entities, spawn a player, force research, inject ingredients, drain outputs, or suppress enemies. These remain additional test conditions if explicitly needed.

A short console command unpauses the disposable save after loading, allowing inspection of inputs saved in a paused state. This is recorded in the manifest. It does not register event handlers in the scenario context.

The mod owns its own event handler. It never calls `script.on_event` in the scenario's console context. Subsequent loads reset the inspection mod's private measurement state, including when inspecting its own saved output; original scenario/mod state remains subject to normal Factorio loading behavior.

Snapshots requested twice within the same tick reuse serialized bytes: snapshot-only initial/final and zero-warmup initial/baseline. Different ticks always rebuild state. Required filenames remain available, and the cache is released on the next inspection tick. The Python validator parses each artifact once. No cross-run cache or persistent server is used; follow-up questions should query existing exports when possible.

Snapshots contain entity ID, type/name, coordinates/bounds, direction, quality, force, status and energy, plus type-specific recipes, inventories, modules, transport lanes, belt neighbors, loader containers, underground pairs, drill resources and inserter targets. IDs are local to an export/run; do not assume stable identity across unrelated maps. References outside the exported area are retained so incomplete traces are detectable.

## Authoritative references

- CLI: https://wiki.factorio.com/Command_line_parameters
- Runtime API: https://lua-api.factorio.com/
- Installed exact-version docs: `<game-data>/../doc-html/classes/LuaEntity.html`, `LuaSurface.html`, `LuaBootstrap.html`.

Prefer the installed API over remembering field names. For example, in 2.0.77 a drill's base mining speed is `entity.prototype.mining_speed`, not `entity.mining_speed`. Regular entity lookup by unit number is not a universal substitute for retaining LuaEntity references. PTY console input can truncate long lines; use the mod rather than sending large Lua programs as console commands.

## Benchmark evidence (2026-10-04)

Sequential runs on this Mac with Steam Factorio 2.0.77, a fresh `Ribbon-AI` copy each time, bounds `-630 -100 -580 100`, recipe `automation-science-pack`, and `--profile sustained`:

| Speed | Total elapsed | Engine phase | Measured output |
|---|---:|---:|---:|
| 32× | 42.18 s | 41.34 s | 1,200 packs / 36,000 ticks |
| 64× | 24.35 s | 23.56 s | 1,200 packs / 36,000 ticks |

64× reduced observed total time by 42.3% (1.73× faster). Both runs used 36,000 warmup ticks and had identical per-machine measurements: eight machines each produced 150 packs and reported `working` for all 36,000 measured ticks. Source hashes and user mod settings were unchanged. These are one paired benchmark, not statistical averages or a guarantee for larger maps.

Separate checks: snapshot-only completed in 3.59 s with one snapshot build and one reuse. A paused, already-warmed save with tiles and a 3,600-tick measurement completed in 4.57 s with two builds and one reuse, producing 120 packs. Byte equality was checked for reused artifacts. Those short checks establish behavior; their elapsed times are not controlled comparisons against the earlier implementation.

Benchmark artifacts were retained under `/private/tmp/factorio-speed-bench-32`, `factorio-speed-bench-64`, `factorio-speed-snapshot`, and `factorio-speed-zero-warmup`. Temporary directories may later be removed; this section records the main evidence.
