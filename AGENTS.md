# AGENTS.md — sockat (ハブ) の作業ルール

sockat は、`sun_path` の上限を超えるパスでも Unix domain socket を bind / connect できるライブラリ。このリポは言語によらない仕様の正本と、言語ごとの実装 (`kawaz/sockat-<言語>`) への入口。ライブラリのコードは置かない。言語によらない適合試験 (`conformance/` の表と、それを各言語の試験用 CLI に流して突き合わせるスクリプト) は置く ([docs/design/conformance.md](docs/design/conformance.md))。

## 必読

- [docs/SPEC-ja.md](docs/SPEC-ja.md) — 言語によらない仕様の正本
- [docs/decisions/DR-0001](docs/decisions/DR-0001-hub-and-per-language-repos.md) — リポの分け方と、仕様をここに置く理由
- [docs/decisions/DR-0017](docs/decisions/DR-0017-resolve-through-persistent-base.md) — 長いパスの経路と公開 API の形 (resolve、置き場 B・D・E、`_ex` と `Options`、`Spelling`、`route`・`skipped`) の判断と却下した案

## 構成

| パス | 中身 |
|---|---|
| `README-ja.md` / `README.md` | 何を解決するか (各言語の標準が出すエラーと、その言語のリポへのリンクの表)、置き換えの例を 1 言語だけ。インストール方法と各言語の例は各言語のリポに置く |
| `docs/SPEC-ja.md` / `docs/SPEC.md` | 言語によらない仕様 (利用者と各言語の README を書く人への約束) |
| `docs/SPEC-routes-ja.md` / `docs/SPEC-routes.md` | 経路の作り方 (各言語の実装者向け。B の作り方、各経路の手順) |
| `docs/decisions/` | 仕様と構成の判断 (DR) |
| `docs/research/` | 決める前に外の事実を集めた調査 (他言語の標準、需要、先行例)。判断の材料 |
| `docs/findings/` | 実機で確かめた結果 (環境・手順・出力つき)。SPEC・DR の主張の根拠 |
| `docs/issue/` | 未着手・検討中の課題 (local-issue の形式、`INDEX.md` は生成物) |
| `docs/QUESTIONS.md` | kawaz の裁定を待つ問い (統括が書く) |
| `docs/design/conformance.md` | 適合試験の決まり (各言語の試験用 CLI の入出力、表の書き方) |
| `docs/design/cli.md` | 短い綴りを作る CLI `sockat` の決まり (呼び方、オプション、出力、終了コード。実装は sockat-rs) |
| `conformance/` | 適合試験の表と、それを流して突き合わせるスクリプト |
| `tools/` | 利用の統計の取得 (`just stats`) |
| `pages/` | 利用者向けに公開するサイトの元 (利用マニュアル `manual`、リファレンス `reference`、技術説明 `technical`、届く範囲の表 `reach/`、fork-cwd の手法、Q&A `faq`、言語ごとの注意 `langs`)。md は全部日本語 `<name>-ja.md` と英語 `<name>.md` の対 (`just push` が対の欠けを止める)。開発用の文書は docs/ |

## 守ること

- **仕様の正本はここ。** 各言語の実装の振る舞いを変える前に、先に SPEC を直す
- SPEC には言語によらないことだけを書く。言語固有の話 (型、ランタイム連携、メモリ安全の扱い) は各言語のリポに置き、リンクで済ませる
- 各言語のリポの README / マニュアルには言語によらない説明を写さず、ハブの SPEC・pages へリンクする。言語固有の注意は各リポに書き、ハブの `pages/langs-ja.md` に 1 行で載せる。README の冒頭 (その言語の標準が出すエラー、その言語での書き換え前後、インストール方法) だけは、リンクで済ませずその言語の例で書く
- 利用者向けの文書は入口から順に深くする: README (困っている人に、置き換えるだけで解決すると伝える。技術の詳細を置かない) → 利用マニュアル `pages/manual` (他にできること。置き場 B・D・E 等の仕様の語彙を使わない) → 技術説明 `pages/technical` (手法の比較と選び方)。README の末尾の案内は「利用マニュアル」「リファレンス」「技術説明」の 3 つの名前だけにする。ハブの利用マニュアルとリファレンス (`pages/reference`) は、各言語のマニュアル・リファレンスへの入口にする (利用マニュアルは「使い方」を教える所で、「できること」の紹介を書かない。kawaz 2026-11-22)。各言語の文書のパスと中身の分け方は SPEC の「各実装に求めること」。各言語のリポの README も同じ 3 つを置き、利用マニュアルとリファレンスはその言語の物へ、技術説明はハブの `pages/technical` へ張る (kawaz 2026-11-22)。README と `pages/manual` は「使う前に知っておくこと」「注意」の枠で書かない (それがあるだけで使いたくなくなる。kawaz 2026-11-22)。できることと、気にしなくてよい理由で書き、まれな場合の注意は仕様と各言語のマニュアルに置く。方針と残りの作業は [issue](docs/issue/2026-11-22-user-docs-in-three-layers.md)
- illumos は CI で確かめ続けるが、利用者向けの文書 (README、`pages/manual`) では触れない。届く範囲の表・SPEC・言語ごとの注意に載せるだけにする (kawaz 2026-11-22)
- SPEC の主張は各言語の実装 (sockat-rs・sockat-py・sockat-go・sockat-ts) とその DR と食い違わせない。食い違いに気づいたら、どちらを直すかを決めてから直す
- パッチ版の公開は各言語のセッションに任せる。CI (BSD・illumos を含む) とハブの適合試験 (全言語) を通した上で bump・push・release し、結果をハブに知らせる。破壊的な変更を含む版 (0.x の minor を上げる物) は kawaz に聞く (kawaz 2026-11-21、PB-Q2 = a)
- 言語を足したら README の表に 1 行足す (日本語版と英語版の両方)。版の番号は README に書かない

## VCS と push

- jj colocate。commit は `jj commit -m "..." <files...>` でパスを指定する
- push は `just push` だけ (翻訳ペアの鮮度を検査してから push する)
- README と docs/SPEC は日本語版 (`*-ja.md`) が正本。英語版は日本語版を直した同じ変更で直し、見出しの数と順を揃える
