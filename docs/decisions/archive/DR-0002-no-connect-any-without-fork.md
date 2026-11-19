# DR-0002: fork の経路を作れない言語は connect_any 系を出さない

- Status: Superseded by DR-0015
- Date: 2026-11-18

## Context

- `connect_any` 系は「他の経路が全部使えない時に fork してでも connect する」操作
- fork を安全に作れない言語・ランタイムがある (子の区間を async-signal-safe な呼び出しだけで書けない等)
- その言語で `connect_any` 系を出すか決める必要がある

## Decision

- fork の経路を作れない言語は `connect_any` / `connect_any_nonblocking` を出さない
- README の OS × 経路の表に「fork の経路なし」と書く

理由:

- 中身が `connect` と同じ関数を出すと、利用者は「fork でやり切る」と誤解する

## Alternatives Considered

- 案 A: 公開して、fork の経路に来たら `connect` と同じエラー (`ENAMETOOLONG`) を返す
  - 不採用理由: 名前が約束する「fork してでも届く」を守らない関数になる

## Consequences

- 言語によって公開する操作の数が違う。違いは README の表で示す

## 関連

- [docs/SPEC-ja.md](../../SPEC-ja.md) の「公開する操作」
