# sockat の Q&A

> [English](./faq.md) | 日本語

sockat を使う前に出やすい問いと答え。仕様の正本は [SPEC](../docs/SPEC-ja.md)、届く場面の一覧は [届く範囲の表](reach/README-ja.md)。

答えは [DR-0017](../docs/decisions/DR-0017-resolve-through-persistent-base.md) の設計に対するもの。各言語の実装はこの設計へ作り直し中で、公開済みの版の振る舞いは各言語のリポの README にある。

## そもそも

### パスを短くすれば sockat は要らない?

要らない。ソケットのパスを自分で決められるなら、短い場所に置くのが一番良い。sockat が要るのは、パスを自分で選べない時:

- 置き場所を環境や設定が決めている (コンテナの実行環境の作業ディレクトリ、深い状態ディレクトリ等)
- 相手が決めたパスへ connect / 送信する (`NOTIFY_SOCKET` 等の環境変数で渡される)
- ライブラリで、使う側から渡されたパスをそのまま使う

### 長いパスで何が標準と違う?

カーネルが覚える綴り (`getsockname` や listener のアドレス) が元のパスでなく、置き場 B の中の D と symlink E を通る綴りになる。綴りが生きている間は元のパスと同じ所を指すが、綴りの種類によっては綴りで消してもファイルが残る・どこにも届かない。綴りを後で使えるかは `_ex` が返す `Spelling` で分かる。消すのは元のパスか `remove()` で行う ([SPEC の「使ってはいけない書き方」](../docs/SPEC-ja.md#使ってはいけない書き方))。

## 環境

### `$TMPDIR` が長い環境でも使える?

使える。B は `/tmp` に先に作る (`/tmp` → `$XDG_RUNTIME_DIR` → `$TMPDIR` → ソケットのディレクトリの順で最初に作れた所)。綴りは Linux なら `/proc/<pid>/fd/<fd>/…` (procB、置き場の長さによらない)、それ以外は B の実パス (`/tmp` の下なら短い) を使う。`$TMPDIR` を使うのは `/tmp` にも `$XDG_RUNTIME_DIR` にも作れない時だけ。

### PrivateTmp (systemd 等で `/tmp` が隔離された) の環境では?

Linux では procB の綴りが `/tmp` を通らないので、自分か相手のどちらかが `/tmp` を隔離していても相手から辿れる。`/proc` の無い macOS で PrivateTmp のような隔離はまず無い。「`/proc` が無く、かつ `/tmp` が隔離されている」組み合わせはまれ。辿れるかは `Spelling` の `usable_with_private_tmp` で分かる。

### 別の uid のプロセスと通信する時は?

connect は自分で綴りを解決するので、相手の uid は届くかに影響しない。影響するのは、bind した側の綴りを相手が辿る場面 (DGRAM の返信等) だけ。procB と、持ち主だけが入れる置き場 (`/run/user/<uid>`、macOS の `$TMPDIR`) の下の綴りは、別の uid から辿れない。`Options.usable_cross_uid` を指定すると、別の uid も辿れる置き場 (`/tmp` 等) の B の綴りを選ぶ。満たせない時は満たさない綴りに落とさず、スレッドの cwd 等の経路 (綴りは `Dangling`) に進むので、結果の `Spelling` を確かめる。

### 置き場を自分で決めたい

`Options.base` に B そのもののパス (例 `/tmp/app-<uid>/sockat`) を渡す。sockat はその中にプロセスごとの D を作るだけで、B の掃除はアプリに任せる。B が確かめに外れたらエラーで、自動の置き場に落とさない。

### 共有の volume を通してコンテナどうしで通信したい

共有の volume は運用者が場所を決めて mount するので、短いパスに置く。長いパスにする理由が無い。

### `ProtectProc=invisible` (systemd) の環境では?

隠れるのは他のユーザのプロセスで、同じ uid なら procB の綴りは辿れる。

## fork

### sockat は fork する?

しない。fork の副作用 (全部の fd の複製、`SIGCHLD`、`waitpid(-1)` の取り違え、`pthread_atfork`、connect では相手に見える pid) はプロセス全体に及ぶため。fork でしか届かない場面と、利用者が自分で fork する時の手法と注意は [fork-cwd](fork-cwd-ja.md)。

## DGRAM

### bind していないソケットで返信を受けられる?

受けられない。bind していないソケットには住所が無く、受け手は返信先を指定できない。返信を受けたい送り手は自分も bind する。例外は `socketpair` (最初からつながった組) と、Linux で `SO_PASSCRED` を付けた時の自動の abstract の名前。どれも OS の仕様で、言語によらない。

### 長いパスに bind した送り手に返信は届く?

綴りが生きている間は届く (procB は同じ uid、`/tmp` の B の実パスは別の uid も)。スレッドの cwd 等で bind した綴り (`Dangling`) と、`cleanup` の後は届かない。

### 返信を受けたい送り手が、長いパスに bind する必要はある?

普通は無い。返信用のパスは送り手が自分で選べるので、短い場所に置ける。

## 速さ

### 同じパスに何度も connect する時は速い?

`resolve_for_connect` で 1 度作った綴りを何度も connect に使い、使い終わったら `cleanup` する。綴りを作る手数 (置き場の symlink の作成・削除) が 1 回で済む。既定の `connect` は綴りを残さず、プロセスの中に D と E を残さない (使い回すのは B とその fd だけ)。

### 既定の `connect` は重い?

普段は軽い。最初に試すのは置き場への書き込みもスレッドも要らない経路 (Linux の `/proc/self/fd/<dirfd>/<名前>`、macOS の相対パス・広げた sockaddr、FreeBSD の `connectat`) で、CLI の 1 回だけの connect は普通ここで終わる。次に使い捨てのスレッドの cwd を試し、置き場 B の直下に symlink を作って connect し、すぐ消す経路まで進むのは、ファイル名がかなり長く、スレッドの cwd も使えない時。

### 既定の `connect` が綴りをキャッシュしないのはなぜ?

隠れた状態がプロセスの中にでき、いつ片付くかが利用者から見えず、長命のプロセスでは宛先の数だけ symlink が溜まるため。再利用したい時は resolve を使う。

## 後始末

### 既定の `bind` は何を残す?

パスが長い時だけ、`/tmp/sockat-<uid>` の中に小さなディレクトリと symlink を残す。容量はほぼ 0 で、OS の一時ディレクトリの掃除で消える。すぐ片付けたい時は `bind_ex` の `remove()` を使う。

### `/tmp/sockat-<uid>` の中身は消してよい?

よい。使用中のプロセスのソケットも、元のパスでは働き続ける。使われていない物だけを消したい時は `sweep()` を呼ぶ。

### sockat は残った物を自動で片付けない?

片付けない。ssh-agent や tmux と同じく OS の掃除に任せる。片付けたい時に `sweep()` を呼ぶ。

### 試験を繰り返すと `/tmp/sockat-<uid>` に溜まる

試験の最後で `sweep()` を 1 回呼ぶ。他の試験が並行して走っていても、使用中の物は消さない。

### 長いパスに何度も bind する daemon は?

bind ごとに symlink が 1 つ増え、プロセスが終わるまで残る。セッションごとにソケットを作るような daemon は、`bind_ex` の `remove()` で片付ける。

### 既定の `connect` は何か残す?

残さない。

### `remove()` はいつ呼ぶ?

listener を閉じる前に呼ぶ。閉じた後だと、同じパスに作り直された別のファイルを見分けられずに消すことがある ([詳しく](../docs/findings/2026-11-19-inode-reuse-after-close.md))。`remove()` は listener を閉じない。

### 置き場を片付けた後の綴りを他人が作り直せるのは危なくない?

std でも同じ。元のパスのファイルを消した後は、そのディレクトリに書ける人が同じパスに作り直せる。片付けた後の古い綴りやパスを使わない。
