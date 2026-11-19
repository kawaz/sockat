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

- 戻り値は、その言語の標準の bind / connect が返すのと同じソケットの型
- 長いパスでも、ソケットファイルは渡したパスにできる
- 長いパスは、sockat 専用のディレクトリを作って fd で掴み、その中に置いた乱数の名前の symlink を通す短い綴りで bind / connect し、終わったら片付ける
- そのディレクトリの fd を基準にする手段は、OS ごとに決まった順に試す (スレッド cwd、bindat / connectat、/proc、fork)。connect は、書き込みもスレッドも要らない経路 (/proc、相対パス、広げた sockaddr) を先に試す
- どの経路も呼び出し元のプロセスとスレッドの cwd を変えない
- `connect` は fork しない。fork するのは `bind` と、最終手段を使う `connect_ex` 系だけで、他の手段が使えない時の最後の手
- 経路が実際に bind / connect して失敗したら、そのエラーを返し、次の経路でやり直さない
- カーネルが返すアドレス (`getsockname` / `getpeername`) は元のパスでない (普段は後で解決しても何にも当たらない綴り。消す時は元のパスで消す)。標準の型のまま差し替えられる言語は元のパスを返し、それ以外は元のパスを呼び出し元が持つ
- 後始末つきの bind (`bind_ex` 等) の `discard()` は、自分が作ったソケットのファイルだけを消す (listener は閉じない)
- Windows は対象外

## ドキュメント

- [docs/SPEC-ja.md](./docs/SPEC-ja.md) — 言語によらない仕様 (経路、試す順番、安全条件、エラー、各実装に求めること)
- [docs/decisions/](./docs/decisions/INDEX.md) — このリポの構成の判断 (DR)
- [docs/decisions/DR-0012](./docs/decisions/DR-0012-own-directory-and-thread-cwd.md) — 長いパスの経路の判断と却下した案

## ライセンス

MIT License, Yoshiaki Kawazu (@kawaz)
