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
| Python | [kawaz/sockat-py](https://github.com/kawaz/sockat-py) | [`sockat`](https://pypi.org/project/sockat/) on PyPI | published (no fork route) |
| Go | [kawaz/sockat-go](https://github.com/kawaz/sockat-go) | [`github.com/kawaz/sockat-go`](https://pkg.go.dev/github.com/kawaz/sockat-go) | published (no fork route, no widened sockaddr on macOS) |
| JavaScript / TypeScript | kawaz/sockat-ts | npm | planned |
| Ruby | kawaz/sockat-rb | RubyGems | planned |

Usage is in each repository's README.

## Common behavior

- Returns the same socket types the language's standard bind / connect return
- Even for a long path, the socket file is created at the path given
- A long path is bound / connected through a short spelling: sockat creates a directory of its own, holds it by fd, and goes through a randomly named symlink placed inside it, then cleans up
- The means of resolving against that directory's fd are tried per OS in a fixed order (thread cwd, bindat / connectat, /proc, fork). `connect` tries routes that need neither writing nor a thread (/proc, relative path, widened sockaddr) first
- On OSes where bind follows a final symlink (macOS etc.), a bind goes through a symlink to the socket file, so there is no limit on the file name's length
- No route changes the cwd of the calling process or thread
- `connect` never forks. Only `bind` and the `connect_ex` variants with the last resort fork, and only as the last resort when no other means works
- When a route actually binds / connects and fails, that error is returned and no later route is tried
- For a long path, the address the kernel reports (`getsockname` / `getpeername`) is not the original path (a spelling that normally matches nothing when resolved later; remove by the original path). Languages that can substitute it while keeping the standard type return the original path; elsewhere the caller keeps the original path
- The bind with cleanup (`bind_ex` and the like) has `discard()`, which removes only the socket file it created (it does not close the listener)
- Windows is not supported

## Documentation

- [docs/SPEC.md](./docs/SPEC.md) — the language-independent specification (routes, order, what is lost, patterns not to use, errors, what each implementation must do)
- [docs/decisions/](./docs/decisions/INDEX.md) — decisions on the specification and how this repository is organized (DR, Japanese)
- [docs/decisions/DR-0017](./docs/decisions/DR-0017-resolve-through-persistent-base.md) — the decision on the long-path routes and the API, and rejected alternatives (Japanese)
- [docs/design/conformance.md](./docs/design/conformance.md) — the language-independent conformance test (each language's test CLI input and output, the table of cases) (Japanese)

## License

MIT License, Yoshiaki Kawazu (@kawaz)
