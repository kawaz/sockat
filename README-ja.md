# sockat

> [English](./README.md) | 日本語

Unix domain socket のパスが長すぎて bind / connect できない。sockat は、それを無くすライブラリです。

| 言語 | こんなエラーが出たら | sockat |
|---|---|---|
| Rust | `path must be shorter than SUN_LEN` | [sockat-rs](https://github.com/kawaz/sockat-rs) |
| Python | `OSError: AF_UNIX path too long` | [sockat-py](https://github.com/kawaz/sockat-py) |
| Go | `listen unix /…/app.sock: bind: invalid argument` | [sockat-go](https://github.com/kawaz/sockat-go) |
| Node.js / Bun | `Error: listen EINVAL: invalid argument /…/app.sock` | [sockat-ts](https://github.com/kawaz/sockat-ts) |

標準ライブラリの bind / connect を sockat に置き換えるだけで、長いパスでもそのまま動きます。Rust の例です (他の言語も同じ形で、表のリンク先にあります)。

```rust
// let listener = UnixListener::bind(&path)?;
let listener = sockat::bind(&path)?;

// let stream = UnixStream::connect(&path)?;
let stream = sockat::connect(&path)?;
```

返ってくるのは標準ライブラリと同じ型で、短いパスは今までどおり標準ライブラリにそのまま渡します。長いパスの時だけ、sockat が同じ場所を指す短い道を裏で用意してつなぎます。パスを短くする工夫も、OS ごとの上限も、気にしなくて構いません。

## CLI もあります

アプリに組み込む前のお試しに便利です。

```console
$ sockat /very/long/…/app.sock
/private/tmp/sockat-501/f21ddd85c65f4a0b93d7e1c2a85b6f30/app.sock

$ sockat --json /very/long/…/app.sock
{
  "path": "/private/tmp/sockat-501/f21ddd85c65f4a0b93d7e1c2a85b6f30/app.sock",
  "bytes": 65,
  "limit": 103,
  …
}
```

インストールと使い方は [sockat コマンド](./pages/cli-ja.md) にあります。

## もっと詳しく

- [利用マニュアル](./pages/manual-ja.md)
- [リファレンス](./pages/reference-ja.md)
- [技術説明](./pages/technical-ja.md)

## ライセンス

MIT License, Yoshiaki Kawazu (@kawaz)
