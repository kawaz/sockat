# fork-cwd: fork した子がディレクトリへ移って bind / connect する手法

> [English](./fork-cwd.md) | 日本語

sockat はこの手法を使わない (kawaz 裁定 2026-11-20)。fork の副作用 (fd の複製、`SIGCHLD`、`waitpid(-1)`、`pthread_atfork`、connect では相手に見える pid) は呼び出したライブラリでなくプロセス全体に及び、それを望まない利用者の方が多いため。この文書は、sockat が届かない場面で利用者が自分のアプリで fork を使う時のために、手法と副作用と、それで届く場面を書く。

- 届く範囲の全体: [reach](reach/README-ja.md) (表の「fork-cwd なら」の列が、この文書の節へのリンク)
- 判断の記録: [DR-0017](../docs/decisions/DR-0017-resolve-through-persistent-base.md) (fork をしない判断、bind の綴りに乱数の名前を挟む理由)、[issue](../docs/issue/2026-11-20-resolve-and-persistent-base.md) の「最終手段と fork」

## 手法

`sun_path` に入らないのはパスの文字列であって、ディレクトリの深さではない。子プロセスの cwd をソケットのディレクトリ (か、それを指す短い名前を持つディレクトリ) に移せば、短い相対の綴りで bind / connect できる。cwd はプロセスに 1 つなので、呼び出し元のプロセスの cwd を変えないよう、fork した子だけを移す。

| 手順 | bind | connect |
|---|---|---|
| 1. 親が用意する | ソケットを作り、sockaddr を組み立てる。自分専用のディレクトリ D を作って fd で掴み、その中にソケットのディレクトリを指す乱数の名前の symlink R を作る | ソケットを作り、sockaddr を組み立てる。ソケットのディレクトリを開いて fd を持つ。ブロックしない connect ならソケットを非ブロッキングにする |
| 2. fork | 同じ | 同じ |
| 3. 子 | `fchdir(Dfd)` → `bind(sock, "R/<ファイル名>")` → `_exit(0 か errno)` | `fchdir(dirfd)` → `connect(sock, "<ファイル名>")` → `_exit(0 か errno)` |
| 4. 親 | その pid だけを `waitpid` し、R と D を片付けてから `listen` する | その pid だけを `waitpid` する |

- 子と親は同じソケットを共有している (fork は fd を複製するが、指すソケットは 1 つ)。子が bind / connect した結果は親のソケットに残る
- bind の listen は必ず親がする。子に listen させると、クライアントから見えるサーバの peer が死んだ子になる (実測 2026-11-18、macOS と Linux。[DR-0017](../docs/decisions/DR-0017-resolve-through-persistent-base.md))
- bind の綴りに R を挟むのは、カーネルが覚えて `getsockname` で返す綴りが cwd からの相対パスになり、後で別の cwd で解決されると同じ名前の無関係なファイルに当たるため ([DR-0017](../docs/decisions/DR-0017-resolve-through-persistent-base.md))。R を片付けた後の綴りはどこにも当たらない。connect の綴りは相手に残らないので R は要らない
- `waitpid` が `ECHILD` (他者に status を刈り取られた) なら、ソケットの状態から結果を読む: bind は `getsockname` にパスが入っているか、connect は `getpeername` が通るか

届くファイル名 (バイト):

| | Linux / Android / illumos | Apple の OS | BSD |
|---|---|---|---|
| bind (`R/<ファイル名>`) | 96 | 92 | 92 |
| connect (`<ファイル名>`) | 107 | 253 (子で広げた sockaddr を使う時。カーネルが受け付けなければ 103) | 103 |

## 副作用

| 範囲 | 副作用 |
|---|---|
| 相手から見える (connect だけ) | サーバに見える peer の pid は、もう終わった子の pid。uid / gid は呼び出し元と同じ<br>Linux の `SO_PEERCRED` は子の pid のまま<br>macOS の `LOCAL_PEERPID` は呼び出し元が send すると呼び出し元の pid になる |
| 相手から見えない (bind と connect) | 子は終わるまで全 fd の複製を持つ。その間に他のスレッドが閉じたソケットやパイプは開いたままで、相手に EOF が届くのが遅れる<br>親に `SIGCHLD` が届く<br>`pthread_atfork` の handler が走る<br>監視ツール (プロセスの一覧、audit) に短命の子が見える<br>他のスレッドの `waitpid(-1)` や `SIGCHLD` の handler が子を刈り取り、結果を取り違えうる |
| 大きいプロセス | fork はページテーブルを複製するので、仮想メモリの大きいプロセスほど時間が掛かる (未計測)<br>Linux の `vm.overcommit_memory=2` (厳格) では、子の分の commit を確保できずに fork が `ENOMEM` で失敗しうる。既定の `0` でも、使っているメモリが大きいと断られうる (未検証) |

