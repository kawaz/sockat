# sockat user manual

> English | [日本語](./manual-ja.md)

Replace the standard bind / connect with sockat's, and long paths just work ([README](../README.md)). How to install it and how to use it in detail in your language are in each language's manual.

| Language | Manual |
|---|---|
| Rust | [sockat-rs](https://github.com/kawaz/sockat-rs/blob/main/docs/MANUAL.md) |
| Python | [sockat-py](https://github.com/kawaz/sockat-py/blob/main/docs/MANUAL.md) |
| Go | [sockat-go](https://github.com/kawaz/sockat-go/blob/main/docs/MANUAL.md) |
| JavaScript / TypeScript | [sockat-ts](https://github.com/kawaz/sockat-ts/blob/main/docs/MANUAL.md) |

Below are the things you can do in every language. Function names are the Rust ones. The other languages have the same shape, with names that follow each language's conventions.

## DGRAM works too

Besides stream sockets, DGRAM sockets can bind / connect at a long path too.

```rust
let server = sockat::datagram::bind(&path)?;

let client = sockat::datagram::unbound()?;
sockat::datagram::connect(&client, &path)?;
```

A sender bound in a deep place still gets replies. Bind with the absolute path, and the sender address the receiver sees becomes an absolute path that fits the limit (with the standard alone, the absolute path is too long to bind, and a sender bound by a relative path cannot be replied to).

TypeScript has no DGRAM (the Node.js and Bun standards have none).

## Get just the short path

The simplest way is to replace bind / connect with sockat's, but there are also functions that only make the short path. Use them when you want to hand the path to another library or a standard function yourself.

```rust
let to = sockat::resolve_for_connect(&long_path, Default::default())?;
let stream = std::os::unix::net::UnixStream::connect(&to.path)?; // use it as many times as you like
to.cleanup()?; // when you are done
```

For bind, make the short path with `resolve_for_bind`. The short path you get back points to the same place as the original path.

## Let sockat remove the socket file too

`bind_ex` returns, along with the listener, a handle that removes the socket file it bound.

```rust
let bound = sockat::bind_ex(&path, Default::default())?;
// ... accept on bound.socket ...
bound.file.remove()?; // before closing the listener
drop(bound.socket);
```

It remembers the file it bound, so if that file has been replaced by another, it leaves it alone.

## Any depth of path is reached

A directory is reached however deep it is. A file name of ordinary length, like `daemon.sock`, is reached everywhere too. The exact limits per OS are in [the reach table](./reach/README.md).

## You don't need to worry about what is created behind the scenes

When binding at a long path, sockat creates a small directory and a symlink in `/tmp/sockat-<uid>/` and connects through a short way that passes there.

- They take almost no space, and the OS usually cleans up the ones no longer used
- connect leaves nothing behind
- To clean up, call `sweep()`; it removes only what is not in use. Where tests run over and over, one call at the end keeps them from piling up
- To choose the place yourself, pass the path of a directory reserved for sockat (e.g. `/tmp/my-app-1000/sockat`) in the `base` option of `bind_ex` and the like

## List of functions

See the [reference](./reference.md).

## How sockat makes the short way

See [how it works](./technical.md).
