# DR-0007: connect_any 系は既定の API に出さず、使う人が選んで有効にする

- Status: Active
- Date: 2026-11-18

## Context

- スレッド cwd の経路 (DR-0005) で、`connect` 系が届かない場面はほぼ無くなった。`connect_any` 系が要るのは、fork が最後の手になる環境 (NetBSD / OpenBSD / illumos、`unshare` が断られる Linux、`pthread_fchdir_np` が無い Apple の OS) だけ
- 既定の API に `connect` と並んで出ていると、エディタの補完などで利用者がどちらを使うか迷う

## Decision

- `connect_any` 系は残すが、既定の API に出さない
- 使う人が自分で選んで有効にする、その言語の仕組みの後ろに置く

| 言語 | 置き場 |
|---|---|
| Rust | feature `connect-any` (docs.rs では全 feature を有効にし、feature が要ることを表示する) |
| Python 等 | 既定で import されない別のモジュール等。各言語の DR で決める |
| fork を作れない言語 | 出さない (DR-0002) |

理由:

- 有効にする手間が「fork の副作用を受け入れる」という意思表示になる
- ほぼ使わない関数で、普段の補完と doc の入口を散らかさない

## Alternatives Considered

- 案 A: 既定の API にそのまま残す
  - 不採用理由: 補完で `connect` と並び、利用者を迷わせる
- 案 B: 消す
  - 不採用理由: fork が最後の手になる環境で、fork を受け入れてでもつなぎたい人の逃げ道が無くなる

## Consequences

- Rust 版は API を壊す (今 `connect_any` を使うコードは feature が要る) ので 0.3.0 にする

## 関連

- 裁定: kawaz (2026-11-18)
- [DR-0002](DR-0002-no-connect-any-without-fork.md)、[DR-0005](DR-0005-thread-cwd-route.md)
