---
title: "仕様を、実際に使われている物に絞って整理し直す"
status: open
category: design
created: 2026-11-24
origin: "kawaz との議論"
---

# 仕様を、実際に使われている物に絞って整理し直す

## 概要

- SPEC と SPEC-routes は合わせて 809 行あり、4 言語がそれぞれ全部を実装している。外部のレビューが見つけた優先度の高い指摘は、どれも言語の間のずれだった
- kawaz (2026-11-24): 実際にコアで使っていない仕様は、削って整理し直してよい
- 利用者は kawaz のプロダクトだけなので、互換は気にしない
- 方針はまだ決まっていない。下は、決めるための材料と候補

## 利用者が使っている物 (2026-11-24 に調べた)

調べ方: kawaz のリポ (各リポの main の workspace) の依存の宣言とコードを `sockat` で grep した。

| | llm-gateway | hyoui |
|---|---|---|
| 言語と版 | Rust、sockat 0.5.1 | Rust、sockat 0.5.1 |
| OS | Linux、macOS | Linux、macOS |
| 呼ぶ関数 | `bind`、`connect`、`connect_nonblocking` | `bind`、`connect`、`connect_nonblocking`、試験の後片付けに `sweep` |
| 渡すパス | 絶対パスだけ | 絶対パスだけ |
| 実運用のパスの長さ | 60〜66 バイト (上限に当たらない) | 55〜82 バイト (上限に当たらない) |
| 長いパスに当たる場面 | 試験 (`$TMPDIR` が深い)、利用者が長い置き場を設定した時 | 試験、状態の置き場を深い所に向けた時、`--socket` の指定 |

- 利用者はこの 2 つだけ。Python・Go・TypeScript の実装と、CLI `sockat` を使っている所は無い
- `_ex`、resolve、DGRAM、`Options`、`Spelling`、`SocketFile`、`sweep_base` を呼んでいる所は 0 件
- 利用者が当てにしている性質: fork しない、close-on-exec で listen 済みの物が返る、errno がそのまま返る (`ECONNREFUSED`・`ENOENT`・`EAGAIN`・`EADDRINUSE`・`ENAMETOOLONG` で分岐している)、ブロックしない connect が待たない
- 利用者が要ると言った物 ([回答の記録](archive/2026-11-20-resolve-and-persistent-base.md)): 待たない connect、書き込みもスレッドも要らない connect の経路を先に試すこと、並行で競合しない置き場の作成、生きているプロセスの物を消さない掃除
- 利用者が使わないと言った物: `_ex`、`getsockname`、DGRAM と SEQPACKET、別の uid との通信、PrivateTmp、fork

## 量の目安

| 物 | 量 |
|---|---|
| sockat-rs の実装 (`src/`。試験を除く) | およそ 6700 行 |
| sockat-py・sockat-go・sockat-ts の実装 | 4094・4907・3802 行 |
| 各言語の試験 | rs 6700、py 5569、go 10927、ts 3390 行 |
| CI の VM の job (FreeBSD・NetBSD・OpenBSD・illumos) | 3 言語 × 4 OS = 12 本。1 巡でおよそ 29 分 |

sockat-rs の中で、利用者が呼ばない物の行数の目安: resolve 387、`remove`・`cleanup`・`socket_file` 243、`Options.base` 110、DGRAM 104、`sweep_base` を含む掃除 174、相対パスを絶対にする処理 200、FreeBSD の経路 35、CLI 用の入口 400。

## 削る候補

利用者が使っていない順に並べる。それぞれ、削ると失う物を書く。

| 候補 | 削ると失う物 |
|---|---|
| DGRAM の `send_to` | 無し (どの言語にも実装が無い) |
| DGRAM の専用の関数 | DGRAM を関数 1 つで使える手軽さ (resolve が残れば、綴りを標準ライブラリに渡して使える) |
| `Options.usable_cross_uid` と、それに伴う置き場の選び分け | 別の uid の相手に辿らせる綴りを選ぶこと |
| `Options.base`・`sweep_base` | アプリが置き場を指定すること (CLI の `--base` はこれを使う) |
| `_ex`・診断 (`route`・`base`・`skipped`)・`Spelling` | どの経路で通ったかの観察 (適合試験と届く範囲の実測はこれで比べている)、綴りを後で使えるかで分岐すること |
| `SocketFile` の `remove`・`cleanup`・`socket_file` | 置き換えられたファイルを消さない削除 (利用者は 2 つとも、自分の持つ元のパスで消している) |
| resolve | 綴りを自分で標準ライブラリに渡すこと (SEQPACKET、CLI の土台) |
| 相対パスを絶対にする決まり (DR-0019) | 相対パスで bind した時に、カーネルの覚える綴りが相対のまま残ることの是正 |
| FreeBSD・NetBSD・OpenBSD・illumos・Android・iOS | その OS で動くこと。FreeBSD だけの経路 (`at`・`at-direct`) と、CI の VM の job 12 本が無くなる |
| Python・Go・TypeScript の実装 | その言語から使えること。4 言語の間のずれという問題そのものが無くなる |
| CLI | sockat を組み込めないプログラムに、収まるパスを渡す手段 |

## 置き場の作りの候補

削る話とは別に、置き場の作りそのものを単純にする候補がある (kawaz 2026-11-24)。

