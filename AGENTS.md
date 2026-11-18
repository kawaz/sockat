# AGENTS.md — sockat (ハブ) の作業ルール

sockat は、`sun_path` の上限を超えるパスでも Unix domain socket を bind / connect できるライブラリ。このリポは言語によらない仕様の正本と、言語ごとの実装 (`kawaz/sockat-<言語>`) への入口。コードは置かない。

## 必読

- [docs/SPEC-ja.md](docs/SPEC-ja.md) — 言語によらない仕様の正本
- [docs/decisions/DR-0001](docs/decisions/DR-0001-hub-and-per-language-repos.md) — リポの分け方と、仕様をここに置く理由
- [docs/decisions/DR-0012](docs/decisions/DR-0012-own-directory-and-thread-cwd.md) — 長いパスの経路の判断と却下した案

## 構成

| パス | 中身 |
|---|---|
| `README-ja.md` / `README.md` | 何を解決するか、言語ごとの実装の表 |
| `docs/SPEC-ja.md` / `docs/SPEC.md` | 言語によらない仕様 |
| `docs/decisions/` | このリポの構成の判断 (DR) |
| `docs/research/` | 他言語への移植等の調査 |

## 守ること

- **仕様の正本はここ。** 各言語の実装の振る舞いを変える前に、先に SPEC を直す
- SPEC には言語によらないことだけを書く。言語固有の話 (型、ランタイム連携、メモリ安全の扱い) は各言語のリポに置き、リンクで済ませる
- SPEC の主張は sockat-rs の実装・DR と食い違わせない。食い違いに気づいたら、どちらを直すかを決めてから直す
- 言語版を公開したら README の実装の表を直す (日本語版と英語版の両方)

## VCS と push

- jj colocate。commit は `jj commit -m "..." <files...>` でパスを指定する
- push は `just push` だけ (翻訳ペアの鮮度を検査してから push する)
- README と docs/SPEC は日本語版 (`*-ja.md`) が正本。英語版は日本語版を直した同じ変更で直し、見出しの数と順を揃える
