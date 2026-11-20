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
| Python | [kawaz/sockat-py](https://github.com/kawaz/sockat-py) | PyPI の [`sockat`](https://pypi.org/project/sockat/) | 公開済み (fork の経路なし) |
| Go | [kawaz/sockat-go](https://github.com/kawaz/sockat-go) | [`github.com/kawaz/sockat-go`](https://pkg.go.dev/github.com/kawaz/sockat-go) | 公開済み (fork の経路なし。macOS の広げた sockaddr なし) |
| JavaScript / TypeScript | kawaz/sockat-ts | npm | 予定 |
| Ruby | kawaz/sockat-rb | RubyGems | 予定 |

使い方は各リポの README にある。

## 共通の振る舞い

[DR-0017](./docs/decisions/DR-0017-resolve-through-persistent-base.md) の設計。各言語の実装はこの設計へ作り直し中で、公開済みの版の振る舞いは各リポの README にある。

- 戻り値は、その言語の標準の bind / connect が返すのと同じソケットの型
- 長いパスでも、ソケットファイルは渡したパスにできる
- 長いパスは、利用者ごとの置き場 B (`/tmp` を先に、`$XDG_RUNTIME_DIR`、`$TMPDIR`、ソケットのディレクトリの順) の中に、プロセスごとのディレクトリ D と symlink E を作り、それを通る短い綴りに言い換えて (resolve) bind / connect する
- bind の綴りは消さずに残す。綴りが生きている間は、`getsockname` の綴りで消す上のライブラリや DGRAM の返信が元のパスと同じに働く
- 綴りが収まらない長さの bind は、使い捨てのスレッドの cwd (FreeBSD は `bindat`) で届かせる。bind が最後の要素の symlink を辿る OS (macOS 等) では、ソケットのファイルを指す symlink を通し、ファイル名の長さの上限が無い
- connect は、書き込みもスレッドも要らない経路 (/proc、相対パス、広げた sockaddr、`connectat`) を先に、次に使い捨てのスレッド、最後に置き場の symlink を試す。既定の connect はプロセスの中に状態を残さない
- 綴りを自分で標準ライブラリに渡したい時は resolve (`resolve_for_bind` / `resolve_for_connect`) を使う
- sockat は fork しない
- どの経路も呼び出し元のプロセスとスレッドの cwd を変えない
- 経路が実際に bind / connect して失敗したら、そのエラーを返し、次の経路でやり直さない
- 長いパスでは、カーネルが返すアドレス (`getsockname` / `getpeername`) は元のパスでなく bind の綴り。後で使えるかは `_ex` が返す綴りの性質 (`Spelling`) で分かる。標準の型のまま差し替えられる言語は元のパスを返す
- `_ex` の `remove()` は、自分が作ったソケットのファイルだけを消す (listener は閉じない)。B と D は sockat が片付けず、OS の一時ディレクトリの掃除に任せる (`sweep()` を呼べば死んだプロセスの D を消す)
- Windows は対象外

## ドキュメント

- [docs/SPEC-ja.md](./docs/SPEC-ja.md) — 言語によらない仕様 (公開する操作、resolve、綴りの性質、片付け、経路の試す順、使ってはいけない書き方、エラー、各実装に求めること)
- [docs/SPEC-routes-ja.md](./docs/SPEC-routes-ja.md) — 経路の作り方 (置き場 B の作り方、各経路の手順。実装者向け)
- [docs/decisions/](./docs/decisions/INDEX.md) — 仕様と構成の判断 (DR)
- [docs/decisions/DR-0017](./docs/decisions/DR-0017-resolve-through-persistent-base.md) — 長いパスの経路と API の判断と却下した案
- [docs/design/conformance.md](./docs/design/conformance.md) — 言語によらない適合試験 (各言語の試験用 CLI の入出力、場面の表)

## ライセンス

MIT License, Yoshiaki Kawazu (@kawaz)
