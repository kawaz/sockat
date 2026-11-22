# DR-0003: 標準ライブラリの connect が元から待たない言語は connect を 1 つだけ出す

- Status: Active
- Date: 2026-11-18

## Context

- Rust 版は `connect` (ブロックする) と `connect_nonblocking` を分けて出す
- Node.js 等は標準ライブラリの connect が元から待たない (コールバック・Promise で結果を返す)
- Go の標準ライブラリの `net.DialUnix` も元から待たない (backlog が満杯なら Linux は即 `EAGAIN`、macOS は `ECONNREFUSED`。[sockat-go の DR-0001](https://github.com/kawaz/sockat-go/blob/main/docs/decisions/DR-0001-public-api.md) で実測)
- その言語でも 2 つに分けるか決める必要がある

## Decision

- 標準ライブラリの connect が元から待たない言語は、標準ライブラリと同じ形の connect を 1 つだけ出し、`_nonblocking` を分けない
- `connect_ex` 系も同じく 1 つ

理由:

- 標準ライブラリと同じ形で置き換えて使えることが sockat の約束

## Alternatives Considered

- 案 A: Rust と同じく 2 つを揃える
  - 不採用理由: 標準ライブラリに無いブロックする connect を足すことになり、標準ライブラリと同じ形でなくなる

## Consequences

- 言語によって公開する connect の数が違う。名前と形はその言語の標準ライブラリに合わせる
- Go は `Dial` と `DialEx` を 1 つずつ出す

## 関連

- [docs/SPEC-ja.md](../SPEC-ja.md) の「公開する操作」
