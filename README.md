# sockat

> English | [日本語](./README-ja.md)

Libraries that bind and connect Unix domain sockets whose path is longer than `sun_path` allows (104 bytes with the NUL on macOS and the BSDs, 108 on Linux). There is an implementation per language; this repository holds the language-independent specification and leads to each implementation.

## Usage

Replace the standard bind / connect with sockat's. The return types are the standard ones, and a short path is handed to the standard unchanged, so nothing changes for it. Shown in Rust (every language has the same shape; each repository's README has its own examples).

```rust
// let listener = std::os::unix::net::UnixListener::bind(&path)?;
let listener = sockat::bind(&path)?;

// let stream = std::os::unix::net::UnixStream::connect(&path)?;
let stream = sockat::connect(&path)?;
```

DGRAM is the same (`sockat::datagram::bind` etc.).

## Good to know

- A bind at a long path leaves a small directory and a symlink in `/tmp/sockat-<uid>/` (the OS's temporary-directory cleaning removes them). Where tests run over and over, one call of `sweep()` cleans them up
- For a long path, the listener's address (`local_addr` / `getsockname`) is a short spelling different from the path given (Python and TypeScript return the original path when the socket's own address is asked). Remove the socket file by the original path, not by the address
- When you need cleanup or which route was taken, use the functions with `_ex`

## Implementations

| Language | Repository | Package | Status |
|---|---|---|---|
| Rust | [kawaz/sockat-rs](https://github.com/kawaz/sockat-rs) | [`sockat`](https://crates.io/crates/sockat) on crates.io | published (0.5.1) |
| Python | [kawaz/sockat-py](https://github.com/kawaz/sockat-py) | [`sockat`](https://pypi.org/project/sockat/) on PyPI | published (0.3.2) |
| Go | [kawaz/sockat-go](https://github.com/kawaz/sockat-go) | [`github.com/kawaz/sockat-go`](https://pkg.go.dev/github.com/kawaz/sockat-go) | published (v0.4.1; no widened sockaddr on macOS) |
| JavaScript / TypeScript | [kawaz/sockat-ts](https://github.com/kawaz/sockat-ts) | [`@kawaz/sockat`](https://www.npmjs.com/package/@kawaz/sockat) on npm | published (0.1.1; Node 22+ and Bun; no native code, so no thread-cwd, `bindat` / `connectat` or widened-sockaddr routes) |
| Ruby | kawaz/sockat-rb | RubyGems | planned |

## How it works and the details

- [docs/SPEC.md](./docs/SPEC.md) — the language-independent specification (operations, resolve, spelling properties, cleanup, the order of routes, patterns not to use, errors, what each implementation must do)
- [docs/SPEC-routes.md](./docs/SPEC-routes.md) — how the routes are built (building the base B, the steps of each route; for implementers)
- [docs/decisions/](./docs/decisions/INDEX.md) — decisions on the specification and the layout (DR, Japanese). The current design is [DR-0017](./docs/decisions/DR-0017-resolve-through-persistent-base.md)
- [docs/design/conformance.md](./docs/design/conformance.md) — the language-independent conformance tests (Japanese)
- [pages/](./pages/) — the reach table, Q&A, [per-language caveats](./pages/langs.md)

## License

MIT License, Yoshiaki Kawazu (@kawaz)
