# sockat 仕様

> [English](./SPEC.md) | 日本語

言語によらない sockat の振る舞い。各言語の実装はこれに従う。設計の判断と却下した案は [sockat-rs の DR-0001](https://github.com/kawaz/sockat-rs/blob/main/docs/decisions/DR-0001-long-socket-path-routes.md)、Rust 固有の話 (型、`unsafe` の置き場、tokio) は [sockat-rs の MANUAL](https://github.com/kawaz/sockat-rs/blob/main/docs/MANUAL-ja.md) にある。

## 用語

| 用語 | 意味 |
|---|---|
| 標準 | その言語の標準ライブラリの Unix domain socket の bind / connect |
| 標準に渡す長さ | その言語の標準が受け付けるパスの最長。これ以下は標準にそのまま渡す。多くは `sun_path` − 1、Java は `sun_path` − 2 ([DR-0004](decisions/DR-0004-standard-length-per-language.md)) |
| sockaddr に入る長さ | `sun_path` の長さ − 1 バイト (NUL の分を除く)。広げていない sockaddr に入る綴りの最長。/proc・相対パス・symlink・スレッド cwd・fork の経路の綴りの条件 |
| ディレクトリ / ファイル名 | パスの最後の要素の前と、最後の要素 |
| 綴り | カーネルに渡すパスの文字列。同じ場所を指す別の綴りを作るのが経路 |

## 対象

- pathname 型の Unix domain socket の bind (と listen) / connect
- Unix 系の OS。Windows は対象外

## 公開する操作

| 操作 | fork の経路 | ブロック | 戻り値 |
|---|---|---|---|
| `bind` | 最後に試す | (待たない) | listen 済みの listener |
| `connect` | 試さない | する | stream |
| `connect_nonblocking` | 試さない | しない | 非ブロッキングの stream |
| `connect_any` | 最後に試す | する | stream と `forked` を持つ名前付きの型 |
| `connect_any_nonblocking` | 最後に試す | しない | 非ブロッキングの stream と `forked` を持つ名前付きの型 |

- 戻り値の listener / stream は、標準の bind / connect が返すのと同じ型。標準の代わりに置き換えるだけで使える
- `connect_any` 系の戻り値は、標準の stream と `forked` (fork の経路を通った時だけ真) を持つ名前付きの型。形は言語の慣習で決める (Rust は struct 等)
- 名前はその言語の命名の慣習に合わせてよい。振る舞いは上の表に従う
- fork の経路を作れない言語では `connect_any` 系を出さない。README の表に「fork の経路なし」と書く ([DR-0002](decisions/DR-0002-no-connect-any-without-fork.md))
- 標準の connect が元から待たない言語 (Node.js 等) では、標準と同じ形の connect を 1 つだけ出し、`_nonblocking` を分けない ([DR-0003](decisions/DR-0003-single-connect-when-standard-never-blocks.md))
- `connect` / `connect_nonblocking` は fork の経路に来た所で `ENAMETOOLONG` を返す
- `connect_any` 系は、他の経路が全部使えない時に fork してでも connect する。pid は返さない
- `connect_any` 系は既定の API に出さない。使う人が自分で選んで有効にする、その言語の仕組みの後ろに置く (Rust は feature `any`、Python は別のモジュール等) ([DR-0007](decisions/DR-0007-connect-any-is-opt-in.md))
- ブロックしない 2 つは、connect の前にソケットを非ブロッキングにし、そのまま返す。相手の backlog が満杯なら待たずに失敗する
- ブロックしない connect は呼び出しの中で結果が出る前提。`EINPROGRESS` が返ったらそれをエラーとして返し、ソケットを閉じる (つながっていない stream を返さない)
- 自前で作るソケットは、その言語の標準が作るソケットと同じ設定にする (close-on-exec、`SO_NOSIGPIPE`、listen の backlog 等)
- listener を閉じた時のソケットファイルは、短いパスでは標準と同じ (Go の標準は消す)。長いパスでは、標準が消す言語でも消さない (カーネルが覚えている綴りは元のパスでなく、綴りで消すと別のファイルを消しうる)。消す言語では README の「標準と違う点」に書く

## 短いパス

標準に渡す長さ以下のパスは、標準にそのまま渡す。何も足さず、環境変数も読まない。それを超えたら経路に回す ([DR-0004](decisions/DR-0004-standard-length-per-language.md))。

- 先頭以外に NUL を含むパスは、長さによらず標準に渡さず引数の誤りにする ([DR-0006](decisions/DR-0006-nul-is-invalid-at-any-length.md))
- Linux / Android で先頭が NUL のパス (abstract namespace。ファイルではない) は sockat の対象外で、長さによらず標準にそのまま渡す。言語固有の abstract の書き方 (Go の `@` 等) も同じ
- abstract namespace の無い OS (Linux / Android 以外) では、先頭が NUL のパスも、長さによらず引数の誤り
- 標準にブロックしない connect が無い言語では、ブロックしない connect に限り、標準と同じアドレスで自前のソケットを connect する
- 経路の綴りを標準が受け付けない時 (標準に渡す長さが sockaddr に入る長さより短い言語) も、標準と同じアドレスで自前のソケットを使う

| OS | sockaddr に入る長さ |
|---|---|
| Linux / Android / illumos | 107 バイト |
| macOS / iOS 等 Apple の OS / FreeBSD / NetBSD / OpenBSD | 103 バイト |

## 長いパスの経路と試す順番

標準に渡す長さを超えるパスは、OS ごとに次の順で試し、最初に使えた経路で bind / connect する。

| OS | 試す順番 |
|---|---|
| Linux / Android (`/proc` を使える) | /proc → 相対パス → symlink → スレッド cwd → fork |
| Linux / Android (`/proc` を使えない) | 相対パス → symlink → スレッド cwd → fork |
| FreeBSD | bindat |
| macOS / iOS 等 Apple の OS の bind | 相対パス → symlink → スレッド cwd → fork |
| macOS / iOS 等 Apple の OS の connect 系 | 相対パス → 広げた sockaddr → symlink → スレッド cwd → fork |
| NetBSD / OpenBSD / illumos / その他の Unix | 相対パス → symlink → fork |

- 標準に渡す長さを超えるパスで、最後がファイル名でないもの (`dir/`、`dir/.`、`dir/..`、`..`) は、何も作らずに引数の誤りを返す
- どの経路も呼び出し元のプロセスの cwd を変えない
- Apple の OS の bind は広げた sockaddr を使わない。そのソケットのアドレスは途中で切れて `sun_path` に入らず、読む側を壊す (CPython の `getsockname` が後ろに無関係なバイトを付ける、Go の `net.FileConn` で相手の `RemoteAddr` が nil になる) ([DR-0009](decisions/DR-0009-apple-bind-without-widened-sockaddr.md))
- symlink の経路は、置き場の候補ごとに、安全なら置き場に直接 symlink を作り、安全でなければ fd で掴む形 (`/proc` を使える Linux / Android だけ) で試す。`TMPDIR` を `/tmp` より先に使い切る

### 各経路

| 経路 | やり方 | 使える条件 |
|---|---|---|
| /proc | ディレクトリを `O_PATH \| O_DIRECTORY` で開き、`/proc/self/fd/<fd>/<ファイル名>` を標準に渡す | `/proc/self/fd/<fd>` を stat で引け、綴り全体が sockaddr に入る長さ以内 (ファイル名はおよそ 90 バイトまで) |
| bindat | ディレクトリを `O_RDONLY` で開き、`bindat(2)` / `connectat(2)` でファイル名を渡す | FreeBSD。ファイル名が 103 バイトを超えたら `ENAMETOOLONG` |
| 相対パス | cwd からの相対パスを標準に渡す。文字列を書き直すだけで `chdir` しない | 元のパスが絶対パスで、相対パスが sockaddr に入る長さ以内。相対パスのディレクトリと元のディレクトリの `(st_dev, st_ino)` が一致し、綴りを作る間に cwd が変わっていない |
| 広げた sockaddr | `sun_len` とアドレス長を `2 + パスの長さ` にした sockaddr で、元のパス、無理なら相対パスを渡す | Apple の OS の connect 系だけ。パスが 253 バイト以内。カーネルが `EINVAL` / `ENAMETOOLONG` を返したら使えないとみなす |
| symlink | 置き場に短い symlink を作り、それを通した綴りを渡して、すぐ消す | 綴りが sockaddr に入る長さ以内 (*) で、symlink を作れる置き場がある。置き場が安全でない時は fd で掴む形で、`/proc` を使える Linux / Android の connect 系だけ |
| スレッド cwd | bind / connect するスレッドだけ cwd をディレクトリに移し、ファイル名で bind / connect する | Linux / Apple の OS。ファイル名が sockaddr に入る長さ以内 (*)。その言語でスレッドを作って固定できる |
| fork | ディレクトリの fd に `fchdir` した子を fork し、子がファイル名で bind / connect する | `bind` と `connect_any` 系だけ。ファイル名が sockaddr に入る長さ以内 (*) |

(*) Apple の OS の connect 系でカーネルが広げた sockaddr を受け付ける時は 253 バイト以内。bind と、カーネルが断った時は sockaddr に入る長さで判定する。

### 相対パスの作り方

1. パスが cwd の綴り (`getcwd`、または `stat` の `(st_dev, st_ino)` が `.` と一致する `$PWD`) で始まれば、区切り単位でそれを削る
2. 1 で sockaddr に入る長さ以内にならない時だけ、ソケットのディレクトリと cwd を `realpath` で実パスにし、`..` で上る綴りを作る
3. 短い方を使う。使う前に相対パスのディレクトリと元のディレクトリの `(st_dev, st_ino)` が同じこと、cwd の `(st_dev, st_ino)` が 1 の前と同じことを確かめる。違えばこの経路は使えない
4. bind / connect の後に cwd の `(st_dev, st_ino)` が変わっていたら、結果を捨てて一般のエラーを返す (できたかもしれないソケットファイルは消さない)

### symlink の置き場と名前

| 項目 | 仕様 |
|---|---|
| 置き場の候補 | `TMPDIR` (空でない絶対パスの時)、`/tmp` の順。`TMPDIR` が `/tmp` と同じ綴りなら 1 回だけ |
| 安全な置き場 | symlink を辿って stat し、ディレクトリで、次のどちらか<br>sticky bit が立ち、持ち主が root か実効 uid<br>持ち主が実効 uid で、`mode & 0o022 == 0` |
| 名前 | `sockat.` + 英数 62 種から 10 文字。OS の安全な乱数から取る |
| 衝突 | `symlink(2)` の `EEXIST` で名前を引き直す。16 回で打ち切り、その候補は使えないとみなす |
| bind の symlink | ソケットのディレクトリを指す。綴りは `<置き場>/sockat.XXXXXXXXXX/<ファイル名>` |
| connect の symlink | ソケットのファイル (元のパス) を指す。綴りは `<置き場>/sockat.XXXXXXXXXX` |
| symlink の先 | 利用者のパスの綴りそのもの (bind はそのディレクトリ部分。相対パスなら cwd を前に付ける) |
| 片付け | bind / connect が成功しても失敗しても消す。消す失敗は無視する |

- 候補ごとに、何かを作る前に綴りの長さと置き場の安全を確かめる。綴りが収まらない候補には何も作らず次へ進む
- 試す順: `TMPDIR` が安全なら symlink → 安全でなければ fd で掴む形 → `/tmp` が安全なら symlink → 安全でなければ fd で掴む形。fd で掴む形が無い OS では安全でない候補に何も作らず次へ進む
- symlink を作れない時 (置き場が無い・書けない、名前を使い切った、乱数が取れない) も次の候補へ進む

### fd で掴む形 (安全でない置き場)

`/proc` を使える Linux / Android で、安全でない置き場の候補に自分専用のディレクトリを作り、名前でなく fd で辿る ([DR-0008](decisions/DR-0008-unsafe-base-held-by-fd.md))。

0. 何かを作る前に、`/proc` を使えるか確かめる (置き場の fd で `/proc/self/fd/<fd>` を引ける)。使えなければ何も作らずに次へ
1. 置き場に mode 0700 のディレクトリを作る。名前と衝突の扱いは symlink と同じ (`sockat.` + 10 文字、`EEXIST` で引き直し 16 回で打ち切り)
2. それを `O_PATH | O_DIRECTORY | O_NOFOLLOW` で開いて fd を持ち (読み取り権限が無くても開ける)、`fstat` で「ディレクトリ・持ち主が実効 uid・group と other に権限が無い」を確かめる。違えば使えない。通ったら `chmod("/proc/self/fd/<fd>", 0700)` で持ち主の権限をそろえる (`O_PATH` の fd には `fchmod` できない。/proc の綴りは fd が指す実体に効くので、名前で触る時の差し替えの心配が無い)。umask が持ち主のビットを削る環境でも、確認に落ちて残骸が溜まらない
3. fd の中に `symlinkat` で、ソケットのファイル (元のパス) を指す symlink `s` を作る
4. 綴り `/proc/self/fd/<fd>/s` を渡す
5. 片付け: `s` は自分が `symlinkat` に成功した時だけ `unlinkat(fd, "s")` で消す。ディレクトリは、手順 2 の確認が通っていて、かつその名前を `lstat` した `(st_dev, st_ino)` が fd と一致する時だけ `rmdir` する (確認に落ちたディレクトリは他人の物とみなし、中身も含めて触らない)。fd を閉じる

- connect 系だけが使う。bind の綴り (`/proc/self/fd/<fd>/s/<ファイル名>`) は /proc の経路の綴りより長く、これが収まるなら /proc の経路が先に通っているので、bind には効かない
- 使えない: ディレクトリを作れない、`fstat` の確認が通らない、`symlinkat` が失敗した
- 使えないと分かった時は、作った物を片付けてから次の候補へ進む
- 片付けは bind / connect が成功しても失敗してもする。消す失敗は無視する

### スレッド cwd の経路

プロセスの cwd は変えない ([DR-0005](decisions/DR-0005-thread-cwd-route.md))。

| OS | やり方 |
|---|---|
| Linux / Android | 使い捨てのスレッドで `unshare(CLONE_FS)` → `fchdir(dirfd)` → ファイル名で bind / connect |
| Apple の OS | 使い捨てのスレッドで `pthread_fchdir_np(dirfd)` → ファイル名で bind / connect |
| その他 | 無い |

- どの OS も sockat が作った使い捨てのスレッドで行い、使い終わったら捨てる。呼び出し元のスレッドの cwd には触らない (`pthread_fchdir_np(-1)` で戻す形は、呼び出し元がスレッドに付けた cwd を消しうるので使わない)
- Linux: seccomp の filter が掛かっている時と確かめられない時 (`prctl(PR_GET_SECCOMP)` が 0 以外を返すか失敗する。emulate された環境や seccomp 無しのカーネルは `EINVAL`) は使えないとみなし、`unshare` を呼ばない。filter が `unshare` をエラーでなくプロセスの kill (SIGSYS) で断る環境 (systemd の `SystemCallFilter=` の既定の動作等) があり、呼ぶとプロセスが死ぬ
- `unshare` の後の `fchdir` の失敗 (`EACCES` 等) は、使えないのでなく本当の失敗として返す (fork の経路と同じ)
- 呼び出し元がソケットを作り、ディレクトリを開いた fd を持つ。ブロックしない connect ではその前にソケットを非ブロッキングにする。bind の後の listen は呼び出し元がする
- ディレクトリの開き方は fork の経路と同じ
- `pthread_fchdir_np` は libSystem の非公開 API (中身は `__pthread_fchdir` syscall)。実行時に引き、無ければ使えない
- 副作用は無い。peer の pid は呼び出し元のまま、fd の複製も無く、他のスレッドの cwd は変わらない。そのため `connect` / `connect_nonblocking` も試す

### fork の経路

1. 親がソケットを作り、ディレクトリを開いた fd を持ち、sockaddr を組み立ててから fork する。ブロックしない connect では fork の前にソケットを非ブロッキングにする
2. 子は `fchdir(dirfd)` → ファイル名で `bind` / `connect` → `_exit(結果)` (0 が成功、1〜255 が errno)
3. 親はその pid だけを `waitpid` する。bind の後の listen は必ず親がする。子が listen すると、クライアントに見えるサーバの peer 情報が子になる ([DR-0010](decisions/DR-0010-fork-bind-listen-by-parent.md))

- 子の区間は async-signal-safe な呼び出しだけ (allocation・lock・言語の後始末を通さない)
- `waitpid` が `ECHILD` (status を他者に刈り取られた) なら、ソケットの状態から結果を読む: bind は `getsockname` にパスが入っているか、connect は `getpeername` が通るか。失敗は一般のエラー
- ディレクトリの開き方: Apple の OS は `O_SEARCH` (カーネルが `EISDIR` / `EINVAL` を返したら `O_RDONLY`)、Linux は /proc の経路で開いた `O_PATH` の fd、他は `O_RDONLY`

## 経路の失敗の扱い

- 経路が実際に bind / connect して失敗したら (`ENOENT`、`EADDRINUSE`、`ECONNREFUSED` 等)、そのエラーを返し、次の経路も次の置き場も試さない
- 次へ進むのは、経路自体が使えない時だけ
  - 長さが足りない
  - `/proc` を使えない
  - カーネルが広げた sockaddr を受け付けない
  - 置き場が安全でない・symlink を作れない
  - fd で掴む形 (connect 系だけ) で、ディレクトリを作れない、`fstat` の確認が通らない、`symlinkat` が失敗した
  - 相対パスの経路で、作った綴りのディレクトリが元と `(st_dev, st_ino)` で一致しない、または cwd が既に変わっている
  - スレッド cwd の経路で、seccomp の filter が掛かっている (Linux)、`unshare` が断られた、`pthread_fchdir_np` が無い・失敗した、スレッドを作れない・固定できない
- ディレクトリが無い時はどの OS でも `ENOENT`。ディレクトリを先に開くので、ファイル名の長さの判定より前に決まる
- `connect` / `connect_nonblocking` はディレクトリを開いてから fork の手前で `ENAMETOOLONG` を返す

## どこから届かなくなるか

標準に渡す長さを超えるパスが `ENAMETOOLONG` になる時 (ディレクトリがある前提。数字はバイト)。

| OS | `bind` | `connect` 系 | `connect_any` 系 |
|---|---|---|---|
| Linux (`/proc` あり) | ファイル名 > 107 | ファイル名 > 107、symlink も使えない (置き場の安全は問わない)<br>スレッド cwd が使えない時: ファイル名が `/proc` の綴りに収まらず、相対パス > 107、symlink も使えない (置き場の安全は問わない) | ファイル名 > 107、symlink も使えない (置き場の安全は問わない) |
| Linux (`/proc` 無し) | ファイル名 > 107 | ファイル名 > 107、symlink も使えない<br>スレッド cwd が使えない時: 相対パス > 107、symlink も使えない | ファイル名 > 107、symlink も使えない |
| FreeBSD | ファイル名 > 103 | ファイル名 > 103 | ファイル名 > 103 |
| macOS / iOS 等 Apple の OS | ファイル名 > 103 | ファイル名 > 253、symlink も使えない<br>スレッド cwd が使えない時: 元のパスも相対パスも > 253、symlink も使えない | ファイル名 > 253、symlink も使えない |
| NetBSD / OpenBSD / その他の BSD | ファイル名 > 103 | 相対パス > 103、symlink も使えない | ファイル名 > 103、symlink も使えない |
| illumos | ファイル名 > 107 | 相対パス > 107、symlink も使えない | ファイル名 > 107、symlink も使えない |

- スレッド cwd の経路を使える Linux / Apple の OS では、`connect` 系も `connect_any` 系と同じ所まで届く
- `/tmp` で symlink の経路を使えれば、connect はディレクトリの深さにもファイル名の長さにもよらず届く
- `/proc` を使える Linux では、置き場が安全でなくても、そこにディレクトリを作れれば connect は同じく届く (fd で掴む形)
- `/tmp` を通した bind はファイル名が 84 バイト (`sun_path` が 104 の OS は 80) まで
- ディレクトリを開く等でフルパスを渡すので、PATH_MAX (macOS 1024、Linux 4096) を超えるパスは `ENAMETOOLONG`。sockat の責務外

## fork の副作用

| 範囲 | 副作用 |
|---|---|
| 相手から見える (`connect_any` 系だけ) | サーバに見える peer の pid は終了した子の pid。uid / gid は呼び出し元と同じ<br>Linux の `SO_PEERCRED` は子の pid のまま<br>macOS の `LOCAL_PEERPID` は呼び出し元が send すると呼び出し元の pid になる |
| 相手から見えない (`bind` と `connect_any` 系) | 子は終了まで全 fd の複製を持つ。その間に他のスレッドが閉じたソケットやパイプは開いたままになる<br>親に `SIGCHLD` が届く<br>`pthread_atfork` の handler が走る<br>監視ツールに短命の子が見える<br>他のスレッドの `waitpid(-1)` が子を刈り取りうる |

- bind は相手から見える副作用が無い。子は bind だけして listen は親がするので、クライアントに見えるサーバの peer 情報 (macOS の `LOCAL_PEERPID` / `LOCAL_PEEREPID` / audit token の pid と pidversion、Linux の `SO_PEERCRED` / `SO_PEERPIDFD`) は send の前から親 (実測 2026-11-18、macOS 26.5.2 と Linux) ([DR-0010](decisions/DR-0010-fork-bind-listen-by-parent.md))

## 長いパスで標準と違う点

| 点 | 内容 |
|---|---|
| カーネルが返すアドレス | カーネルの `getsockname` / `getpeername` は bind に使った綴り (相対パス、`/proc/self/fd/...`、もう無い symlink、ファイル名だけ) を返す。標準の型でアドレスを返す口を sockat が差し替えられる言語では、元のパスを返す (上のライブラリがアドレスの綴りで後始末をする。Python の asyncio は listener の `getsockname` の綴りを `stat` / unlink する)。差し替えられない言語は元のパスを呼び出し元が持つ |
| ディレクトリを先に引く | /proc・相対パス・bindat・スレッド cwd・fork は、ディレクトリを引いてからファイル名で渡す。その間の rename や symlink の張り替えは反映されない。広げた sockaddr と symlink は標準と同じ |
| 他のスレッドの chdir | 相対パスの経路は、間に cwd が変わったままなら一般のエラー。変えて戻した場合は見えない |
| symlink の残骸 | symlink や fd で掴む形のディレクトリを消す前にプロセスが死ぬと `sockat.XXXXXXXXXX` が置き場に残る |

- 先頭以外の NUL は短いパスでも引数の誤り。標準が NUL で黙って切り詰める言語 (Go 等) では、README の「標準と違う点」に書く

## エラー

| 状況 | エラー |
|---|---|
| ディレクトリが無い / connect 先が無い | `ENOENT` |
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
- 環境を読む部分 (symlink の置き場の候補、`/proc/self/fd` の場所、Apple の OS で広げた sockaddr を受け付けるか、スレッド cwd の経路を使えるか) は試験から差し替えられるようにする
- README とマニュアルにこの仕様へのリンクを置く。仕様と食い違う振る舞いを入れる時は、先にこの仕様を直す

## 実装が確かめる試験の観点

| 観点 | 確かめること |
|---|---|
| 短いパスの境界 | 標準に渡す長さちょうどは標準にそのまま渡り、1 バイト長いと経路に回る (標準自身で境界を確かめる) |
| 場所 | 各経路で、ソケットファイルが元のパスにでき、置き場に何も残らない |
| 送受信 | 各経路で bind した listener と connect した stream で実際に送受信できる |
| 標準の型 | 戻り値が標準の型として使える (非同期ランタイムに渡せる言語では渡して使う) |
| 失敗をやり直さない | `ENOENT` / `EADDRINUSE` / `ECONNREFUSED` を返し、後の経路・置き場に何も作らない (後の候補のディレクトリの mtime が変わらない) |
| /proc が無い Linux | `/proc/self/fd` の場所を空のディレクトリ等に差し替えて、相対パス → symlink → スレッド cwd → fork に進む |
| symlink の置き場 | 安全でない置き場を飛ばす、深すぎる `TMPDIR` で `/tmp` に回る、名前の衝突を飛ばし 16 回で打ち切る、成功でも失敗でも symlink を消す |
| fd で掴む形 | 安全でない置き場で、ソケットが元のパスにでき届く、終わった後に置き場に何も残らない、作ってから開くまでに差し替えたディレクトリ (持ち主が違うか group / other に権限が付いた) を使わず、その中身も消さない、`TMPDIR` を `/tmp` より先に使う、`/proc` を使えない時は安全でない置き場を飛ばす |
| connect と fork | `connect` 系は fork でしか届かない時に `ENAMETOOLONG`、`connect_any` 系は届いて `forked` が真 |
| cwd | どの経路の後も cwd が変わっていない。相対パスの経路の途中で cwd が変わったら一般のエラー |
| スレッド cwd | 経路を強制して、プロセスの cwd が変わらない、peer の pid が呼び出し元、ソケットが元のパスにできる。使えない時は次の経路へ進む |
| fork | fork の経路で bind したサーバに connect したクライアントから見える peer が親 (send の前も後も)。`connect_any` 系の peer の pid の振る舞い、`SIGCHLD` を `SIG_IGN` にした時の結果の読み取り |
| macOS | connect 系で 253 バイトのパスが広げた sockaddr で通る。bind は広げた sockaddr を使わない |
| ブロックしない connect | backlog が満杯で待たずに失敗する |
| 名前で終わらないパス、先頭以外の NUL | 何も作らずに引数の誤り。NUL は短いパスでも。先頭が NUL (abstract) は標準に渡る |
| カーネルが返すアドレス | 長いパスでも取得で落ちない。差し替えられる言語では、listener・accept したソケット・connect したソケットの各口が元のパスを返し、その言語の代表的な上のライブラリ (Python の asyncio の `start_unix_server(sock=...)` 等) が引数を足さずに短いパスと同じに動く |

- 経路は OS で違うので、少なくとも macOS と Linux で回す。他の Unix は CI の VM で回す
- cwd やシグナルの扱いのようにプロセス全体に効く設定を変える試験は、子プロセスの中で行う
- fork の経路の子は全 fd の複製を一瞬持つので、「誰も listen していないソケット」は別プロセスで作る

## 未確定

- Android と macOS 以外の Apple の OS は全体が未確認
- NetBSD・OpenBSD・illumos は peer の資格情報が未確認
- ブロックしない connect が `EINPROGRESS` を返さないことは Linux と macOS でだけ確認済み