- bind は相手から見える副作用が無い。子は bind だけして listen は親がするので、クライアントに見えるサーバの peer 情報 (macOS の `LOCAL_PEERPID` / `LOCAL_PEEREPID` / audit token、Linux の `SO_PEERCRED` / `SO_PEERPIDFD`) は send の前から親 (実測 2026-11-18、[DR-0017](../docs/decisions/DR-0017-resolve-through-persistent-base.md))
- connect の peer の pid が子になるので、相手のサーバが peer の pid で認可や記録をしているなら、fork した connect は使えない

## 自分のアプリで行う時の注意

- 子の区間は async-signal-safe な呼び出しだけにする。`fchdir`・`bind`・`connect`・`_exit` は async-signal-safe (Linux の signal-safety(7)。`fchdir` は POSIX.1-2008 TC1 で加わった)。allocation・lock・printf・言語の後始末 (`exit`、デストラクタ、例外) を通さない。多スレッドのプロセスでは、他のスレッドが掴んでいた lock が子で解けないまま残るため
- sockaddr とパスの文字列は fork の前に作っておく
- 親は fork した pid を指定して `waitpid` する (`EINTR` はやり直す)。他のスレッドで `waitpid(-1)` を使わない
- `SIGCHLD` を `SIG_IGN` にしているプログラムでは子が自動で刈り取られ、`waitpid` が `ECHILD` になる。上の「ソケットの状態から結果を読む」で扱う
- ブロックしない connect は fork の前にソケットを非ブロッキングにする。`EINPROGRESS` は子の終了コードで親に伝わる

言語ごとの現実性:

| 言語 | 現実性 | 理由 |
|---|---|---|
| C / C++ | できる | `fork` と上の手順をそのまま書ける |
| Rust | できる (`unsafe`) | `libc::fork` を使い、子では allocation も panic もしない (std の `Command` は fork + exec しかしない)。sockat-rs は fork の経路を作っていない |
| Python | 難しい | `os.fork()` の子はインタプリタのまま動き続け、バイトコードの実行・参照カウント・allocation を避けられない (async-signal-safe な区間にできない)。CPython は多スレッドのプロセスでの `os.fork()` に `DeprecationWarning` を出す (3.15.2 で実測)。確実にするなら、fork から `_exit` までを C の拡張で書く。sockat-py は fork の経路を作っていない |
| Go | できない (fork だけでは) | runtime が多スレッドで、`syscall.ForkExec` は fork の直後に exec する形しか持たない。生の fork の子では runtime が動かない (sockat-go のリファレンスの「SPEC から外れる経路」)。代わりに、cwd をソケットのディレクトリにして小さな補助のプログラムを起動し (`os/exec` の `Cmd.Dir`)、ソケットの fd を渡して (`ExtraFiles`) 補助のプログラムにファイル名で bind / connect させる形はありうる (fork + exec なので費用はさらに大きい。未検証) |

## fork-cwd なら届く場面

[届く範囲の表](reach/README-ja.md) で「fork-cwd なら」の列にリンクがある所。数字はバイトで、表と同じ見積もり (置き場の長さは代表値)。

### bind-linux-without-thread-cwd

Linux / Android で、スレッドの cwd を使えない bind。

| 項目 | 中身 |
|---|---|
| 条件 | 既定の bind・bind_ex: seccomp の filter が掛かっている (docker や systemd の `SystemCallFilter=` の既定)、`unshare(CLONE_FS)` が断られる、スレッドを作れない<br>resolve_for_bind: スレッドの cwd によらない (thread-cwd を持たない)<br>どれも、ファイル名が link-dir の綴りに収まらない時 |
| sockat で届く所 | 既定の bind・bind_ex・resolve_for_bind で同じ。link-dir でファイル名が次まで (procB と B の実パスを順に試すので、使える方の長い方)<br>procB (`/proc` を使え、`usable_cross_uid` でない時): 73<br>B の実パス: `/tmp` の B 76、`$XDG_RUNTIME_DIR` の B 71、`$TMPDIR` が `/var/tmp` の B 72、`Options.base` が `/tmp/app-<uid>/sockat` の B 72<br>B の綴りが収まらない (`$TMPDIR` や `Options.base` が深い所) か、B がソケットのディレクトリになり `/proc` も使えない時は届かない |
| fork で届く所 | ファイル名 96 まで (置き場によらない。D はソケットのディレクトリにも作れる) |
| 固有の副作用 | 相手から見える副作用は無い (listen は親)。seccomp の filter が `fork` / `clone` を断る環境では fork-cwd も使えない |

### bind-apple-without-thread-cwd

macOS と他の Apple の OS で、スレッドの cwd を使えず (`pthread_fchdir_np` が無いか失敗する)、link-file でも届かない bind。

