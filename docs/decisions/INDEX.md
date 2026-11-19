# Decision Records 一覧

Status は各 DR ファイルの `Status:` 行が正本。ここに載るのは今立っている DR だけで、置き換えられた DR は [archive/INDEX.md](archive/INDEX.md) にある。

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
| [DR-0006](DR-0006-nul-is-invalid-at-any-length.md) | ⬜ 未実装 | 先頭以外に NUL を含むパスは長さによらず引数の誤り。先頭が NUL (abstract) は対象外 |
| [DR-0010](DR-0010-fork-bind-listen-by-parent.md) | ⬜ 未実装 | fork の経路の bind は listen を必ず親がする。相手から見える副作用は無く、見えない副作用 (`SIGCHLD` 等) はある |
| [DR-0012](DR-0012-own-directory-and-thread-cwd.md) | 🚧 進行中 | 長いパスは自分専用のディレクトリ D を fd で掴み、その中の乱数の symlink R を通して `R/<ファイル名>` で bind / connect する (スレッド cwd → /proc 版 → fork)。connect は予備に今の経路。bind は /proc・相対パス・広げた sockaddr・置き場の symlink を使わない |
| [DR-0013](DR-0013-any-means-reach-at-any-cost.md) | 🚧 進行中 | any 系は「何かを失ってでも届かせる」opt-in の API (Rust は feature `any`)。`bind_any` は最後に置き場の symlink (持ち主だけが書ける置き場 → 共有の置き場)、`connect_any` 系は最後に fork。失ったものの名前の並び (`losses`) と、診断用の通った経路と飛ばした経路 (理由つき、失敗時も) を返す |
| [DR-0014](DR-0014-discard-removes-only.md) | 🚧 進行中 | 後始末つきの bind の `discard` はファイルを消すだけで、listener を閉じない |
