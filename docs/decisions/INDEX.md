# Decision Records 一覧

Status は各 DR ファイルの `Status:` 行が正本。ここに載るのは今立っている DR だけで、置き換えられた DR は [archive/INDEX.md](archive/INDEX.md) にある。

状態は絵文字とラベルだけ。日付・Phase・裁定の内訳は各 DR 本文に書く。

- `💭 提案`: Decision がまだ裁定されていない。実装に着手しない (本文の `Status: Proposed`)
- `✅ 実装済`: Decision の全部に実装エビデンスがある
- ハブにはコードが無いので、実装エビデンスは各言語のリポ (sockat-rs・sockat-py・sockat-go・sockat-ts) にある
- `🟡 部分実装`: 一部のみ実装
- `⬜ 未実装`: 裁定済みで設計のみ、実装エビデンスなし (着手してよい)
- `🚧 進行中`: 実装の途中
- `N/A`: 実装対象でない (命名・思想・プロセス等)
- `❌ 撤退`: 撤退判断済

| DR | 状態 | 説明 |
|---|---|---|
| [DR-0001](DR-0001-hub-and-per-language-repos.md) | N/A | 言語ごとに別リポ (`kawaz/sockat-<言語>`)、ハブ `kawaz/sockat` に言語によらない仕様の正本、Rust 版は sockat-rs (crate 名は `sockat` のまま) |
| [DR-0003](DR-0003-single-connect-when-standard-never-blocks.md) | ✅ 実装済 | 標準の connect が元から待たない言語 (Go 等) は connect を 1 つだけ出し、`_nonblocking` を分けない |
| [DR-0004](DR-0004-standard-length-per-language.md) | ✅ 実装済 | 標準に渡す長さはその言語の標準が受け付ける長さ。経路の綴りの条件は sockaddr に入る長さ (`sun_path` − 1) |
| [DR-0006](DR-0006-nul-is-invalid-at-any-length.md) | ✅ 実装済 | 先頭以外に NUL を含むパスは長さによらず引数の誤り。先頭が NUL (abstract) は対象外 |
| [DR-0017](DR-0017-resolve-through-persistent-base.md) | ✅ 実装済 | 長いパスを、置き場 B (利用者ごと)・D (プロセスごと)・E (resolve ごと) の消さない symlink を通る短い綴りに resolve して bind / connect する。既定の bind も綴りを残す。収まらなければ thread-cwd / at。fork と最終手段は無く、bind の綴りの性質は `Spelling` |
| [DR-0018](DR-0018-cli-resolve-with-reused-hashed-link.md) | 🟡 部分実装 | 短い綴りを作る CLI `sockat` を Rust で作る。既定の `resolve` はソケットのディレクトリを指すハッシュの名前の E を B の直下で使い回す (D を作らず、片付け不要)。手法の名指しは CLI の進んだオプションだけに置き、ライブラリには足さない |
| [DR-0019](DR-0019-absolutize-relative-path-on-bind.md) | ✅ 実装済 | bind と resolve は、相対パスを絶対パスにしてから扱う (実パスと `$PWD` からの綴りの候補が収まればそれを標準に渡し、収まらなければ置き場を通す。長い絶対パスも先に実パスを試す)。届かない時だけ相対のまま標準に渡す。connect と送信の宛先は変えない。`resolve_for_connect` も綴りの性質を返す |
