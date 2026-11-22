# sockat

> English | [日本語](./README-ja.md)

Your Unix domain socket path is too long to bind / connect. sockat makes that go away.

| Language | If you see this error | sockat |
|---|---|---|
| Rust | `path must be shorter than SUN_LEN` | [sockat-rs](https://github.com/kawaz/sockat-rs) |
| Python | `OSError: AF_UNIX path too long` | [sockat-py](https://github.com/kawaz/sockat-py) |
| Go | `listen unix /…/app.sock: bind: invalid argument` | [sockat-go](https://github.com/kawaz/sockat-go) |
| Node.js / Bun | `Error: listen EINVAL: invalid argument /…/app.sock` | [sockat-ts](https://github.com/kawaz/sockat-ts) |

Replace the standard bind / connect with sockat's, and long paths just work. Here it is in Rust (the other languages have the same shape; see the links in the table).

```rust
// let listener = UnixListener::bind(&path)?;
let listener = sockat::bind(&path)?;

// let stream = UnixStream::connect(&path)?;
let stream = sockat::connect(&path)?;
```

You get back the same types as the standard, and short paths go to the standard unchanged, as before. Only for a long path does sockat quietly set up a short way to the same place and connect through it. You don't need to shorten paths yourself or care about each OS's limit.

## There is a CLI too

Handy for trying sockat out before embedding it in your app.

```console
$ sockat /very/long/…/app.sock
/private/tmp/sockat-501/f21ddd85c65f/app.sock

$ sockat --json /very/long/…/app.sock
{
  "path": "/private/tmp/sockat-501/f21ddd85c65f/app.sock",
  "bytes": 45,
  "limit": 103,
  …
}
```

How to install and use it is in [the sockat command](./pages/cli.md).

## More

- [User manual](./pages/manual.md)
- [Reference](./pages/reference.md)
- [How it works](./pages/technical.md)

## License

MIT License, Yoshiaki Kawazu (@kawaz)
