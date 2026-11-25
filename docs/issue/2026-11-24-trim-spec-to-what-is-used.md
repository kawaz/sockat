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

- 利用者に選ばせるのは「何がしたいか」: 別の uid からの接続を受ける必要があるか、速さ重視か、bind か connect か、置き場を指定するか、指定しないなら PrivateTmp を気にするか、等。手法は選ばせない (内部の粒度の話)
- したい事は先に受け取る。sockat が先に綴りを決めて、使えるかは結果 (`Spelling`) を見て確かめさせる今の作りは、向きが逆 (「result の方を作ったあたりからずっと逆だと思っていた」)
- 個別の条件の指定とは別に、よくある使い方のための、名前の付いた条件の組を選べるようにする
- 標準ライブラリと同じ形の `bind`・`connect` は導入。細かくやりたい人は resolve を使うのが基本
- `_ex` は無い方がすっきりする (resolve と同じ物を返しているだけ)
- 長く動く利用者のために、bind で使っている symlink の時刻を新しくする関数を、明示で呼ぶ形で用意する (例: 4 時間に 1 回)。黙ってする副作用や、用途と違う使い方 (時々 `sockat` を呼び直す等) を勧めるのは採らない
- Linux の置き場は、古さで掃除されない `$XDG_RUNTIME_DIR` を先にする形でよい
- 語: 「手法」は個々の技。「ルート」(最初は「ストラテジー」「戦略」と呼んでいた) は、手法を好きな順に並べた物、ルートの選び方のチャート、結果の単数の `route` (1 つの手法から作られたパス)。今の文書は 2 つを混ぜている
- 「手法の名指しは CLI だけ」(DR-0018) は kawaz の言葉で、上の「したい事を選ばせる」とは別の話

### 相手がそのパスで繋げるかは、sockat の考える事ではない (kawaz 2026-11-25。決定ではなく、考え直した向き)

- sockat が考えるのは、自分がソケットをうまく開く事だけ。sockat が作るパスは、相手に伝える物ではない
- 相手には、内部のパスでなく素直なソケットのパスで「ここで待ち受けている」と伝えればよい。それが相手から見て長くて開きにくくても、どう解決するかは相手が考える事で、sockat を組み込むアプリの責務ではない (同じ cwd の client なら `./server.sock` に繋げば済む)
- 自分しかアクセスできない場所に内部のパスがあっても、相手から見て大抵は何の問題も無い
- なので、別の uid・PrivateTmp・`/proc` を「相手が辿れるか」のために考える必要は無い。例外は DGRAM だけ (返信を受けるなら、`getsockname` のパスが相手から見える必要がある)
- connect の symlink は、すぐに捨ててよい (`getsockname` で返信したり掃除したりする機会が無い)
- bind の symlink を残す必要があるかは、アプリの都合でしかない
  - 残す必要がある: `getsockname` のパスでの自動の掃除が組み込まれていて、騙せない言語 (Go)
  - 残す必要が無い: ソケットがオブジェクトで、`getsockname` を元の絶対パスに差し替えて上の層に使わせられる言語 (Python)

統括が確かめた事 (今の仕様のどこに当たるか):

- SPEC は connect 系について既に同じ事を言っている (「connect の綴りは相手に残らない」ので `usable_cross_uid` を見ない)
- SPEC が、bind の綴りが生きている事に頼る物として挙げるのは 3 つ: `getsockname` の綴りで消す上のライブラリ、DGRAM の返信、運用の道具 (`ss`・`lsof` に出るアドレス)
- 綴りの途中の symlink が消えると、その綴りでの unlink は `ENOENT` になり、ソケットのファイルが残る ([実測](../findings/2026-11-24-cli-base-fd-and-vanished-link.md))。閉じる時に綴りで unlink する標準ライブラリ (Go の `UnixListener.Close`) で symlink が要るのは、このため
- CLI と resolve も、アプリが自分で使うパスを作る道具で、作ったパスを相手に伝える物ではない (kawaz 2026-11-25)。サーバーもクライアントも、それぞれが元の長いパスを `sockat resolve` に渡し、返ったパスで自分が bind・connect する
- CLI に残るのは、相手の話ではなく寿命の話: パスを作った `sockat` のプロセスは先に終わるので、symlink は呼んだ側が使い終わるまで残っている必要があり、sockat の側からは捨てられない (DR-0018 の、使い回すハッシュの symlink と OS の掃除の警告はこのため)
- Node.js と Bun の close も、listen に渡したパスの文字列で unlink する。綴りの途中の symlink が消えていると、ソケットのファイルが残る ([実測](../findings/2026-11-25-node-bun-unlink-on-close.md))。標準ライブラリの listener をそのまま返すなら、TypeScript は Go と同じ側になる

