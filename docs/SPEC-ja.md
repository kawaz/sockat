# sockat 仕様

> [English](./SPEC.md) | 日本語

言語によらない sockat の振る舞い。各言語の実装はこれに従う。判断と却下した案は [docs/decisions](decisions/INDEX.md)、Rust 固有の話 (型、`unsafe` の置き場、tokio) は [sockat-rs の MANUAL](https://github.com/kawaz/sockat-rs/blob/main/docs/MANUAL-ja.md) にある。

## 用語

| 用語 | 意味 |
|---|---|
| 標準 | その言語の標準ライブラリの Unix domain socket の bind / connect |
| 標準に渡す長さ | その言語の標準が受け付けるパスの最長。これ以下は標準にそのまま渡す。多くは `sun_path` − 1、Java は `sun_path` − 2 ([DR-0004](decisions/DR-0004-standard-length-per-language.md)) |
| sockaddr に入る長さ | `sun_path` の長さ − 1 バイト (NUL の分を除く)。広げていない sockaddr に入る綴りの最長 |
| ディレクトリ / ファイル名 | パスの最後の要素の前と、最後の要素 |
| 綴り | カーネルに渡すパスの文字列。同じ場所を指す別の綴りを作るのが経路 |
| D | sockat が bind / connect のたびに作る自分専用のディレクトリ (「中心の経路」) |
| R | ソケットのディレクトリを指す乱数の名前の symlink。D の中 (D 無しの fork ではソケットのディレクトリの中) に作る |

## 対象

- pathname 型の Unix domain socket の bind (と listen) / connect
- Unix 系の OS。Windows は対象外

## 公開する操作

| 操作 | Rust | Python | Go | fork | ブロック | 戻り値 |
|---|---|---|---|---|---|---|
| bind | `bind` | `bind` | `Listen` | 試す | (待たない) | listen 済みの標準の listener |
| 後始末つきの bind | `bind_ex` | `bind_ex` | `ListenEx` | 試す | (待たない) | 標準の listener と `discard()` |
| connect | `connect` | `connect` | `Dial` | 試さない | する | 標準の stream |
| ブロックしない connect | `connect_nonblocking` | `connect_nonblocking` | なし | 試さない | しない | 非ブロッキングの標準の stream |
| fork してでも届く connect | `connect_any` | なし | なし | 試す | する | `AnyConnection { stream, forked }` |
| 同 (ブロックしない) | `connect_any_nonblocking` | なし | なし | 試す | しない | 同上 (stream は非ブロッキング) |

- 名前は仮。他の言語はその言語の命名の慣習に合わせる。振る舞いは上の表に従う
- 戻り値の listener / stream は標準が返すのと同じ型。標準の代わりに置き換えるだけで使える
- `_ex` は bind の側だけ。bind したソケットのファイルの realpath と `(st_dev, st_ino)` を覚え、`discard()` で listener を閉じ、そのパスの `(st_dev, st_ino)` が同じ時だけファイルを消す
  - 覚えるのは bind が通った直後 (経路の中で、listener を返す前)。覚えられなければ listener を閉じ、ファイルは消さずにエラーを返す (消せない `discard()` を成功に見せない)
  - 引数のパスは入口で一度だけ文字列にし、覚える・bind する・返すのすべてにその値を使う (呼ぶたびに違う値を返しうるパスの型で、覚えた物と bind した物を食い違わせない)
  - `discard()` は、ファイルが既に無い時と別のファイルに置き換わっていて消さない時も成功を返す。失敗を返すのは、確かめられない時 (`lstat` が `ENOENT` / `ENOTDIR` 以外で失敗) と消そうとして失敗した時 (消せたか分からないのを成功に見せない)
  - 確かめてから消すまでと、bind してから覚えるまでの間に、ソケットのディレクトリに書ける者がファイルをすり替えるのは防げない (inode を指定して消す手段が POSIX に無い)
- `connect_any` 系は、他の経路が全部使えない時に fork してでも connect する。pid は返さない。`forked` は fork の経路を通った時だけ真
- `connect_any` 系は既定の API に出さず、使う人が選んで有効にする仕組みの後ろに置く (Rust は feature `any`) ([DR-0007](decisions/DR-0007-connect-any-is-opt-in.md))。fork の経路を作れない言語は出さず、README の表に「fork の経路なし」と書く ([DR-0002](decisions/DR-0002-no-connect-any-without-fork.md))
- 標準の connect が元から待たない言語 (Node.js 等) は、標準と同じ形の connect を 1 つだけ出す ([DR-0003](decisions/DR-0003-single-connect-when-standard-never-blocks.md))
- `connect` / `connect_nonblocking` は fork の経路に来た所で `ENAMETOOLONG` を返す
- ブロックしない connect は、connect の前にソケットを非ブロッキングにしてそのまま返す。相手の backlog が満杯なら待たずに失敗する。`EINPROGRESS` はエラーとして返し、ソケットを閉じる
- 自前で作るソケットは、その言語の標準が作るソケットと同じ設定にする (close-on-exec、`SO_NOSIGPIPE`、listen の backlog 等)。backlog を指定する口は作らない
- listener を閉じた時のソケットファイルは、短いパスでは標準と同じ (Go の標準は消す)。長いパスでは、標準が消す言語でも消さない (カーネルが覚えている綴りは元のパスでない)。消す言語では README の「標準と違う点」に書く。消すのは `_ex` の `discard()`

## 短いパス

標準に渡す長さ以下のパスは、標準にそのまま渡す。何も足さず、環境変数も読まない。それを超えたら経路に回す ([DR-0004](decisions/DR-0004-standard-length-per-language.md))。

- 先頭以外に NUL を含むパスは、長さによらず標準に渡さず引数の誤りにする ([DR-0006](decisions/DR-0006-nul-is-invalid-at-any-length.md))
- Linux / Android で先頭が NUL のパス (abstract namespace) は対象外で、長さによらず標準にそのまま渡す。言語固有の abstract の書き方 (Go の `@` 等) も同じ
- abstract namespace の無い OS では、先頭が NUL のパスも長さによらず引数の誤り
- 標準にブロックしない connect が無い言語では、ブロックしない connect に限り、標準と同じアドレスで自前のソケットを connect する
- 経路の綴りを標準が受け付けない時 (標準に渡す長さが sockaddr に入る長さより短い言語) も、標準と同じアドレスで自前のソケットを使う

| OS | sockaddr に入る長さ |
|---|---|
| Linux / Android / illumos | 107 バイト |
| macOS / iOS 等 Apple の OS / FreeBSD / NetBSD / OpenBSD | 103 バイト |

## 長いパスの経路と試す順番

標準に渡す長さを超えるパスは、次の順に試し、最初に使えた経路で bind / connect する ([DR-0012](decisions/DR-0012-own-directory-and-thread-cwd.md))。

- 最後がファイル名でないパス (`dir/`、`dir/.`、`dir/..`、`..`) は、何も作らずに引数の誤り
- 最初にソケットのディレクトリを `stat` で引き、realpath を取る。無ければ `ENOENT`、ディレクトリでなければ `ENOTDIR`、realpath を引けなければそのエラー (どれも長さの判定や D を作るより前)。ソケットのディレクトリの fd が要る経路 (/proc、connectat、fork、D 無しの fork の R) だけがそれを開き、開けなければその経路は使えない (他の OS の `O_RDONLY` は読み取り権限の無いディレクトリを開けない)
- どの経路も、呼び出し元のプロセスの cwd も呼び出し元のスレッドの cwd も変えない
- ディレクトリの開き方 (置き場、ソケットのディレクトリ): Apple の OS は `O_SEARCH` (カーネルが `EISDIR` / `EINVAL` を返したら `O_RDONLY`)、Linux は `O_PATH | O_DIRECTORY`、他は `O_RDONLY | O_DIRECTORY`

### 試す順番

| 順 | bind | `connect` / `connect_nonblocking` | `connect_any` 系 |
|---|---|---|---|
| 1 | 標準に渡す長さ以下なら標準にそのまま (「短いパス」) | 同じ | 同じ |
| 2 | 中心の経路 (スレッド cwd。FreeBSD は bindat) | 中心の経路 (スレッド cwd。FreeBSD は connectat) | 同左 |
| 3 | 中心の経路の /proc 版 (`/proc` を使える Linux / Android) | 同左 | 同左 |
| 4 | 中心の経路を fork で | 予備の経路 | 予備の経路 |
| 5 | `ENAMETOOLONG` | `ENAMETOOLONG` | fork の経路 |

- bind の 4 は、2・3 がスレッド cwd / `/proc` を使えない、または `/proc` の綴りに収まらない時に試す。D をどこにも作れない時は D 無しの形で試す (「D の置き場」)。綴りが sockaddr に入らない時は試さず `ENAMETOOLONG`
- bind は /proc (D を通さない形)・相対パス・広げた sockaddr・置き場の symlink の経路を使わない (綴りが後で無関係なファイルに当たるか、アドレスが途中で切れて読む側を壊すか、中心の経路で足りる)
- connect の綴りは相手に残らない (connect した側のソケットは bind されない) ので、予備の経路は綴りにランダムな部品を挟まない

### 中心の経路

1. 置き場 (「D の置き場」) を開いて fd で掴み、その中に `mkdirat` で mode 0700 の D を作る。名前は `sockat.` (ソケットのディレクトリでは `.sockat.`) + 英数 62 種から 10 文字 (OS の安全な乱数)。`EEXIST` で引き直し、16 回で打ち切る
2. D を開く (Linux は `O_PATH | O_DIRECTORY | O_NOFOLLOW`、Apple の OS は `O_SEARCH | O_DIRECTORY | O_NOFOLLOW` (カーネルが `EISDIR` / `EINVAL` を返したら `O_RDONLY`)、他の OS は `O_RDONLY | O_DIRECTORY | O_NOFOLLOW`。`O_PATH` と `O_SEARCH` は umask が持ち主の読み取りを削っても開ける)。`fstat` で「ディレクトリ・持ち主が実効 uid・group と other に権限が無い」を確かめ、0700 にそろえる
   - `O_PATH` の fd: `/proc` を使えれば `chmod("/proc/self/fd/<fd>", 0700)`。使えなければ D を名前で `O_RDONLY | O_DIRECTORY | O_NOFOLLOW` で開き直し、`(st_dev, st_ino)` が最初の fd と同じことを確かめて `fchmod` (`O_PATH` の fd に `fchmod` は `EBADF`)
   - 他の fd: `fchmod`
   - 確認が通った後に開き直せない・そろえられない時は「作れない」とし、手順 5 で D を片付ける
3. D の中に R を作る: `symlinkat(<ソケットのディレクトリの realpath>, Dfd, R)`。R の名前は英数 62 種から 10 文字 (`sockat.` を付けない)。`EEXIST` で引き直し、16 回で打ち切る
4. D の fd を基準に `R/<ファイル名>` で bind / connect する (「D の fd を基準にする手段」)
5. 片付け: R は自分が作れた時だけ `unlinkat(Dfd, R)`。D は手順 2 の確認が通り、`fstatat(置き場の fd, D の名前, AT_SYMLINK_NOFOLLOW)` の `(st_dev, st_ino)` が fd と一致する時だけ `unlinkat(置き場の fd, D の名前, AT_REMOVEDIR)`。fd を閉じる。成功でも失敗でもする。消す失敗は無視する

- 綴り `R/<ファイル名>` は 11 バイト + ファイル名。ファイル名の上限は sockaddr に入る長さ − 11 (Linux / illumos 96、Apple の OS / BSD 92)
- 片付けた後は R がどこにも無いので、カーネルが返す綴りを後でプロセスの cwd 等の別の文脈で解決しても、無関係なファイルに当たらない
- 確認に落ちた D は他人の物とみなし、中身も含めて触らない
- 長さと、手段を使えるか (確かめられる所まで) は D を作る前に確かめる。使えなければ何も作らずに次へ
- /proc 版の綴りの長さは D の fd の番号で変わり、開くまで分からない。D を作る前は見積もりで確かめ、開いた後に確かめ直す (収まらなければ D を片付けて次へ)
- `/proc` を使えるかの確認に、ソケットのディレクトリの fd は要らない (`/` か D の fd で確かめる)

### D の置き場

| 順 | 置き場 | 条件 |
|---|---|---|
| 1 | `${TMPDIR:-/tmp}` | 相対パスも可 (一度開いて fd で掴む) |
| 2 | `/tmp` | 1 で作れない時だけ。1 と同じ綴りなら飛ばす |
| 3 | ソケットのディレクトリ | 2 でも作れない時だけ。名前は `.sockat.XXXXXXXXXX` (利用者のディレクトリなので、残っても sockat の物と分かり目立たない)。bind ではここに書けるはず。connect では書けるとは限らない |

- 「作れない」は、置き場を開けない、D を作れない、名前を使い切った、乱数が取れない、手順 2 の確認が通らない、R を作れない
- どこにも作れない時、bind は D 無しの fork に進む。子がソケットのディレクトリの fd に `fchdir` し、そこに作った R (名前は `.sockat.XXXXXXXXXX`、ソケットのディレクトリの realpath を指す) を通して `.sockat.XXXXXXXXXX/<ファイル名>` で bind する。綴りは 19 バイト + ファイル名 (ファイル名は Linux / illumos 88、Apple の OS / BSD 84 まで)。R も作れなければ `ENAMETOOLONG`
- どこにも作れない時、connect 系は予備の経路に進む
- 置き場の安全 (sticky 等) と長さは問わない。D を fd で掴み、綴りに置き場が出ない

### D の fd を基準にする手段

| 手段 | OS | やり方 | 使えない時 |
|---|---|---|---|
| スレッド cwd | Linux / Android | 使い捨てのスレッドで `unshare(CLONE_FS)` → `fchdir(Dfd)` → `R/<ファイル名>` で bind / connect | seccomp の filter が掛かっているか確かめられない (`prctl(PR_GET_SECCOMP)` が 0 以外か失敗)、`unshare` が断られた、スレッドを作れない・固定できない |
| スレッド cwd | Apple の OS | 使い捨てのスレッドで `pthread_fchdir_np(Dfd)` → 同上 | `pthread_fchdir_np` が無い・失敗した、スレッドを作れない・固定できない |
| bindat / connectat | FreeBSD | スレッドを使わず `bindat(Dfd, ...)` / `connectat(Dfd, ...)` に `R/<ファイル名>` を渡す | |
| /proc 版 | `/proc` を使える Linux / Android | スレッドを使わず `/proc/self/fd/<Dfd>/R/<ファイル名>` で bind / connect | `/proc/self/fd/<Dfd>` を引けない、綴りが sockaddr に入らない (ファイル名およそ 79 バイトまで、fd の桁で変わる) |
| (無い) | NetBSD / OpenBSD / illumos | 手が無い (bind は fork へ) | |

- 呼び出し元は使い捨てのスレッドが終わるまで待ってから R と D を片付け、fd を閉じる。待つのが割り込まれても (Python の `KeyboardInterrupt` 等)、スレッドが終わるまでは片付けない (先に閉じた fd の番号が使い回されると、スレッドが無関係なディレクトリに移って bind する)
- スレッドは sockat が作った使い捨てで、使い終わったら捨てる。呼び出し元のスレッドの cwd には触らない (`pthread_fchdir_np(-1)` で戻すと、呼び出し元がスレッドに付けた cwd を消しうる)
- Linux で seccomp の filter が掛かっている時は `unshare` を呼ばない。filter がプロセスの kill (SIGSYS) で断る環境 (systemd の `SystemCallFilter=` の既定) がある
- `unshare` の後の `fchdir` の失敗 (`EACCES` 等) は本当の失敗として返す
- 呼び出し元がソケットを作り、D の fd を持つ。ブロックしない connect ではその前にソケットを非ブロッキングにする。bind の後の listen は呼び出し元がする
- `pthread_fchdir_np` は libSystem の非公開 API (`__pthread_fchdir` syscall)。実行時に引く
- スレッド cwd と /proc 版は副作用が無い (peer の pid は呼び出し元のまま、fd の複製も無く、他のスレッドの cwd は変わらない)。そのため `connect` / `connect_nonblocking` も試す
- /proc 版の綴りも R を通すので、後で fd の番号が使い回されても無関係なファイルに当たらない

### fork の経路

1. 親がソケットを作り、fd を持ち、sockaddr を組み立ててから fork する。ブロックしない connect では fork の前にソケットを非ブロッキングにする
2. 子は `fchdir(fd)` → 綴りで `bind` / `connect` → `_exit(結果)` (0 が成功、1〜255 が errno)

| 操作 | 子が `fchdir` する fd | 綴り |
|---|---|---|
| bind | D | `R/<ファイル名>` |
| bind (D をどこにも作れない時) | ソケットのディレクトリ | `.sockat.XXXXXXXXXX/<ファイル名>` (R はソケットのディレクトリの中) |
| `connect_any` 系 | ソケットのディレクトリ | ファイル名 |

3. 親はその pid だけを `waitpid` し、それから R と D を片付ける。bind の後の listen は必ず親がする ([DR-0010](decisions/DR-0010-fork-bind-listen-by-parent.md))

- 子の区間は async-signal-safe な呼び出しだけ (allocation・lock・言語の後始末を通さない)
- `waitpid` が `ECHILD` (status を他者に刈り取られた) なら、ソケットの状態から結果を読む: bind は `getsockname` にパスが入っているか、connect は `getpeername` が通るか。失敗は一般のエラー
- Apple の OS の `connect_any` 系は、カーネルが受け付ければ広げた sockaddr を使う

### 予備の経路 (connect 系)

中心の経路が使えない時 (手段が無い、D を作れない、綴りが収まらない) に試す。

| OS | 試す順番 |
|---|---|
| Linux / Android (`/proc` を使える) | /proc → fd で掴む形 → symlink |
| Linux / Android (`/proc` を使えない) | 相対パス → symlink |
| macOS / iOS 等 Apple の OS | 相対パス → 広げた sockaddr → symlink |
| FreeBSD | connectat |
| NetBSD / OpenBSD / illumos / その他の Unix | 相対パス → symlink |

| 経路 | やり方 | 使える条件 |
|---|---|---|
| /proc | ソケットのディレクトリを開き、`/proc/self/fd/<fd>/<ファイル名>` を渡す | `/proc/self/fd/<fd>` を stat で引け、綴りが sockaddr に入る長さ以内 (ファイル名およそ 90 バイトまで、fd の桁で変わる) |
| fd で掴む形 | D を作り (中心の経路の手順 1・2・5)、その中に `symlinkat` でソケットのファイルを指す `s` を作り、`/proc/self/fd/<Dfd>/s` を渡す。`s` は自分が作れた時だけ消す | `/proc` を使える Linux / Android。D と `s` を作れる |
| 相対パス | cwd からの相対パスを渡す。文字列を書き直すだけで `chdir` しない | 元のパスが絶対パスで、相対パスが sockaddr に入る長さ以内 (「相対パスの作り方」) |
| 広げた sockaddr | `sun_len` とアドレス長を `2 + パスの長さ` にした sockaddr で、元のパス、無理なら相対パスを渡す | Apple の OS。パスが 253 バイト以内。カーネルが `EINVAL` / `ENAMETOOLONG` を返したら使えない |
| symlink | 安全な置き場にソケットのファイルを指す symlink を作り、`<置き場>/sockat.XXXXXXXXXX` を渡して、すぐ消す | 綴りが sockaddr に入る長さ以内で、symlink を作れる安全な置き場がある (「symlink の置き場と名前」) |
| connectat | ソケットのディレクトリを開き、`connectat(fd, <ファイル名>)` | FreeBSD。ファイル名が 103 バイト以内 |

- fd で掴む形と symlink の先は、ソケットのファイルの綴りそのもの (相対パスなら cwd を前に付ける)

### 相対パスの作り方

1. パスが cwd の綴り (`getcwd`、または `stat` の `(st_dev, st_ino)` が `.` と一致する `$PWD`) で始まれば、区切り単位でそれを削る
2. 1 で sockaddr に入る長さ以内にならない時だけ、ソケットのディレクトリと cwd を `realpath` で実パスにし、`..` で上る綴りを作る
3. 短い方を使う。使う前に相対パスのディレクトリと元のディレクトリの `(st_dev, st_ino)` が同じこと、cwd の `(st_dev, st_ino)` が 1 の前と同じことを確かめる。違えばこの経路は使えない
4. connect の後に cwd の `(st_dev, st_ino)` が変わっていたら、結果を捨てて一般のエラーを返す

### symlink の置き場と名前

| 項目 | 仕様 |
|---|---|
| 置き場の候補 | `TMPDIR` (空でない絶対パスの時)、`/tmp` の順。`TMPDIR` が `/tmp` と同じ綴りなら 1 回だけ |
| 安全な置き場 | symlink を辿って stat し、ディレクトリで、次のどちらか<br>sticky bit が立ち、持ち主が root か実効 uid<br>持ち主が実効 uid で、`mode & 0o022 == 0` |
| 名前 | `sockat.` + 英数 62 種から 10 文字。OS の安全な乱数から取る |
| 衝突 | `EEXIST` で名前を引き直す。16 回で打ち切り、その候補は使えないとみなす |
| 片付け | connect が成功しても失敗しても消す。消す失敗は無視する |

- 候補ごとに、何かを作る前に綴りの長さと置き場の安全を確かめる。収まらない・安全でない・作れない候補には何も作らず次へ進む

## 経路の失敗の扱い

- 経路が実際に bind / connect して失敗したら (`ENOENT`、`EADDRINUSE`、`ECONNREFUSED` 等)、そのエラーを返し、次の経路も次の置き場も試さない
- 次へ進むのは、経路自体が使えない時だけ
  - 綴りが収まらない
  - D の置き場で D か R を作れない (次の置き場へ)
  - D の fd を基準にする手段が使えない (「D の fd を基準にする手段」の「使えない時」)
  - `/proc` を使えない
  - fd で掴む形で D か `s` を作れない
  - カーネルが広げた sockaddr を受け付けない
  - 置き場が安全でない・symlink を作れない
  - 相対パスの経路で、作った綴りのディレクトリが元と `(st_dev, st_ino)` で一致しない、または cwd が既に変わっている
- ディレクトリが無い時はどの OS でも `ENOENT`。ディレクトリを先に引くので、長さの判定より前に決まる
- `connect` / `connect_nonblocking` は fork の手前で `ENAMETOOLONG` を返す

## どこから届かなくなるか

標準に渡す長さを超えるパスが `ENAMETOOLONG` になる時 (ディレクトリがあり、D を作れる前提。数字はバイト)。

| OS | `bind` | `connect` 系 | `connect_any` 系 |
|---|---|---|---|
| Linux / Android (`/proc` あり) | ファイル名 > 96 | 届く (fd で掴む形) | 届く |
| Linux / Android (`/proc` 無し) | ファイル名 > 96 | 中心の経路が使えず (ファイル名 > 96 かスレッド cwd が使えない)、相対パス > 107、symlink も使えない | ファイル名 > 107、symlink も使えない |
| FreeBSD | ファイル名 > 92 | ファイル名 > 103 | ファイル名 > 103 |
| macOS / iOS 等 Apple の OS | ファイル名 > 92 | 中心の経路が使えず (ファイル名 > 92 かスレッド cwd が使えない)、元のパスも相対パスも > 253、symlink も使えない | ファイル名 > 253、symlink も使えない |
| NetBSD / OpenBSD / その他の BSD | ファイル名 > 92 | 相対パス > 103、symlink も使えない | ファイル名 > 103、symlink も使えない |
| illumos | ファイル名 > 96 | 相対パス > 107、symlink も使えない | ファイル名 > 107、symlink も使えない |

- Linux でスレッド cwd が使えない時、bind はファイル名およそ 79 バイトまで /proc 版、その先 96 までは fork
- D をどこにも作れない時、bind は D 無しの fork でファイル名 88 (Apple の OS / BSD 84) まで届く (ソケットのディレクトリに R を作れる時)。connect 系は予備の経路の分だけ届く (fd で掴む形は使えない)
- ディレクトリを引く等でフルパスを渡すので、PATH_MAX (macOS 1024、Linux 4096) を超えるパスは `ENAMETOOLONG`。sockat の責務外

## fork の副作用

| 範囲 | 副作用 |
|---|---|
| 相手から見える (`connect_any` 系だけ) | サーバに見える peer の pid は終了した子の pid。uid / gid は呼び出し元と同じ<br>Linux の `SO_PEERCRED` は子の pid のまま<br>macOS の `LOCAL_PEERPID` は呼び出し元が send すると呼び出し元の pid になる |
| 相手から見えない (`bind` と `connect_any` 系) | 子は終了まで全 fd の複製を持つ。その間に他のスレッドが閉じたソケットやパイプは開いたままになる<br>親に `SIGCHLD` が届く<br>`pthread_atfork` の handler が走る<br>監視ツールに短命の子が見える<br>他のスレッドの `waitpid(-1)` が子を刈り取りうる |

- bind は相手から見える副作用が無い。子は bind だけして listen は親がするので、クライアントに見えるサーバの peer 情報 (macOS の `LOCAL_PEERPID` / `LOCAL_PEEREPID` / audit token の pid と pidversion、Linux の `SO_PEERCRED` / `SO_PEERPIDFD`) は send の前から親 (実測 2026-11-18、macOS 26.5.2 と Linux) ([DR-0010](decisions/DR-0010-fork-bind-listen-by-parent.md))

## 長いパスで標準と違う点

| 点 | 内容 |
|---|---|
| カーネルが返すアドレス | bind した側の `getsockname` と、そこへ connect した側の `getpeername` は `R/<ファイル名>` (/proc 版は `/proc/self/fd/<fd>/R/<ファイル名>`) を返す。R はもう無いので、後でどこで解決しても何にも当たらない。標準の型でアドレスを返す口を差し替えられる言語 (Python) は元のパスを返す (Python の asyncio は listener の `getsockname` の綴りを `stat` / unlink する)。差し替えられない言語は元のパスを呼び出し元が持つ |
| ディレクトリを先に引く | 中心の経路は R を作る時にソケットのディレクトリを realpath で引く。予備の経路の /proc・相対パス・connectat と `connect_any` 系の fork はディレクトリを引いてからファイル名で渡す。その間の rename や symlink の張り替えは反映されない。広げた sockaddr と symlink は標準と同じ |
| 他のスレッドの chdir | 相対パスの経路は、間に cwd が変わったままなら一般のエラー。変えて戻した場合は見えない |
| 残骸 | D・R・置き場の symlink を消す前にプロセスが死ぬと、`sockat.XXXXXXXXXX` が置き場に、`.sockat.XXXXXXXXXX` (D か D 無しの fork の R) がソケットのディレクトリに残る。D を `O_RDONLY` で開く OS (Linux と Apple の OS 以外) では、umask が持ち主の読み取りを削っていると D を開けず、確かめられないので触らずに残す |

- 先頭以外の NUL は短いパスでも引数の誤り。標準が NUL で黙って切り詰める言語 (Go 等) では、README の「標準と違う点」に書く

## エラー

| 状況 | エラー |
|---|---|
| ディレクトリが無い / connect 先が無い | `ENOENT` |
| ディレクトリの位置にディレクトリでない物がある | `ENOTDIR` |
| bind 先に既にファイルがある | `EADDRINUSE` |
| 誰も listen していないソケットファイル | `ECONNREFUSED` |
| backlog が満杯 | Linux はブロックしない connect で `EAGAIN` (ブロックする connect は待つ)、macOS は `ECONNREFUSED` |
| どの経路にも収まらない。`connect` 系では fork の経路でしか届かない時も | `ENAMETOOLONG` |
| 標準に渡す長さを超えるパスで、名前で終わらない | 引数の誤り |
| 先頭以外に NUL を含むパス (長さによらない) | 引数の誤り |
| 相対パスの経路の途中で cwd が変わった | 一般のエラー |
| fork した子が正常に終了しなかった。または status を刈り取られ、bind / connect されていなかった | 一般のエラー |

- OS のエラーは、その言語の作法で errno を取り出せる形で返す
- 「引数の誤り」「一般のエラー」をどの型で表すかは各実装が決める

## 各実装に求めること

- 上の経路と順番に従う。その言語で作れない経路は飛ばし (使えない経路として次へ進む)、README に OS × 経路の表で明示する
- 自前で作ったソケットを標準の型に取り込む言語では、広げた sockaddr で connect したソケットを取り込んでも、取り込みやアドレスの取得で落ちないか確かめる。落ちるならその経路を作れない経路として飛ばす
- 経路は公開 API に出さない。試験はパッケージの中から各経路を直接呼んで強制する
- 環境を読む部分 (D の置き場、symlink の置き場の候補、`/proc/self/fd` の場所、Apple の OS で広げた sockaddr を受け付けるか、スレッド cwd を使えるか) は試験から差し替えられるようにする
- README とマニュアルにこの仕様へのリンクを置く。仕様と食い違う振る舞いを入れる時は、先にこの仕様を直す

## 実装が確かめる試験の観点

| 観点 | 確かめること |
|---|---|
| 短いパスの境界 | 標準に渡す長さちょうどは標準にそのまま渡り、1 バイト長いと経路に回る (標準自身で境界を確かめる) |
| 中心の経路 | 強制して、プロセスの cwd も呼び出し元のスレッドの cwd も変わらない、ソケットが元のパスにでき送受信できる、peer の pid が呼び出し元、片付けの後に置き場に何も残らない |
| 返る綴り | bind した後、返る綴り (`getsockname`) をそのまま unlink / stat しても無関係なファイル (cwd の同名ファイル、fd の番号を使い回させた別のディレクトリの同名ファイル) に当たらない |
| 差し替えたディレクトリ | D を作ってから開くまでに差し替えたディレクトリ (持ち主が違うか group / other に権限が付いた) を使わず、その中身も消さない |
| D の置き場 | `TMPDIR` に作れない時は `/tmp`、それも作れない時はソケットのディレクトリに `.sockat.` の名前で作る。相対パスや深い `TMPDIR` でも使える。どこにも作れない時、bind は D 無しの fork、connect 系は予備の経路 |
| 手段が使えない時 | スレッド cwd を使えなくして、`/proc` を使える Linux は /proc 版に進む。それも使えない時、bind は fork (peer は親)、connect 系は予備の経路に進む |
| 予備の経路 | 各経路を強制して、ソケットに届き、置き場に何も残らない。symlink は安全でない置き場を飛ばす、深すぎる `TMPDIR` で `/tmp` に回る、名前の衝突を飛ばし 16 回で打ち切る |
| 失敗をやり直さない | `ENOENT` / `EADDRINUSE` / `ECONNREFUSED` を返し、後の経路・置き場に何も作らない |
| connect と fork | `connect` 系は fork でしか届かない時に `ENAMETOOLONG`、`connect_any` 系は届いて `forked` が真 |
| 相対パスと cwd | 相対パスの経路の途中で cwd が変わったら一般のエラー |
| fork | fork の経路で bind したサーバに connect したクライアントから見える peer が親 (send の前も後も)。`connect_any` 系の peer の pid の振る舞い、`SIGCHLD` を `SIG_IGN` にした時の結果の読み取り |
| macOS | connect 系で 253 バイトのパスが広げた sockaddr で通る。bind は広げた sockaddr を使わない |
| ブロックしない connect | backlog が満杯で待たずに失敗する |
| 名前で終わらないパス、先頭以外の NUL | 何も作らずに引数の誤り。NUL は短いパスでも。先頭が NUL (abstract) は標準に渡る |
| カーネルが返すアドレス | 長いパスでも取得で落ちない。差し替えられる言語では、listener・accept したソケット・connect したソケットの各口が元のパスを返し、その言語の代表的な上のライブラリ (Python の asyncio の `start_unix_server(sock=...)` 等) が引数を足さずに短いパスと同じに動く |
| `_ex` | `discard()` で閉じてファイルが消える。間に別のファイルに置き換えられていたら消さない |

- 経路は OS で違うので、少なくとも macOS と Linux で回す。他の Unix は CI の VM で回す
- cwd やシグナルの扱いのようにプロセス全体に効く設定を変える試験は、子プロセスの中で行う
- fork の経路の子は全 fd の複製を一瞬持つので、「誰も listen していないソケット」は別プロセスで作る

## 未確定

- Android と macOS 以外の Apple の OS は全体が未確認
- NetBSD・OpenBSD・illumos は peer の資格情報が未確認
- ブロックしない connect が `EINPROGRESS` を返さないことは Linux と macOS でだけ確認済み
- `connect_any` 系の fork と FreeBSD の connect の予備の経路は D を通さない (ソケットのディレクトリの fd とファイル名)。kawaz 未確認 ([DR-0012](decisions/DR-0012-own-directory-and-thread-cwd.md) の「未確定」)
