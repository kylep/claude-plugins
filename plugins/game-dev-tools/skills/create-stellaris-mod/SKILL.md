---
name: create-stellaris-mod
description: Use when the user wants to build a Stellaris mod — especially gameplay-tuning mods (cap-lifting, scaling, value replacement). Codifies the build-from-vanilla / regex-transform / symlink-deploy / preflight-then-launch pattern from two shipped Workshop mods, including the bug-museum (sentinel separation, JPEG-in-PNG, BOM, launcher cache).
---

# Create a Stellaris Mod

A Stellaris mod is a shadow of the vanilla game tree. You don't write game logic from scratch — you copy specific vanilla files into your mod folder, modify them, and the engine loads your version instead of vanilla's. The work is: figure out which files contain the knob you want to tune, transform them programmatically (so future patches can be re-absorbed by re-running your script), wire up the launcher, verify before launching, then launch.

This skill encodes the patterns extracted from two shipped mods. Follow the workflow. Don't reinvent the deploy/preflight wheel — every step in the bug museum cost real debugging time.

## When to use

- User wants a Stellaris gameplay-tuning mod: lift a build cap, scale resource yields, multiply planet sizes, free a tech, etc.
- User wants to build their first Stellaris mod and needs guidance on layout / launcher mechanics.
- A previous Paradox mod (HOI4, EU4, CK3) needs porting — patterns are nearly identical, only directory names change.

## When NOT to use

- The user wants a *new* gameplay system (new megastructure type, new species, new tradition tree). That's content design, not the regex-transform pattern. The deploy/preflight/thumbnail half of this skill still applies; the transformation half doesn't.
- Total conversion / story mods. Out of scope.
- The user just wants to subscribe to an existing Workshop mod.

## Vanilla file location (macOS)

```
~/Library/Application Support/Steam/steamapps/common/Stellaris/
```

User data (where mods get deployed, where logs live):

```
~/Documents/Paradox Interactive/Stellaris/
```

Linux/Windows paths differ — surface the actual `gameDataPath` from `Stellaris/launcher-settings.json` if you can't assume macOS.

## The shape of a Stellaris mod

```
<repo>/<modname>/
├── README.md
├── TESTING.md
├── mod/
│   ├── descriptor.mod        ← INNER descriptor (no `path=`)
│   ├── thumbnail.png         ← 512×512, real PNG, no alpha, <1 MB
│   └── common/
│       └── <subdir>/<vanilla_file>.txt   ← overrides, must use vanilla filenames
└── scripts/
    ├── build.py              ← reads vanilla, writes overrides
    ├── preflight.py          ← pre-launch checks
    └── deploy.sh             ← symlinks mod into user dir + writes OUTER `.mod`
```

After deploy, the user dir looks like:

```
~/Documents/Paradox Interactive/Stellaris/mod/
├── <modname>                 ← SYMLINK to repo's mod/ folder
└── <modname>.mod             ← OUTER descriptor with absolute `path=`
```

**Two descriptor files.** The OUTER `.mod` is what the launcher scans; it must contain a `path=` line pointing at the symlink target. The INNER `descriptor.mod` lives inside the mod folder and is read by the game engine itself.

## Three transformation patterns

Pick **one** before scaffolding. The choice determines the shape of `build.py`.

### A. Sentinel rewrite — for cap-lifting

Vanilla uses country flags as gates: `NOT { has_country_flag = built_X }` in `possible = { ... }` blocks. The same flag is set in `on_build_complete`. After first build, the gate fails.

The fix is **not** "replace built_X with a single sentinel everywhere." That reproduces the bug — the sentinel gets read AND set, so after first build it gates the second one. Use the asymmetric strategy:

- **Rewrite READS only**: `has_country_flag = built_X` → `has_country_flag = mmod_read_never_set`. Never written anywhere, so `NOT { has_country_flag = ... }` gates always pass.
- **Leave WRITES alone**: `set_country_flag = built_X` and `remove_country_flag = built_X` stay vanilla. Critical: external systems (focus cards, crisis events, scripted effects, room textures) read these flags. Rewriting writes silently breaks unrelated game systems. **Always grep vanilla for non-target reads before touching writes.**

Discover the flag set by intersection: any country flag both set AND read across the target vanilla directory, restricted to a naming convention (e.g. `built_<X>` prefix or `<X>_built` suffix for megastructures). Cross-file intersection, not per-file — flags often get set in file A and read in file B.

