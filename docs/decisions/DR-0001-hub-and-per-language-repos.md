# DR-0001: 言語ごとに別リポ、ハブに言語によらない仕様の正本を置く

- Status: Active
- Date: 2026-11-18

## Context

- sockat は Rust の crate として作り、仕様 (経路、試す順番、安全条件、エラー) は Rust のリポの DR-0001 と MANUAL に書いてあった
- 同じ問題は Python・Go・JavaScript / TypeScript・Ruby 等にもあり、他言語版を作る ([調査](../research/2026-11-18-ports-to-other-languages.md))
- 言語が増えると、リポの分け方と、言語によらない仕様をどこに置くかを決める必要がある

## Decision

| 項目 | 決定 |
|---|---|
| 実装のリポ | 言語ごとに別のリポ `kawaz/sockat-<言語>` (sockat-rs、sockat-py、sockat-go、sockat-ts、sockat-rb 等) |
| ハブ | `kawaz/sockat` に言語によらない仕様の正本 ([SPEC-ja.md](../SPEC-ja.md)) と、各実装への入口を置く |
| Rust 版 | リポを `kawaz/sockat-rs` にリネーム。crates.io の crate 名は `sockat` のまま |
| 言語固有の文書 | 各リポに置く (型、ランタイム連携、メモリ安全の扱い等) |

理由:

- 言語ごとにビルド・CI・release の手順・publish 先 (crates.io、PyPI、npm、RubyGems、Go の module proxy) が違い、1 つのリポでは手順と tag が混ざる
- Go の module path はリポの path そのもの (`github.com/kawaz/sockat-go`) にするのが慣習。サブディレクトリの module は tag に path の接頭辞が要る
- 仕様の正本を 1 か所にし、どの言語のリポからも同じ所を参照させる。特定の言語のリポに置くと、その言語の都合 (標準ライブラリの型、`unsafe` 等) と混ざる
- crate 名を変えると利用者の依存の書き換えが要るので、名前は変えない

## Alternatives Considered

- 案 A: 1 つのリポに全言語の実装を置く (monorepo)
  - 不採用理由: 言語ごとのビルド・CI・release・publish が 1 つのリポに混ざる。Go の module に path 接頭辞付きの tag が要る。言語ごとに版を独立に上げにくい
- 案 B: 仕様を Rust のリポ (sockat-rs) に置いたままにする
  - 不採用理由: 他言語の実装が Rust のリポを仕様の正本として参照することになり、Rust 固有の話と言語によらない仕様が分けられない。仕様の変更が Rust の release の流れに縛られる

## Consequences

- 仕様を変える時は、先にハブの SPEC を直し、各言語のリポに追従させる。追従は各リポの作業
- 各言語のリポの README は SPEC へリンクし、作れない経路を OS × 経路の表で示す
- 言語版を公開したら、ハブの README の実装の表を更新する
- crates.io の `sockat` 0.2.5 までの repository は `kawaz/sockat` (このハブ) を指す。ハブの README から sockat-rs へ辿れるようにしておく

## 関連

- [docs/SPEC-ja.md](../SPEC-ja.md)
- [sockat-rs の DR-0001](https://github.com/kawaz/sockat-rs/blob/main/docs/decisions/archive/DR-0001-long-socket-path-routes.md)
- [docs/research/2026-11-18-ports-to-other-languages.md](../research/2026-11-18-ports-to-other-languages.md)
