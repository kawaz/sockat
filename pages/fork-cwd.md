# fork-cwd: fork した子がディレクトリへ移って bind / connect する手法

sockat はこの手法を使わない (kawaz 裁定 2026-11-20)。fork の副作用 (fd の複製、`SIGCHLD`、`waitpid(-1)`、`pthread_atfork`、connect では相手に見える pid) は呼び出したライブラリでなくプロセス全体に及び、それを望まない利用者の方が多いため。この文書は、sockat が届かない場面で利用者が自分のアプリで fork を使う時のために、手法と副作用と、それで届く場面を書く。

- 届く範囲の全体: [reach](reach/README.md) (表の「fork-cwd なら」の列が、この文書の節へのリンク)
- 判断の記録: [DR-0010](../docs/decisions/DR-0010-fork-bind-listen-by-parent.md) (listen は親)、[DR-0012](../docs/decisions/DR-0012-own-directory-and-thread-cwd.md) (D と R)、[issue](../docs/issue/2026-11-20-resolve-and-persistent-base.md) の「最終手段と fork」

## 手法

`sun_path` に入らないのはパスの文字列であって、ディレクトリの深さではない。子プロセスの cwd をソケットのディレクトリ (か、それを指す短い名前を持つディレクトリ) に移せば、短い相対の綴りで bind / connect できる。cwd はプロセスに 1 つなので、呼び出し元のプロセスの cwd を変えないよう、fork した子だけを移す。

| 手順 | bind | connect |
|---|---|---|
| 1. 親が用意する | ソケットを作り、sockaddr を組み立てる。自分専用のディレクトリ D を作って fd で掴み、その中にソケットのディレクトリを指す乱数の名前の symlink R を作る | ソケットを作り、sockaddr を組み立てる。ソケットのディレクトリを開いて fd を持つ。ブロックしない connect ならソケットを非ブロッキングにする |
| 2. fork | 同じ | 同じ |
| 3. 子 | `fchdir(Dfd)` → `bind(sock, "R/<ファイル名>")` → `_exit(0 か errno)` | `fchdir(dirfd)` → `connect(sock, "<ファイル名>")` → `_exit(0 か errno)` |
| 4. 親 | その pid だけを `waitpid` し、R と D を片付けてから `listen` する | その pid だけを `waitpid` する |

- 子と親は同じソケットを共有している (fork は fd を複製するが、指すソケットは 1 つ)。子が bind / connect した結果は親のソケットに残る
- bind の listen は必ず親がする。子に listen させると、クライアントから見えるサーバの peer が死んだ子になる (実測 2026-11-18、macOS と Linux。[DR-0010](../docs/decisions/DR-0010-fork-bind-listen-by-parent.md))
- bind の綴りに R を挟むのは、カーネルが覚えて `getsockname` で返す綴りが cwd からの相対パスになり、後で別の cwd で解決されると同じ名前の無関係なファイルに当たるため ([DR-0012](../docs/decisions/DR-0012-own-directory-and-thread-cwd.md))。R を片付けた後の綴りはどこにも当たらない。connect の綴りは相手に残らないので R は要らない
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

- bind は相手から見える副作用が無い。子は bind だけして listen は親がするので、クライアントに見えるサーバの peer 情報 (macOS の `LOCAL_PEERPID` / `LOCAL_PEEREPID` / audit token、Linux の `SO_PEERCRED` / `SO_PEERPIDFD`) は send の前から親 (実測 2026-11-18、[DR-0010](../docs/decisions/DR-0010-fork-bind-listen-by-parent.md))
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
| Rust | できる (`unsafe`) | `libc::fork` を使い、子では allocation も panic もしない (std の `Command` は fork + exec しかしない)。sockat-rs の今の版はこの手順を実装している (適合試験の `no-thread-cwd-no-proc-bind` で rs だけ fork-cwd を通る。実測 2026-11-20) |
| Python | 難しい | `os.fork()` の子はインタプリタのまま動き続け、バイトコードの実行・参照カウント・allocation を避けられない (async-signal-safe な区間にできない)。CPython は多スレッドのプロセスでの `os.fork()` に `DeprecationWarning` を出す (3.15.2 で実測)。確実にするなら、fork から `_exit` までを C の拡張で書く。sockat-py は fork の経路を作っていない |
| Go | できない (fork だけでは) | runtime が多スレッドで、`syscall.ForkExec` は fork の直後に exec する形しか持たない。生の fork の子では runtime が動かない (sockat-go の README の「SPEC から外れる経路」)。代わりに、cwd をソケットのディレクトリにして小さな補助のプログラムを起動し (`os/exec` の `Cmd.Dir`)、ソケットの fd を渡して (`ExtraFiles`) 補助のプログラムにファイル名で bind / connect させる形はありうる (fork + exec なので費用はさらに大きい。未検証) |