```python
def discover_tracking_flags(vanilla_dir: Path) -> set[str]:
    SET = re.compile(r"set_country_flag\s*=\s*([A-Za-z_0-9]+)")
    HAS = re.compile(r"has_country_flag\s*=\s*([A-Za-z_0-9]+)")
    set_flags, read_flags = set(), set()
    for p in vanilla_dir.glob("*.txt"):
        text = p.read_text(encoding="utf-8")
        set_flags |= set(SET.findall(text))
        read_flags |= set(HAS.findall(text))
    candidates = set_flags & read_flags
    return {f for f in candidates if f.startswith("built_") or f.endswith("_built")}
```

The transform is then a single regex `subn` per flag against the read pattern only.

### B. Multiplier transform — for scaling

For mods that triple resource yields, double planet sizes, etc. Walk vanilla files and multiply numeric values matching specific keys.

- **Multiply positives only.** `district_X_max_add = 3` becomes `9`; `district_X_max_add = -2` (blocker penalty) stays at `-2`. Negatives shouldn't grow proportionally to size or yield.
- **Skip `@VAR` references.** Lines like `district_max_add = @SOME_VAR` are computed at runtime — handle the variable in `common/scripted_variables/` (use a `zz_` filename prefix so your override loads after vanilla's `100_*` files, last-definition-wins).
- **Skip `upkeep = { ... }` blocks** unless symmetric scaling is the goal. Multiplying produces but not upkeep is intentional (and asymmetric — document it).
- **Use a brace-depth scanner for blocks**, not a regex with `{...}` — Clausewitz blocks nest. Pattern from `3x-bigger-worlds/scripts/build.py`:

```python
pattern = re.compile(r"produces\s*=\s*\{")
m = pattern.search(text, i)
depth = 1
j = m.end()
while j < len(text) and depth:
    if text[j] == "{": depth += 1
    elif text[j] == "}":
        depth -= 1
        if depth == 0: break
    j += 1
body = text[m.end():j]
# transform body, splice back in
```

### C. Direct override — for value replacement

User wants specific values changed (e.g. starting resources, ascension perk slot count). No transformation needed: copy the vanilla file into the mod and edit the literal numbers. A `build.py` may or may not be useful here — if it's a one-time edit and vanilla rarely changes, hand-edited is fine.

For variables (`@something = N` lines), prefer the `zz_` scripted_variables prefix over copying the whole file. Smaller surface = fewer patch conflicts.

## Workflow

### Phase 1: Scope (interview)

Ask the user, one question at a time:

1. **What's the mechanic?** (cap, scaling, value, content)
2. **Pattern fit?** (A/B/C from above — derive from their answer; if you can't, ask)
3. **Target vanilla files?** Often grep-discoverable. If not, ask.
4. **Compatibility constraints?** Co-installation with which other mods? Last-loaded wins on shared file overrides — surface conflicts up front.
5. **Stellaris version?** Read `Stellaris/launcher-settings.json` `rawVersion`. Plan `supported_version` in descriptor accordingly (use `v4.3.*` wildcard, not pinned).

Cap at 5 questions. The patterns are constrained; you usually have what you need fast.

### Phase 2: Discover

Greps that always pay off:

```bash
# What modifies the knob the user cares about?
grep -rE "district_[a-z_]+_max_add" "<vanilla>/common/deposits/" | head

# What flags / variables gate the behavior?
grep -rh "has_country_flag = " "<vanilla>/common/<target>/" | sort -u

# Where does an identifier appear across vanilla? (catches cross-system reads)
grep -rE "has_country_flag\s*=\s*<flag_name>\b" "<vanilla>/" | grep -v "common/<target>/"
```

Always grep for cross-system readers before touching writes (Pattern A). This is the step that prevented breaking focus cards / crisis events in Multi-Megastructures.

### Phase 3: Scaffold + generate

Create the directory layout shown above. Files to write:

- `mod/descriptor.mod` (inner) — see template below
- `scripts/build.py` — pattern-specific transform, deterministic header in each output file
- `scripts/preflight.py` — see the minimum check set below
- `scripts/deploy.sh` — see template
- `README.md`, `TESTING.md` — describe the mod and verification plan
- `mod/thumbnail.png` — see Thumbnail section

Run `build.py`. Inspect a few generated files by hand to sanity-check the diff. Brace-count any non-trivially-transformed file.

### Phase 4: Preflight

Run `python3 scripts/preflight.py`. Iterate until all checks PASS. **Do not deploy or launch until preflight is green** — preflight failures are the cheap-to-fix bugs.

Hard-won lesson: when preflight catches something, it usually catches it because the bug museum already documented that failure mode. Don't disable a check to make it pass; fix the build.

### Phase 5: Deploy + smoke test

```bash
scripts/deploy.sh                     # symlink + outer .mod
# Launch Stellaris → Paradox Launcher → Mods → enable → Play
```

Smoke test in-game per `TESTING.md`. Tail the error log:

```bash
tail -f "~/Documents/Paradox Interactive/Stellaris/logs/error.log"
```

Any error mentioning your override files is a regression.

## Templates

### Inner descriptor.mod

```
name="<Display Name>"
version="0.1.0"
tags={
	"Gameplay"
}
supported_version="v4.3.*"
picture="thumbnail.png"
```

After Workshop upload, the Paradox launcher will inject `remote_file_id="<id>"`. Preserve it in the repo so future deploys retain the Workshop link.

### deploy.sh

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_MOD_DIR="$(cd "${SCRIPT_DIR}/../mod" && pwd)"
MOD_NAME="<modname>"
STELLARIS_USER_DIR="${HOME}/Documents/Paradox Interactive/Stellaris/mod"
mkdir -p "${STELLARIS_USER_DIR}"
LINK="${STELLARIS_USER_DIR}/${MOD_NAME}"
OUTER="${STELLARIS_USER_DIR}/${MOD_NAME}.mod"
if [ -L "${LINK}" ] || [ -e "${LINK}" ]; then rm -rf "${LINK}"; fi
ln -s "${REPO_MOD_DIR}" "${LINK}"
{ cat "${REPO_MOD_DIR}/descriptor.mod"; echo "path=\"${LINK}\""; } > "${OUTER}"
```

Idempotent. Symlink target points at the repo, so `build.py` reruns are picked up immediately — no re-deploy needed.

## Preflight checks (minimum set)

| Check | Catches |
|------|---------|
| Brace balance on every generated file | Transform that drops a `}` and silently corrupts the parser |
| Top-level keys match vanilla (no drops, no extras) | Transform that accidentally strips a whole entity definition |
| Pattern-specific spot check (sentinel present, multiplier applied, etc.) | Transform didn't fire on a file |
| `has_no_non_gate_megastructure` (or equivalent gate) rewritten | Forgotten per-system gate |
| Pattern A: read sentinel never appears in `set_country_flag` / `remove_country_flag` | The same-flag-for-read-and-write bug |
| Pattern B: byte-for-byte negative-value preservation (list compare, not count) | Multiplier accidentally applied to negatives |
| Every `give_technology = { tech = X }` exists in vanilla `common/technology/` | Typo'd or renamed tech ID |
| Every on_action name (e.g. `on_game_start_country`) is a real vanilla on_action | Hook typo makes the whole mod a no-op |
| Every event id referenced from on_actions is defined in the mod's events file | Orphan event reference |
| Localisation YAML files start with `\xef\xbb\xbf` (UTF-8 BOM) | Strings render as raw keys otherwise |
| `descriptor.mod` present with `supported_version=` | Launcher refuses to load the mod |
| If deployed: symlink resolves into repo; outer `.mod` `path=` is absolute and equal to the deployed symlink path | `Path.exists()` returns False on broken symlinks — use `path.is_symlink()` too |
| `thumbnail.png` is a real PNG (magic bytes `89 50 4E 47`), 512×512, no alpha (color_type 2), under 1 MB | Workshop preview breaks otherwise; see Thumbnail section |

Skeleton:

```python
def fail(check, detail): failures.append(f"{check}: {detail}")
def ok(check, detail):   passes.append(f"{check}: {detail}")

def c1_brace_balance(): ...
def c2_pattern_specific_leak_check(): ...
# ...
def main():
    if not VANILLA_ROOT.exists(): print("ERROR: ..."); return 2
    c1_brace_balance(); c2_...; ...
    for line in passes: print(f"PASS {line}")
    for line in failures: print(f"FAIL {line}", file=sys.stderr)
    return 1 if failures else 0
```

## Thumbnail handling

Two separate concerns, easy to confuse:

1. **The launcher's in-app tile** (Mod Library list).
2. **The Steam Workshop preview image** (when uploaded).

Both come from `mod/thumbnail.png` referenced by `picture="thumbnail.png"` in the descriptor — but the launcher only renders the tile after the mod has been through the **Mod Tools → Upload a Mod** workflow at least once. Local-only mods show a placeholder icon, even with a valid thumbnail in the mod folder. This is launcher behavior, not a bug — surface it to the user so they know what to expect.

### Format requirements (preflight C-thumbnail enforces these)

- Magic bytes start with `89 50 4E 47 0D 0A 1A 0A` (real PNG, not JPEG bytes in a `.png` filename — the launcher cache stored multi-megastructures' first thumbnail as `.jpg` because the file was JPEG-encoded).
- 512×512 pixels.
- No alpha channel (PNG color type 2 = RGB; not type 6 = RGBA). Some Paradox tooling chokes on RGBA.
- Under 1 MB (Workshop preview limit).

Re-encode any input with `sips`:

```bash
sips -s format png -Z 512 input.<ext> --out mod/thumbnail.png
```

For programmatic generation, the simplest path is the Gemini image API (`gemini-2.5-flash-image` or `gemini-3-pro-image-preview`). Save raw to `thumbnail-src.png`, then re-encode via `sips`. On Linux, substitute `convert` (ImageMagick).

## Gotchas (the bug museum)

Each line cost real debugging time. Honor them.

- **Same flag for read + write reintroduces the cap after first build.** Multi-megastructures shipped with this bug; CodeRabbit caught it. Use distinct read/write sentinels OR rewrite only reads (preferred — keeps external readers working).
- **External systems read the "built_X" flags.** Focus cards, crisis events, scripted effects, room textures. Always grep cross-file before rewriting writes.
- **`built_<X>` vs `<X>_built`** are both valid naming conventions. Discover from vanilla, don't hard-code a prefix-only regex (`cosmogenesis_world_built` will be missed).
- **`Path.exists()` returns False on broken symlinks.** Preflight skipped a broken deploy as "not deployed." Use `path.is_symlink()` as the deploy-attempt sentinel, and validate `path=` is absolute and equals the expected target.
- **Empty `if = { limit = { } }` blocks** that result from over-aggressive stripping can produce game warnings. Prefer rewriting-to-sentinel over stripping entirely; structure stays intact.
- **Localisation YAML without UTF-8 BOM.** Strings render as raw keys silently. Prepend `\xef\xbb\xbf`.
- **JPEG bytes in a `.png` filename.** Browsers tolerate it, Stellaris launcher doesn't — Workshop preview broke. Always verify magic bytes.
- **Launcher local-mod-thumbnail cache** lives at `~/Documents/Paradox Interactive/Stellaris/.launcher-cache/local-mod-thumbnail-<uuid>/`. Populated by the Upload Mod workflow, not by adding the mod. A local mod with a valid thumbnail in `mod/thumbnail.png` will still show a placeholder tile until first upload — by design.
- **Outer `.mod` vs inner `descriptor.mod`.** Outer is what the launcher scans, has `path=`. Inner has no `path=` and lives in the mod folder. Both must exist; `deploy.sh` writes the outer from the inner plus a `path=` line.
- **Workshop CDN caches thumbnails aggressively.** A re-upload may take minutes to refresh on the Workshop page. Hard-refresh the browser; wait 5-15 min.
- **`country_megastructure_build_cap_add` modifier** was a 3.x-era mechanic. Doesn't exist in 4.x. Don't follow stale tutorials.
- **AI weights are tuned for the vanilla world.** Removing a build cap doesn't make AI spam the structure — `ai_weight` blocks need separate tuning. Document this as a known caveat instead of trying to fix it unless the user explicitly asks for AI changes.
- **`give_technology = { tech = X }`** bypasses ascension-perk gates. Granting a Galactic-Wonders-locked tech directly works; you don't need to also unlock the perk.
- **Pre-commit hooks (ruff, semgrep, gitleaks)** may run on commit. Fix the underlying issue rather than `--no-verify`. The hook isn't lying.

## Rules (non-negotiable)

- **Preflight before deploy. Deploy before launch.** Never present "the mod works" to the user without running preflight + a smoke test.
- **Don't rewrite writes without grepping for cross-system readers.** Always.
- **Pattern A uses two distinct sentinels OR rewrite-reads-only.** Never the same sentinel for both.
- **Match vanilla file names exactly** in the override folder. The engine identifies overrides by filename.
- **Don't pin `supported_version=`** to a single point release. Use `v<MAJOR>.<MINOR>.*`.
- **Don't fight the launcher local-mod tile placeholder** — explain it to the user instead. The fix is "upload once."
- **Localisation YAML always needs BOM.** Always.
- **Real PNG bytes for thumbnails.** Always. Re-encode anything coming from an image API.

## Output

A working Stellaris mod with: `build.py` that regenerates from vanilla on patch, `preflight.py` that catches the bug-museum failure modes, `deploy.sh` that creates the symlink and outer descriptor, a `README.md`/`TESTING.md`, and a real-PNG thumbnail. The user can subscribe to vanilla updates, re-run `build.py`, re-run `preflight.py`, and ship.
