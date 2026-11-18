# Decision Records 一覧

Status は各 DR ファイルの `Status:` 行が正本。

状態は絵文字とラベルだけ。日付・Phase・裁定の内訳は各 DR 本文に書く。

- `💭 提案`: Decision がまだ裁定されていない。実装に着手しない (本文の `Status: Proposed`)
- `✅ 実装済`: Decision の全部に実装エビデンスがある
- `🟡 部分実装`: 一部のみ実装
- `⬜ 未実装`: 裁定済みで設計のみ、実装エビデンスなし (着手してよい)
- `🚧 進行中`: 実装の途中
- `N/A`: 実装対象でない (命名・思想・プロセス等)
- `❌ 撤退`: 撤退判断済

| DR | 状態 | 説明 |
|---|---|---|
| [DR-0001](DR-0001-hub-and-per-language-repos.md) | N/A | 言語ごとに別リポ (`kawaz/sockat-<言語>`)、ハブ `kawaz/sockat` に言語によらない仕様の正本、Rust 版は sockat-rs (crate 名は `sockat` のまま) |
| [DR-0002](DR-0002-no-connect-any-without-fork.md) | ⬜ 未実装 | fork の経路を作れない言語は `connect_any` 系を出さない |
| [DR-0003](DR-0003-single-connect-when-standard-never-blocks.md) | ⬜ 未実装 | 標準の connect が元から待たない言語は connect を 1 つだけ出し、`_nonblocking` を分けない |
| [DR-0004](DR-0004-standard-length-per-language.md) | ⬜ 未実装 | 標準に渡す長さはその言語の標準が受け付ける長さ。経路の綴りの条件は sockaddr に入る長さ (`sun_path` − 1) |
| [DR-0005](DR-0005-thread-cwd-route.md) | ⬜ 未実装 | スレッドだけ cwd を移す経路を fork の手前に足す (Linux は `unshare(CLONE_FS)`、Apple の OS は `pthread_fchdir_np`)。`connect` 系も試す |
| [DR-0006](DR-0006-nul-is-invalid-at-any-length.md) | ⬜ 未実装 | NUL を含むパスは長さによらず引数の誤り |

経路の設計の判断は [sockat-rs の DR-0001](https://github.com/kawaz/sockat-rs/blob/main/docs/decisions/DR-0001-long-socket-path-routes.md) にある。
