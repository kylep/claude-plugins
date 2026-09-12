# peloton

Skills for treating a Peloton bike/tread tablet as the Android device it is. Everything runs over wireless ADB from a laptop on the same LAN; no root, no cable, and every device change is reversible.

## Install

```text
/plugin marketplace add kylep/claude-plugins
/plugin install peloton@pai-plugins
```

## Skills

- **sideloading-peloton-apps**: connect over wireless debugging (pairing persists, the port doesn't), install APKs and a launcher, and diagnose/undo the post-reboot membership gate (`com.onepeloton.systempluginui`) that force-stops third-party apps with a "must be logged in to a Peloton membership" toast. Ships `scripts/peloton_adb.py` with `connect`, `stable-port`, `status`, `packages`, `install`, `launch`, `diagnose`, `unblock`, `reblock`.

## Layout

```
skills/<skill-name>/
├── SKILL.md                    # when to use + the recipe
└── scripts/peloton_adb.py      # stdlib CLI wrapping adb; --help for subcommands
```

Tests live in the repo's `tests/` suites (`unit` + `integration`, fully mocked adb).

## License

MIT — see the [repository LICENSE](../../LICENSE).
