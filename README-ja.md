# sockat

> [English](./README.md) | 日本語

`sun_path` の上限 (NUL 込みで macOS と BSD は 104 バイト、Linux は 108 バイト) を超えるパスでも、Unix domain socket を bind / connect できるライブラリ。言語ごとに実装があり、このリポは言語によらない仕様の正本と、各実装への入口。

## 使い方

標準の bind / connect を sockat に書き換えるだけ。戻り値は標準と同じ型で、短いパスは標準にそのまま渡すので振る舞いは変わらない。Rust で示す (各言語も同じ形。言語ごとの例は各リポの README)。

```rust
// let listener = std::os::unix::net::UnixListener::bind(&path)?;
let listener = sockat::bind(&path)?;

// let stream = std::os::unix::net::UnixStream::connect(&path)?;
let stream = sockat::connect(&path)?;
```

DGRAM も同じ (`sockat::datagram::bind` 等)。

## 知っておくこと

- 長いパスで bind すると、`/tmp/sockat-<uid>/` に小さなディレクトリと symlink が残る (OS の一時ディレクトリの掃除で消える)。試験を何度も回す環境では `sweep()` を 1 回呼べば片付く
- 長いパスでは、listener のアドレス (`local_addr` / `getsockname`) が渡したパスと違う短い綴りになる。ソケットのファイルを消す時は、アドレスでなく元のパスで消す
- 後始末や、どの経路を通ったかが要る時は `_ex` 付きの関数を使う

## 言語ごとの実装

| 言語 | リポ | パッケージ | 状態 |
|---|---|---|---|
| Rust | [kawaz/sockat-rs](https://github.com/kawaz/sockat-rs) | crates.io の [`sockat`](https://crates.io/crates/sockat) | 公開済み (0.5.1) |
| Python | [kawaz/sockat-py](https://github.com/kawaz/sockat-py) | PyPI の [`sockat`](https://pypi.org/project/sockat/) | 公開済み (0.3.0) |
| Go | [kawaz/sockat-go](https://github.com/kawaz/sockat-go) | [`github.com/kawaz/sockat-go`](https://pkg.go.dev/github.com/kawaz/sockat-go) | 公開済み (v0.4.0。macOS の広げた sockaddr なし) |
| JavaScript / TypeScript | [kawaz/sockat-ts](https://github.com/kawaz/sockat-ts) | npm の [`@kawaz/sockat`](https://www.npmjs.com/package/@kawaz/sockat) | 公開済み (0.1.0。Node 22 以上と Bun。native 抜きで、スレッドの cwd・`bindat` / `connectat`・広げた sockaddr の経路なし) |
| Ruby | kawaz/sockat-rb | RubyGems | 予定 |

## 仕組みと詳しい振る舞い

- [docs/SPEC-ja.md](./docs/SPEC-ja.md) — 言語によらない仕様 (公開する操作、resolve、綴りの性質、片付け、経路の試す順、使ってはいけない書き方、エラー、各実装に求めること)
- [docs/SPEC-routes-ja.md](./docs/SPEC-routes-ja.md) — 経路の作り方 (置き場 B の作り方、各経路の手順。実装者向け)
- [docs/decisions/](./docs/decisions/INDEX.md) — 仕様と構成の判断 (DR)。今の設計の正本は [DR-0017](./docs/decisions/DR-0017-resolve-through-persistent-base.md)
- [docs/design/conformance.md](./docs/design/conformance.md) — 言語によらない適合試験
- [pages/](./pages/) — 届く範囲の表、Q&A

## ライセンス

MIT License, Yoshiaki Kawazu (@kawaz)
