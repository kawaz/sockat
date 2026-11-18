# sockat

> English | [日本語](./README-ja.md)

Libraries that bind and connect Unix domain sockets whose path is longer than `sun_path` allows (104 bytes with the NUL on macOS and the BSDs, 108 on Linux). There is an implementation per language; this repository holds the language-independent specification and leads to each implementation.

## What it solves

- The standard library bind / connect refuses a path that does not fit in `sun_path`. A socket in a deep temporary directory (macOS's `$TMPDIR` alone is about 50 bytes) hits it quickly
- The limit applies only to the argument handed to `bind(2)` / `connect(2)`, so sockat hands the kernel a short spelling of the same place
- A path the standard library accepts (usually up to `sun_path` − 1 bytes) is handed to it unchanged

## Implementations

| Language | Repository | Package | Status |
|---|---|---|---|
| Rust | [kawaz/sockat-rs](https://github.com/kawaz/sockat-rs) | [`sockat`](https://crates.io/crates/sockat) on crates.io | published |
| Python | [kawaz/sockat-py](https://github.com/kawaz/sockat-py) | [`sockat`](https://pypi.org/project/sockat/) on PyPI | published (no fork route, no `connect_any` variants) |
| Go | kawaz/sockat-go | `github.com/kawaz/sockat-go` | planned |
| JavaScript / TypeScript | kawaz/sockat-ts | npm | planned |
| Ruby | kawaz/sockat-rb | RubyGems | planned |

Usage is in each repository's README.

## Common behavior

- Returns the same socket types the language's standard bind / connect return
- Even for a long path, the socket file is created at the path given
- A long path is tried on per-OS routes (/proc, bindat, relative path, widened sockaddr, symlink, fork) in a fixed order
- No route changes the caller's cwd
- `connect` never forks. Only `bind` and the `connect_any` variants fork
- When a route actually binds / connects and fails, that error is returned and no later route is tried
- The address the kernel reports (`getsockname` / `getpeername`) is not the original path. The caller keeps the original path
- Windows is not supported

## Documentation

- [docs/SPEC.md](./docs/SPEC.md) — the language-independent specification (routes, order, safety conditions, errors, what each implementation must do)
- [docs/decisions/](./docs/decisions/INDEX.md) — decisions on how this repository is organized (DR, Japanese)
- [sockat-rs's DR-0001](https://github.com/kawaz/sockat-rs/blob/main/docs/decisions/DR-0001-long-socket-path-routes.md) — design decisions on the routes and rejected alternatives (Japanese)

## License

MIT License, Yoshiaki Kawazu (@kawaz)
