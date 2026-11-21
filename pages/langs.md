# Per-language caveats

> English | [日本語](./langs-ja.md)

Caveats specific to each language's implementation (bugs and limits of its standard library or runtime). The details are in each repository. Caveats common to all languages are in the [SPEC](../docs/SPEC.md): "What differs from the standard for a long path", "Patterns not to use", "What stays in the base".

| Language | Caveat | Details |
|---|---|---|
| Rust | On OpenBSD, Rust 1.99 and earlier std's `local_addr`, `peer_addr` and `recv_from` drop the last byte of the path (fixed in 1.100). Replying over DGRAM to the address from `recv_from` needs 1.100 or later | [sockat-rs](https://github.com/kawaz/sockat-rs) |
| Go | No widened-sockaddr route on macOS | [sockat-go](https://github.com/kawaz/sockat-go) |
| Go | The standard `UnixListener.Close` unlinks by the spelling. A `ListenEx` listener does not remove the file when closed (`SetUnlinkOnClose(false)`) | [sockat-go](https://github.com/kawaz/sockat-go) |
| TypeScript | No native code, so no thread-cwd, `bindat` / `connectat` or widened-sockaddr routes | [sockat-ts](https://github.com/kawaz/sockat-ts) |
| TypeScript | On Linux, Bun itself does not start when `/proc` is not visible (Node runs) | [sockat-ts](https://github.com/kawaz/sockat-ts) |
| TypeScript | A `bindEx` listener unlinks by the spelling when closed, as the standard does (neither Node nor Bun offers a way to stop it) | [sockat-ts](https://github.com/kawaz/sockat-ts) |
