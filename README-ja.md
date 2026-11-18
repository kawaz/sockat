# sockat

> [English](./README.md) | 日本語

`sun_path` の上限 (NUL 込みで macOS と BSD は 104 バイト、Linux は 108 バイト) を超えるパスでも、Unix domain socket を bind / connect できるライブラリ。言語ごとに実装があり、このリポは言語によらない仕様の正本と、各実装への入口。

## 何を解決するか

- 標準ライブラリの bind / connect は `sun_path` に収まらないパスを断る。深い一時ディレクトリ (macOS の `$TMPDIR` だけで 50 バイト前後) に置くとすぐ当たる
- 上限が効くのは `bind(2)` / `connect(2)` に渡す引数の長さだけなので、sockat は同じ場所を指す短い綴りでカーネルに渡す
- 標準ライブラリが受け付けるパス (多くは `sun_path` − 1 バイトまで) は、そのまま標準ライブラリに渡す

## 言語ごとの実装

| 言語 | リポ | パッケージ | 状態 |
|---|---|---|---|
| Rust | [kawaz/sockat-rs](https://github.com/kawaz/sockat-rs) | crates.io の [`sockat`](https://crates.io/crates/sockat) | 公開済み |
| Python | [kawaz/sockat-py](https://github.com/kawaz/sockat-py) | PyPI の [`sockat`](https://pypi.org/project/sockat/) | 公開済み (fork の経路と `connect_any` 系なし) |
| Go | kawaz/sockat-go | `github.com/kawaz/sockat-go` | 予定 |
| JavaScript / TypeScript | kawaz/sockat-ts | npm | 予定 |
| Ruby | kawaz/sockat-rb | RubyGems | 予定 |

使い方は各リポの README にある。

## 共通の振る舞い

- 戻り値は、その言語の標準の bind / connect が返すのと同じソケットの型
- 長いパスでも、ソケットファイルは渡したパスにできる
- 長いパスは OS ごとの経路 (/proc、bindat、相対パス、広げた sockaddr、symlink、fork) を決まった順に試す
- どの経路も呼び出し元の cwd を変えない
- `connect` は fork しない。fork するのは `bind` と `connect_any` 系だけ
- 経路が実際に bind / connect して失敗したら、そのエラーを返し、次の経路でやり直さない
- カーネルが返すアドレス (`getsockname` / `getpeername`) は元のパスでない。元のパスは呼び出し元が持つ
- Windows は対象外

## ドキュメント

- [docs/SPEC-ja.md](./docs/SPEC-ja.md) — 言語によらない仕様 (経路、試す順番、安全条件、エラー、各実装に求めること)
- [docs/decisions/](./docs/decisions/INDEX.md) — このリポの構成の判断 (DR)
- [sockat-rs の DR-0001](https://github.com/kawaz/sockat-rs/blob/main/docs/decisions/DR-0001-long-socket-path-routes.md) — 経路の設計の判断と却下した案

## ライセンス

MIT License, Yoshiaki Kawazu (@kawaz)
