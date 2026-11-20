# DR-0010: fork の経路の bind は listen を必ず親がする

- Status: Superseded by DR-0017
- Date: 2026-11-18

## Context

- fork の経路の bind に、相手 (connect するクライアント) から見える副作用があるかを確かめる必要がある (DR-0012 で bind の最後の手に fork を置く前提)
- 実測 (2026-11-18、macOS 26.5.2 と Linux の docker)。peer 情報は macOS が `LOCAL_PEERPID` / `LOCAL_PEEREPID` / audit token の pid と pidversion (kawaz の procline で収集)、Linux が `SO_PEERCRED` / `SO_PEERPIDFD`

| 手順 | クライアントに見えるサーバの peer |
|---|---|
| 子は `fchdir` + bind + `_exit`、listen は親 (sockat と同じ) | send の前から親 |
| 子に listen までさせる (対照) | 死んだ子。macOS は send の前だけ、Linux はずっと |

## Decision

- fork の経路の bind の後の listen は、必ず呼び出し元 (親) がする
- 副作用は範囲つきで書く

| 範囲 | 副作用 |
|---|---|
| 相手から見える | 無い |
| 相手から見えない | 親に `SIGCHLD`<br>`pthread_atfork` の handler が走る<br>監視ツールに短命の子が見える<br>他のスレッドの `waitpid(-1)` が子を刈り取りうる<br>子が終了まで全 fd の複製を持つ |

理由:

- listen した側が peer 情報の持ち主になる。子に listen させると、クライアントは死んだプロセスを相手と見る

## Alternatives Considered

- 案 A: 子が listen までする
  - 不採用理由: クライアントに見える peer が死んだ子になる

## Consequences

- 試験: fork の経路で bind したサーバに connect したクライアントから見える peer が親 (send の前も後も)

## 関連

- [docs/SPEC-ja.md](../../SPEC-ja.md) の「fork の子」「fork の副作用」「実装が確かめる試験の観点」
- 裁定: kawaz (2026-11-18)
- [DR-0012](DR-0012-own-directory-and-thread-cwd.md)
