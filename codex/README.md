# Codex skills

Codex-specific skills live here for now, separately from the Claude plugin marketplace.

## Factorio inspection

[`factorio-inspect`](skills/factorio-inspect/SKILL.md) reads scenarios and saves through an isolated headless Factorio instance, traces production chains, measures throughput, and documents the workflow for authorized map edits and compact layouts. It includes the Python runner, analyzer, Lua inspection mod, and references for reading, writing, testing and packing.

Copy `skills/factorio-inspect` to `~/.codex/skills/factorio-inspect` to install. The runner requires Python 3 and an installed Factorio 2.x executable; its default paths target Steam on macOS and can be overridden. Ordinary inspection needs no additional Python packages. OR-Tools is an optional aid for layout packing.

These files are the working skill from the Ribbon scenario session, retained as-is for a later cleanup. References include local artifact paths and map-specific examples; the scenario saves, artifacts and packing environment are not included.