`/proc` を使えるなら proc 一択でよい (kawaz 2026-11-25。同じく、考えの向き)。統括が確かめた事:

- connect は、Linux で `/proc` を使える時、既に標準ライブラリの次に `proc-direct` を試す
- bind を `/proc/self/fd/<ディレクトリの fd>/<ファイル名>` で直接通すのは、Linux で通る。fd を閉じた後も listener は接続を受け続ける ([実測](../findings/2026-11-25-bind-through-proc-self-fd.md))
- SPEC が bind に `proc-direct` を使わない理由 (綴りが後で無関係なファイルに当たる) は実際に起きる: fd を閉じた後の、bind した文字列での unlink は `ENOENT`。fd の番号が使い回されると、別のディレクトリの同じ名前のファイルが消える (同じ実測)。これが効くのは、カーネルの覚えたパスを後で使う物 (閉じる時に渡したパスで unlink する Go・Node.js・Bun、DGRAM の返信) だけ
- `getsockname`・`getpeername`・`/proc/net/unix`・`ss -xl` には `/proc/self/fd/3/s.sock` と出る
- 付けられるファイル名は、fd が 3 の時に 91 バイトまで (全体で 108 バイト)
- `/proc` が無い所 (macOS、`/proc` を mount していない環境) と、CLI (プロセスが先に終わる) では使えない

bind は `/proc/self/fd/<n>/<乱数の名前>/<ファイル名>` の形にする案 (kawaz 2026-11-25): n はソケットのディレクトリでなく、一時ディレクトリを作って開いた fd。その中に、ソケットのディレクトリを指す乱数の名前の symlink を作る。connect は `/proc/self/fd/<n>/<ファイル名>` のままでよい。統括が Linux のコンテナ (`python:3-slim`) で試した事:

- この形で bind・listen は通る
- fd を閉じて番号が別のディレクトリに使い回されても、bind した文字列での unlink は `ENOENT` で、別のディレクトリの同じ名前のファイルは消えない (乱数の名前がそこに無いため)
- symlink が中にあるまま、一時ディレクトリを rmdir する事はできない (`ENOTEMPTY`)。symlink を消してから rmdir すると、fd を開いたままでも bind した文字列は辿れなくなる (`ENOENT`)。消したディレクトリの中に、fd 越しに symlink を作り直す事もできない (`ENOENT`)
- つまり、bind した文字列を後で辿れる必要がある間 (閉じる時に渡したパスで unlink する Go・Node.js・Bun の listener が生きている間) は、一時ディレクトリと symlink をファイルシステムに残す必要がある。後で辿る物が無い Rust・Python は、bind の直後に両方を消せる

ゴミが残るのは嫌なので、乱数の名前は挟まず、`/proc/self/fd/<n>/<ファイル名>` で bind した後も n (ソケットのディレクトリの fd) を持ち続ければよい (kawaz 2026-11-25、上の案の取り下げ)。統括の評価:

- n を閉じなければ番号は使い回されないので、bind した文字列はプロセスが生きている間ずっと元のファイルを指す。閉じる時の unlink も通る (実測の「fd を開いたままの unlink」)。ファイルシステムには何も作らない
- 弱い所: sockat の外から n を閉じられると (起動時に 3 番以降の fd を全部閉じる類の処理)、番号の使い回しで別のファイルを消しうる状態に戻る。開いている間、そのディレクトリのあるファイルシステムを umount できない。fd は、bind したディレクトリの数だけ増える (同じディレクトリは 1 つを使い回せる)
- exec をまたぐと n は閉じる (close-on-exec)。引き継いだ listener の `getsockname` の文字列は、新しいプロセスでは辿れない

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
