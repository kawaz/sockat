# AGENTS.md — sockat (ハブ) の作業ルール

sockat は、`sun_path` の上限を超えるパスでも Unix domain socket を bind / connect できるライブラリ。このリポは言語によらない仕様の正本と、言語ごとの実装 (`kawaz/sockat-<言語>`) への入口。ライブラリのコードは置かない。言語によらない適合試験 (`conformance/` の表と、それを各言語の試験用 CLI に流して突き合わせるスクリプト) は置く ([docs/design/conformance.md](docs/design/conformance.md))。

## 必読

- [docs/SPEC-ja.md](docs/SPEC-ja.md) — 言語によらない仕様の正本
- [docs/decisions/DR-0001](docs/decisions/DR-0001-hub-and-per-language-repos.md) — リポの分け方と、仕様をここに置く理由
- [docs/decisions/DR-0017](docs/decisions/DR-0017-resolve-through-persistent-base.md) — 長いパスの経路と公開 API の形 (resolve、置き場 B・D・E、`_ex` と `Options`、`Spelling`、`route`・`skipped`) の判断と却下した案

## 構成

| パス | 中身 |
|---|---|
| `README-ja.md` / `README.md` | 何を解決するか、言語ごとの実装の表 |
| `docs/SPEC-ja.md` / `docs/SPEC.md` | 言語によらない仕様 (利用者と各言語の README を書く人への約束) |
| `docs/SPEC-routes-ja.md` / `docs/SPEC-routes.md` | 経路の作り方 (各言語の実装者向け。B の作り方、各経路の手順) |
| `docs/decisions/` | 仕様と構成の判断 (DR) |
| `docs/research/` | 決める前に外の事実を集めた調査 (他言語の標準、需要、先行例)。判断の材料 |
| `docs/findings/` | 実機で確かめた結果 (環境・手順・出力つき)。SPEC・DR の主張の根拠 |
| `docs/issue/` | 未着手・検討中の課題 (local-issue の形式、`INDEX.md` は生成物) |
| `docs/QUESTIONS.md` | kawaz の裁定を待つ問い (統括が書く) |
| `docs/design/conformance.md` | 適合試験の決まり (各言語の試験用 CLI の入出力、表の書き方) |
| `conformance/` | 適合試験の表と、それを流して突き合わせるスクリプト |
| `pages/` | 利用者向けに公開するサイトの元 (届く範囲の表 `reach/`、fork-cwd の手法、Q&A `faq`)。md は全部日本語 `<name>-ja.md` と英語 `<name>.md` の対 (`just push` が対の欠けを止める)。開発用の文書は docs/ |

## 守ること

- **仕様の正本はここ。** 各言語の実装の振る舞いを変える前に、先に SPEC を直す
- SPEC には言語によらないことだけを書く。言語固有の話 (型、ランタイム連携、メモリ安全の扱い) は各言語のリポに置き、リンクで済ませる
- SPEC の主張は各言語の実装 (sockat-rs・sockat-py・sockat-go) とその DR と食い違わせない。食い違いに気づいたら、どちらを直すかを決めてから直す
- 言語版を公開したら README の実装の表を直す (日本語版と英語版の両方)

## VCS と push

- jj colocate。commit は `jj commit -m "..." <files...>` でパスを指定する
- push は `just push` だけ (翻訳ペアの鮮度を検査してから push する)
- README と docs/SPEC は日本語版 (`*-ja.md`) が正本。英語版は日本語版を直した同じ変更で直し、見出しの数と順を揃える
