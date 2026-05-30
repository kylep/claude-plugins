# game-dev-tools

Skills for building mods for moddable games. Currently scoped to Stellaris (Paradox / Clausewitz engine), with patterns transferable to other Paradox titles.

## Install

```text
/plugin marketplace add kylep/claude-plugins
/plugin install game-dev-tools@pai-plugins
```

## Skills

- **create-stellaris-mod** — codified workflow for building a Stellaris mod from a vague idea. Picks the right transformation pattern (sentinel rewrite for cap-lifting, multiplier transform for scaling, direct override for value replacement), scaffolds the build/deploy/preflight scripts, and embeds the hard-won gotchas (thumbnail format, BOM, sentinel separation, launcher cache).

## Lineage

The patterns in this plugin were extracted from two shipped Stellaris mods:

- **Multi-Megastructures + Free Tech** — lifts per-empire and per-system megastructure caps. Source of the *sentinel rewrite* pattern.
- **3x Bigger Worlds** — triples planet sizes, deposit yields, and district-add modifiers. Source of the *multiplier transform* pattern.

Both ship a `build.py` + `preflight.py` + `deploy.sh` triple, generated from local vanilla files, with a thumbnail pipeline.
