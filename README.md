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
| Rust | [kawaz/sockat-rs](https://github.com/kawaz/sockat-rs) | [`sockat`](https://crates.io/crates/sockat) on crates.io | published (0.5.1) |
| Python | [kawaz/sockat-py](https://github.com/kawaz/sockat-py) | [`sockat`](https://pypi.org/project/sockat/) on PyPI | published (0.3.0) |
| Go | [kawaz/sockat-go](https://github.com/kawaz/sockat-go) | [`github.com/kawaz/sockat-go`](https://pkg.go.dev/github.com/kawaz/sockat-go) | published (v0.4.0; no widened sockaddr on macOS) |
| JavaScript / TypeScript | kawaz/sockat-ts | npm | planned |
| Ruby | kawaz/sockat-rb | RubyGems | planned |

Usage is in each repository's README.

## Common behavior

The design of [DR-0017](./docs/decisions/DR-0017-resolve-through-persistent-base.md) (Japanese). Each language's implementation is being rebuilt to this design; the behavior of the published versions is in each repository's README.

- Returns the same socket types the language's standard bind / connect return
- Even for a long path, the socket file is created at the path given
- A long path is turned (resolved) into a short spelling that goes through a directory D per process and a symlink E, created inside a base B per user (`/tmp` first, then `$XDG_RUNTIME_DIR`, `$TMPDIR`, the socket's directory), and bound / connected with it
- A bind's spelling is kept. While it lives, upper libraries that remove by the `getsockname` spelling and DGRAM replies work as with the original path. So a bind at a long path leaves D and E outside the app's own directories (`/tmp/sockat-<uid>` etc.; they go with the OS's temporary-directory cleaning or `sweep()`. Removing a live process's D by hand only makes the spelling unreachable; the socket at the original path keeps working. Where tests run over and over, one call of `sweep()` removes the dead D. [What stays in the base](./docs/SPEC.md#what-stays-in-the-base))
- A bind at a length whose spelling does not fit is reached with a throwaway thread's cwd (`bindat` on FreeBSD). On OSes where bind follows a final symlink (macOS etc.), a bind goes through a symlink to the socket file, so there is no limit on the file name's length
- `connect` tries routes that need neither writing nor a thread (/proc, relative path, widened sockaddr, `connectat`) first, then a throwaway thread, and a symlink in the base last. The default connect leaves no state in the process
- To hand the spelling to the standard library yourself, use resolve (`resolve_for_bind` / `resolve_for_connect`)
- sockat never forks
- No route changes the cwd of the calling process or thread
- When a route actually binds / connects and fails, that error is returned and no later route is tried
- For a long path, the address the kernel reports (`getsockname` / `getpeername`) is the bind's spelling, not the original path. Whether it can be used later is told by the spelling properties (`Spelling`) `_ex` returns. Languages that can substitute it while keeping the standard type return the original path
- `remove()` of `_ex` removes only the socket file it created (it does not close the listener). sockat does not clean up B and D and leaves them to the OS's temporary-directory cleaning (`sweep()` removes the D of dead processes when called)
- Windows is not supported

## Documentation

- [docs/SPEC.md](./docs/SPEC.md) — the language-independent specification (operations, resolve, spelling properties, cleanup, the order of routes, patterns not to use, errors, what each implementation must do)
- [docs/SPEC-routes.md](./docs/SPEC-routes.md) — how the routes are built (building the base B, each route's steps; for implementers)
- [docs/decisions/](./docs/decisions/INDEX.md) — decisions on the specification and how this repository is organized (DR, Japanese)
- [docs/decisions/DR-0017](./docs/decisions/DR-0017-resolve-through-persistent-base.md) — the decision on the long-path routes and the API, and rejected alternatives (Japanese)
- [docs/design/conformance.md](./docs/design/conformance.md) — the language-independent conformance test (each language's test CLI input and output, the table of cases) (Japanese)

## License

MIT License, Yoshiaki Kawazu (@kawaz)
