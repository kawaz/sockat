# Per-language caveats

> English | [日本語](./langs-ja.md)

Caveats specific to each language's implementation (bugs and limits of its standard library or runtime). The details are in each repository. Caveats common to all languages are in the [SPEC](../docs/SPEC.md): "What differs from the standard for a long path", "Patterns not to use", "What stays in the base", "sweep".

| Language | Caveat | Details |
|---|---|---|
| Rust | On OpenBSD, Rust 1.99 and earlier std's `local_addr`, `peer_addr` and `recv_from` drop the last byte of the path (fixed in 1.100). Replying over DGRAM to the address from `recv_from` needs 1.100 or later | [sockat-rs](https://github.com/kawaz/sockat-rs/blob/main/docs/MANUAL.md#caveats-specific-to-rust) |
| Go | No widened-sockaddr route on macOS | [sockat-go](https://github.com/kawaz/sockat-go) |
| Go | The standard `UnixListener.Close` unlinks by the spelling. A `ListenEx` listener does not remove the file when closed (`SetUnlinkOnClose(false)`) | [sockat-go](https://github.com/kawaz/sockat-go) |
| Python | A socket returned for a long path (and `datagram.unbound()`) is a subclass of `socket.socket` whose `getsockname()` / `getpeername()` return the original path. `type(x) is socket.socket` is false, and rebuilding it with `socket.fromfd` brings back the kernel's spelling | [sockat-py](https://github.com/kawaz/sockat-py/blob/main/docs/MANUAL.md#notes-specific-to-python) |
| Python | asyncio's `start_unix_server(sock=)` removes the socket file at the original path on close in 3.13 and later (3.11 / 3.12 do not) | [sockat-py](https://github.com/kawaz/sockat-py/blob/main/docs/MANUAL.md#asyncio) |
| Python | `_ex` lives in `sockat.ex` (to avoid confusion with `socket.socket.connect_ex`) and is not loaded by `import sockat` | [sockat-py](https://github.com/kawaz/sockat-py/blob/main/docs/MANUAL.md#notes-specific-to-python) |
| Python | `os.path.abspath`, `normpath` and `relpath` fold `..` lexically. To make a relative path absolute, use `os.path.join(os.getcwd(), path)` | [sockat-py](https://github.com/kawaz/sockat-py/blob/main/docs/MANUAL.md#notes-specific-to-python) |
| TypeScript | No native code, so no thread-cwd, `bindat` / `connectat` or widened-sockaddr routes. When `usableCrossUid` cannot be met, `ENAMETOOLONG` | [sockat-ts](https://github.com/kawaz/sockat-ts/blob/main/README.md#how-a-long-path-is-reached) |
| TypeScript | On Linux without `flock(1)` (util-linux / busybox), a bind or resolve at a long path gets `ENAMETOOLONG` (the default connect still reaches). illumos has no way to lock and is the same | [sockat-ts](https://github.com/kawaz/sockat-ts/blob/main/README.md#how-a-long-path-is-reached) |
| TypeScript | On Linux, Bun itself does not start when `/proc` is not visible (Node runs) | [sockat-ts](https://github.com/kawaz/sockat-ts/blob/main/README.md#where-it-stops-reaching) |
| TypeScript | A `bindEx` listener unlinks by the spelling when closed, as the standard does (neither Node nor Bun offers a way to stop it). For a short path it could not remember, the original path is unlinked | [sockat-ts](https://github.com/kawaz/sockat-ts/blob/main/README.md#where-it-departs-from-spec) |
| TypeScript | No DGRAM or SEQPACKET (Node and Bun have none in their standard) | [sockat-ts](https://github.com/kawaz/sockat-ts/blob/main/README.md#where-it-departs-from-spec) |
| TypeScript | node:net reads a string that reads as a number as a TCP port, so `./` is put in front (`Spelling` stays `CwdRelative`) | [sockat-ts](https://github.com/kawaz/sockat-ts/blob/main/README.md#usage) |