| | 今の形 | 候補 |
|---|---|---|
| 作り | 利用者ごとの置き場の下に、プロセスごとのディレクトリを作り、ロック (flock) を持ち続ける。死んだ物は `sweep` が消す | 利用者ごとの置き場の直下に、指す先のハッシュを名前にした symlink を置いて使い回す (CLI の今の形)。誰も消さない・張り替えない |
| 綴りの寿命 | 作ったプロセスが生きている間 | プロセスによらない |
| OS の掃除 | ロックされたディレクトリは Linux の systemd-tmpfiles が飛ばす。何も呼ばなくてよい | 守る物が無い。長く動く利用者は、symlink の時刻を新しくする関数を自分で呼ぶ (例: 4 時間に 1 回)。黙って新しくはしない |
| 仕組み | ロック、fd の持ち続け、`sweep`、作り直し | 時刻を新しくする関数 1 つ |
| 残る物 | プロセスが死ぬたびにディレクトリが残り、掃除を待つ | ディレクトリの数だけの symlink |

- 候補の弱い所: 呼ばなければ守られない。「置き換えるだけで動く」で入った利用者は、その関数を知らない。Linux で、古さで掃除されない置き場 (`$XDG_RUNTIME_DIR`) を先に選ぶ形にできるかを、DR-0017 の置き場の順の理由と突き合わせる必要がある
- 枝: ハッシュに自分のバイナリのパスを混ぜて、アプリごとに別の symlink にするか。バイナリのパスは、インタプリタで動く言語・版ごとにパスが変わる配り方・実行のたびにパスが変わる試験で、身元として弱い。「誰も消さない・張り替えない」を約束にすれば、分けなくても害が無い

## kawaz の考え (2026-11-25。決定ではなく、議論の中で述べられた向き)

- 利用者に選ばせるのは「何がしたいか」: 別の uid から辿れる必要があるか、速さ重視か、bind か connect か、置き場を指定するか、指定しないなら PrivateTmp を気にするか、等。手法は選ばせない (内部の粒度の話)
- したい事は先に受け取る。sockat が先に綴りを決めて、使えるかは結果 (`Spelling`) を見て確かめさせる今の作りは、向きが逆 (「result の方を作ったあたりからずっと逆だと思っていた」)
- 個別の条件の指定とは別に、よくある使い方のための、名前の付いた条件の組を選べるようにする
- 標準ライブラリと同じ形の `bind`・`connect` は導入。細かくやりたい人は resolve を使うのが基本
- `_ex` は無い方がすっきりする (resolve と同じ物を返しているだけ)
- 長く動く利用者のために、bind で使っている symlink の時刻を新しくする関数を、明示で呼ぶ形で用意する (例: 4 時間に 1 回)。黙ってする副作用や、用途と違う使い方 (時々 `sockat` を呼び直す等) を勧めるのは採らない
- Linux の置き場は、古さで掃除されない `$XDG_RUNTIME_DIR` を先にする形でよい
- 語: 「手法」は個々の技。「ルート」(最初は「ストラテジー」「戦略」と呼んでいた) は、手法を好きな順に並べた物、ルートの選び方のチャート、結果の単数の `route` (1 つの手法から作られたパス)。今の文書は 2 つを混ぜている
- 「手法の名指しは CLI だけ」(DR-0018) は kawaz の言葉で、上の「したい事を選ばせる」とは別の話

統括が確かめた事 (`_ex` と resolve の違い): `_ex` にしか無いのは、綴りを作れない手法の診断 (適合試験・届く範囲の実測・CLI の `bind`・`connect` が使う)、bind した瞬間にファイルの番号を覚える `remove()`、`Options` を渡せる bind・connect の 3 つ。利用者が使っているのは無い。`connect_nonblocking` は利用者が 2 つとも使っていて、代わりが無い (Rust と Python で要る)。

## API の形で気になっている所

- `ForBind` の `socket_file()` は、bind した後に呼ぶ決まりで、順番を型が守っていない
- `remove()` と `cleanup()` の 2 つの動詞があり、同じ物を片付ける口が複数の型にある
- `Bound` が、診断の値と片付けの権利を同じ型に載せている

## 受け入れ条件

- [ ] 3 つのモデルに出したレビューと書き直し ([別の issue](2026-11-25-model-reviews-and-rebuilds.md)) を読み、どれを採るか・どれも採らずにどう直すかを決める
- [ ] 何を残し何を削るかを決める (kawaz の裁定)
- [ ] 置き場の作りを、今の形のままにするか候補にするかを決める (kawaz の裁定)
- [ ] 決まった形で SPEC と SPEC-routes を書き直し、DR に残す
- [ ] 適合試験、届く範囲の表、各言語の実装と文書を合わせる

## 関連

- [DR-0017](../decisions/DR-0017-resolve-through-persistent-base.md)、[DR-0018](../decisions/DR-0018-cli-resolve-with-reused-hashed-link.md)、[DR-0019](../decisions/DR-0019-absolutize-relative-path-on-bind.md)
- [OS の掃除と symlink の実測](../findings/2026-11-24-tmpfiles-and-symlink-in-use.md)
- [利用者の 0.5.1 の実測](../findings/2026-11-21-consumer-measurements-0-5.md)
