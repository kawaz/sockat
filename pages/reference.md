# sockat reference

> English | [日本語](./reference-ja.md)

The details of the functions and types are in each language's API reference.

| Language | API reference |
|---|---|
| Rust | [docs.rs/sockat](https://docs.rs/sockat) |
| Python | [sockat-py reference](https://github.com/kawaz/sockat-py/blob/main/docs/REFERENCE.md#functions) |
| Go | [pkg.go.dev](https://pkg.go.dev/github.com/kawaz/sockat-go) |
| JavaScript / TypeScript | [sockat-ts reference](https://github.com/kawaz/sockat-ts/blob/main/docs/REFERENCE.md) |

For the command line, see [the sockat command](./cli.md).

## What APIs there are

These are the APIs. The names are the Rust ones; the other languages use names that follow their own conventions.

| API | What it does |
|---|---|
| `bind(path)` | binds even at a long path and returns a listening standard listener |
| `connect(path)` | connects even to a long path and returns a standard stream |
| `connect_nonblocking(path)` | connects without waiting (for async runtimes) |
| `datagram::bind(path)`<br>`datagram::unbound()`<br>`datagram::connect(&sock, path)` | binds / connects a DGRAM socket |
| `bind_ex(path, options)`<br>`connect_ex(path, options)` etc. | does the same as above, and also returns a handle that removes the socket file and information on how it was reached |
| `resolve_for_bind(path, options)`<br>`resolve_for_connect(path, options)` | does not bind / connect; returns only the short path |
| `sweep()`<br>`sweep_base(path)` | cleans up what sockat made behind the scenes and is no longer in use (`sweep_base` does it for the place given by `base`) |

Some languages lack some of these (DGRAM in TypeScript, etc.). Check that language's reference.

## Specification

The promise every language's implementation follows is in the [specification](../docs/SPEC.md).