## fork-cwd なら届く場面

[届く範囲の表](reach/README.md) で「fork-cwd なら」の列にリンクがある所。数字はバイトで、表と同じ見積もり (置き場の長さは代表値)。

### bind-linux-without-thread-cwd

Linux / Android で、スレッドの cwd を使えない bind。

| 項目 | 中身 |
|---|---|
| 条件 | seccomp の filter が掛かっている (docker や systemd の `SystemCallFilter=` の既定)、`unshare(CLONE_FS)` が断られる、スレッドを作れない |
| sockat で届く所 | 既定の bind: `/proc` を使えれば proc でファイル名 79 まで、使えなければ届かない<br>bind_ex: procB の link-dir で 74 まで。`/proc` を使えない時は、置き場に書ければ link-dir で 71 まで (`$XDG_RUNTIME_DIR` の dirB で 61、`/tmp` の tmpB で 71)<br>resolve_for_bind: bind_ex と同じ |
| fork で届く所 | ファイル名 96 まで (置き場によらない。D はソケットのディレクトリにも作れる) |
| 固有の副作用 | 相手から見える副作用は無い (listen は親)。seccomp の filter が `fork` / `clone` を断る環境では fork-cwd も使えない |

### bind-apple-without-thread-cwd

macOS と他の Apple の OS で、スレッドの cwd を使えず (`pthread_fchdir_np` が無いか失敗する)、置き場の symlink も使えない bind。

| 項目 | 中身 |
|---|---|
| 条件 | `pthread_fchdir_np` が無い・失敗する。加えて、`$TMPDIR` と `/tmp` のどちらも書けないか、綴りが収まらないほど長い。他の Apple の OS で bind が symlink を辿らない時は、置き場によらずここに入る |
| sockat で届く所 | 既定の bind: symlink-file で、置き場があればファイル名の長さによらず届く<br>bind_ex: link-file (dirB・tmpB) で、置き場があればファイル名の長さによらず届く<br>置き場が無いと、どちらも届かない |
| fork で届く所 | ファイル名 92 まで |
| 固有の副作用 | 相手から見える副作用は無い (listen は親)。子で Objective-C や CoreFoundation を呼ばない (fork の後に exec しない子でそれらを使うのは安全でない、未検証) |

### bind-without-thread-cwd-means

FreeBSD 以外の BSD、illumos、その他の Unix で、スレッドの cwd も `bindat` も `/proc` も使えない bind。

| 項目 | 中身 |
|---|---|
| 条件 | NetBSD・その他の Unix で bind が symlink を辿る OS: 置き場が無い時<br>OpenBSD・illumos・辿らないその他の Unix: いつも (bind が symlink を辿らず、手段が無い) |
| sockat で届く所 | 既定の bind: NetBSD は symlink-file で置き場があれば長さによらず届く。OpenBSD・illumos は届かない<br>bind_ex / resolve_for_bind: NetBSD は link-file で置き場があれば届く。OpenBSD は tmpB の link-dir でファイル名 67、illumos は 71 まで (`/tmp` に書ける時) |
| fork で届く所 | ファイル名 92 (illumos は 96) まで |
| 固有の副作用 | 相手から見える副作用は無い (listen は親) |

- FreeBSD は `bindat` (at) でファイル名 92 まで届き、fork-cwd も 92 までなので、fork で延びる所が無い

### connect-without-place-or-thread-cwd

書き込みもスレッドも要らない経路で届かず、スレッドの cwd も使えず (かファイル名が長すぎ)、link-file の置き場も無い connect。sandbox の中で短命の CLI が connect する場面に当たりやすい。

| 項目 | 中身 |
|---|---|
| 条件 | 次が全部そろう<br>`/proc` を使える Linux はファイル名が 90 を超え、他の OS は元のパスも相対パスも sockaddr (Apple の OS は広げた sockaddr) に入らない<br>スレッドの cwd を使えない (FreeBSD・NetBSD・OpenBSD・illumos・その他の Unix はいつも)<br>`$XDG_RUNTIME_DIR`・`$TMPDIR`・`/tmp` に B を作れず、`/proc` を使える Linux ではソケットのディレクトリにも書けない |
| sockat で届く所 | Linux (`/proc` あり): proc-direct でファイル名 90 まで<br>他: relative で相対パス 107 / 103 まで、Apple の OS は widened で 253 まで (Go は widened を作れない) |
| fork で届く所 | ファイル名 107 (Linux / illumos)、103 (BSD・その他)、253 (Apple の OS、子で広げた sockaddr を使う時) まで |
| 固有の副作用 | 相手のサーバに見える peer の pid が、もう終わった子の pid になる。peer の pid で認可や記録をするサーバには使えない |