| 項目 | 中身 |
|---|---|
| 条件 | 既定の bind・bind_ex: `pthread_fchdir_np` が無い・失敗する。resolve_for_bind: スレッドの cwd によらない<br>加えて、link-file を使えない: B を作れる所が無いか B の綴りが収まらない (`/tmp` に書けず `$TMPDIR` が未設定・深い所、`Options.base` が深い所、`usable_cross_uid` で `/tmp` に書けない)、または他の Apple の OS で bind が symlink を辿らない (resolve_for_bind は他の Apple の OS では link-file を使わない)<br>加えて、ファイル名が link-dir の綴りに収まらない |
| sockat で届く所 | link-file: B の綴りが収まれば、ファイル名の長さによらず届く (macOS と、bind が symlink を辿る他の Apple の OS)<br>link-dir (B の実パス): ファイル名が `/tmp` の B で 64、`$TMPDIR` の既定の B で 20、`Options.base` が `/tmp/app-<uid>/sockat` の B で 68 まで<br>B を作れる所が無いか B の綴りが収まらない時は届かない |
| fork で届く所 | ファイル名 92 まで |
| 固有の副作用 | 相手から見える副作用は無い (listen は親)。子で Objective-C や CoreFoundation を呼ばない (fork の後に exec しない子でそれらを使うのは安全でない、未検証) |

### bind-without-thread-cwd-means

FreeBSD 以外の BSD、illumos、その他の Unix (と FreeBSD の resolve_for_bind) で、スレッドの cwd も `bindat` も使えない bind。

| 項目 | 中身 |
|---|---|
| 条件 | NetBSD・bind が symlink を辿るその他の Unix: B を作れる所が無いか B の綴りが収まらない時 (resolve_for_bind のその他の Unix は辿るかを見分けられず link-file を使わない)<br>OpenBSD・illumos・辿らないその他の Unix・FreeBSD の resolve_for_bind: ファイル名が link-dir の綴りに収まらない時 |
| sockat で届く所 | link-file (NetBSD と辿るその他の Unix の既定の bind・bind_ex、NetBSD の resolve_for_bind): B の綴りが収まれば、ファイル名の長さによらず届く<br>link-dir (B の実パス): ファイル名が `/tmp` の B で 72 (illumos は 76)、`$TMPDIR` が `/var/tmp` の B と `Options.base` が `/tmp/app-<uid>/sockat` の B で 68 (illumos は 72) まで<br>B を作れる所が無いか B の綴りが収まらない時は届かない |
| fork で届く所 | ファイル名 92 (illumos は 96) まで |
| 固有の副作用 | 相手から見える副作用は無い (listen は親) |

- FreeBSD の既定の bind・bind_ex は at でファイル名 92 まで届き、fork-cwd も 92 までなので、fork で延びる所が無い

### connect-without-place-or-thread-cwd

書き込みもスレッドも要らない経路で届かず、thread-cwd-direct でも届かず、link-file の `B/E` を作れない既定の connect。sandbox の中で短命の CLI が connect する場面に当たりやすい。

| 項目 | 中身 |
|---|---|
| 条件 | 次が全部そろう<br>書き込みもスレッドも要らない経路で届かない: `/proc` を使える Linux はファイル名が 90 を超え、他は元のパスと相対パスの短い方が sockaddr に入らない (Apple の OS の rs・py は 253 を超える)<br>thread-cwd-direct で届かない: スレッドの cwd を使えない (NetBSD・OpenBSD・illumos・その他の Unix はいつも) か、ファイル名が sockaddr に入らない<br>link-file で届かない: `/tmp`・`$XDG_RUNTIME_DIR`・`$TMPDIR` のどこにも B を作れないか、作れた B の `B/E` が sockaddr に入らない (`$TMPDIR` が深い所)。B がソケットのディレクトリになると `B/E` は元のパスより長い |
| sockat で届く所 | proc-direct (`/proc` を使える Linux): ファイル名 90 まで<br>relative: 相対パス 107 (Linux / illumos)、103 (他) まで。Apple の OS の rs・py は widened で 253 まで (Go は widened を作れない)<br>thread-cwd-direct (Linux / Android・Apple の OS): ファイル名 107 / 103 まで<br>link-file: B を作れて `B/E` が収まれば、ファイル名の長さによらず届く |
| fork で届く所 | ファイル名 107 (Linux / illumos)、103 (BSD・その他)、253 (Apple の OS、子で広げた sockaddr を使う時) まで |
| 固有の副作用 | 相手のサーバに見える peer の pid が、もう終わった子の pid になる。peer の pid で認可や記録をするサーバには使えない |

- FreeBSD は at-direct でファイル名 103 まで届き、fork-cwd も 103 までなので、fork で延びる所が無い
