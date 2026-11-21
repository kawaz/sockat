# TypeScript 版 (sockat-ts) の実現性: Bun と Node の標準の上限、経路ごとの部品、native の持ち方

- Date: 2026-11-21
- Status: Concluded (この回の調査。決定は sockat-ts の DR と kawaz の裁定で行う)

## 動機

- [issue](../issue/2026-11-21-typescript-port.md): claude-ccmsg (Bun) の webui の試験と daemon が、macOS の深い一時ディレクトリで sun_path を超えて起動できない。TypeScript (Bun / Node) から長いパスで bind / connect したい
- 決める前に知りたいこと
  - runtime ごとの標準の上限と、超えた時の振る舞い (切り詰めの報告の真偽を含む)
  - SPEC の経路ごとに要る部品と、それが JS だけで作れるか、FFI か native addon が要るか
  - FFI で作った fd を標準の型に取り込めるか
  - 1 つの npm package で Bun と Node を両方扱えるか

## 調査範囲

- 対象: Bun と Node の stream (bind / listen / connect)。Linux と macOS
- Deno は要点だけ (標準の上限、FFI の fd を取り込む口の有無)
- 扱わない: FreeBSD・NetBSD 等の実機 (手元に無い)、npm の公開手順、DGRAM と SEQPACKET (Node と Bun の標準に Unix の DGRAM が無いことだけ確かめた)
- 「確認済み」は下の環境の実測かソースの該当行で確かめたもの。「未検証」は確かめていないもの (理由を書く)

## 環境

| 項目 | 値 |
|---|---|
| macOS | Darwin 25.5.0 arm64 |
| Linux | docker (OrbStack) の Linux 7.2 aarch64。イメージは `node:26-slim` (Node 26.13.1、libuv 1.52.1)、`node:24-slim` (24.22.3、libuv 1.52.1)、`node:22-slim` (22.23.5、libuv 1.51.0)、`oven/bun:1.4.4` (Debian、glibc)、`oven/bun:1.4.4-alpine` (musl)。相手の確かめに python3 を足したもの |
| macOS の Node | 26.13.1 (Homebrew。共有ライブラリの libuv 1.53.0 を使う。`otool -L` で `/opt/homebrew/opt/libuv/lib/libuv.1.dylib`) |
| macOS の Bun | 1.4.4 |
| Deno | 2.9.8 (macOS だけ) |

実験物は `$W` (`mktemp -d` で `$TMPDIR` の下) に置いた。短い絶対パスが要る試験は試験用の別名のディレクトリ `$S` (`mktemp -d /tmp/sockat-ts-probe.XXXXXX`) を使い、`/tmp/sockat-<uid>` には触っていない。

## 調査メモ

### 1. 標準の上限と、超えた時の振る舞い

#### 1-1. 長さの境界

プローブ (`probe-net.mjs`): 長さ L ちょうどのパスを作り (200 バイトを超える分は 100 バイトのディレクトリを挟む)、`net.createServer().listen(p)` → ディレクトリに増えた物の名前の長さ → `net.connect(p)` で往復。`probe-bun.mjs` は同じことを `Bun.listen({unix})` / `Bun.connect({unix})` で行う。

```text
$ node probe-net.mjs $S 103 104 105 106 150 253 254 255 256 300      # macOS、Homebrew の Node 26.13.1 (libuv 1.53.0)
len=103 ... listen=ok ... newEntries=["SAME"] connect=ok:pong
len=104 ... listen=ok ... newEntries=["SAME"] connect=ok:pong
len=150 ... listen=ok ... newEntries=["SAME"] connect=ok:pong
len=253 ... listen=ok ... newEntries=["SAME"] connect=ok:pong
len=254 bytes=254 listen=ERR(EINVAL)
len=300 bytes=300 listen=ERR(EINVAL)

$ docker run node:26-slim ... node probe-net.mjs /tmp/b 106 107 108 109 150 253 300   # Linux、Node 26.13.1 (24.22.3 も同じ)
len=107 ... listen=ok ... newEntries=["SAME"] connect=ok:pong
len=108 ... listen=ok ... newEntries=["SAME"] connect=ok:pong
len=109 bytes=109 listen=ERR(EINVAL)
len=300 bytes=300 listen=ERR(EINVAL)

$ docker run node:22-slim ... node probe-net.mjs /tmp/b 106 107 108 109 150 253 300   # Linux、Node 22.23.5
len=108 ... listen=ok addrLen=108 exists=true newEntries=["SAME"] connect=ok:pong
len=109 ... listen=ok addrLen=109 exists=false newEntries=["len108"] connect=ok:pong
len=150 ... listen=ok addrLen=150 exists=false newEntries=["len108"] connect=ok:pong
len=253 bytes=253 listen=ERR(EADDRINUSE)
```

Node 22 の 253 の `EADDRINUSE` は、108 バイトに切った先が既にあるディレクトリ (`/tmp/b/d0ddd…/`) に当たったため。

```text
$ bun probe-bun.mjs $S 103 ... 130 131 ...        # macOS、Bun.listen (base は 27 バイト)
len=130 listen=ok unix.len=130 exists=true newEntries=["SAME"] connect=ok:pong
len=131 listen=ERR(EINVAL)
$ bun probe-bun.mjs $W/lb 120 129 130 131 140     # base を 83 バイトにすると
len=140 listen=ok unix.len=140 exists=true newEntries=["SAME"] connect=ok:pong

$ docker run oven/bun:1.4.4 ... bun probe-bun.mjs /tmp/b 107 108 109 150 300   # Linux
len=107 listen=ok ...
len=108 listen=ERR(EINVAL)
```

Bun の境界はパス全体の長さでなくファイル名の長さで変わる (下の 1-2)。node:net を Bun で動かしても同じ境界。

```text
$ deno run -A t-deno.ts $S      # macOS、Deno 2.9.8
Deno.listen len=103  (listen は通った。後始末の remove の ENOENT は close が消していたため)
Deno.listen len=104 ERR path must be shorter than SUN_LEN
```

| runtime | OS | 標準にそのまま通る長さ | 超えた時 |
|---|---|---|---|
| Node 26.13.1 / 24.22.3 (libuv 1.52.1) | Linux | 108 (`sun_path` の全部。NUL なし) | `EINVAL` |
| Node 22.23.5 (libuv 1.51.0) | Linux | 108 | **108 バイトに黙って切り詰めて成功を返す**。connect も同じに切るので、切った先に届いてしまう |
| Node 26.13.1 + libuv 1.53.0 (Homebrew) | macOS | 253 (104〜253 は広げた sockaddr) | `EINVAL` |
| Node 26.13.1 (公式バイナリ、libuv 1.52.1 同梱) | macOS | 未検証 (ソースからの見込みは 104、下) | 未検証 |
| Bun 1.4.4 | Linux | 107。それを超えると Bun 自身の迂回 (1-2) で、ファイル名がおよそ 91 まで | `EINVAL` (Bun の C は `ENAMETOOLONG` を立てるが JS には `EINVAL` で届く) |
| Bun 1.4.4 | macOS | 103。それを超えると Bun 自身の迂回で、ファイル名が 102 まで | `EINVAL` |
| Deno 2.9.8 | macOS | 103 | `path must be shorter than SUN_LEN` |

ソースの裏付け:

- Node が切り詰めるかは Node 側の呼び方で決まる。`src/pipe_wrap.cc` の `uv_pipe_bind2` / `uv_pipe_connect2` の flags が v22.23.5 は `0`、v24.22.3 と v26.13.1 は `UV_PIPE_NO_TRUNCATE`。libuv の `uv_pipe_bind2` は flags が 0 なら「Truncate long paths. Documented behavior.」で `sun_path` の長さに切る (1.51.0 も 1.52.1 も同じ)。[agenthook#439](https://github.com/Jesuso/agenthook/issues/439) の Linux の Node 22 の切り詰めの報告は事実
- macOS の 253 は libuv 1.53.0 (2026-09-24、ChangeLog「unix: support long path names in pipe.c」) の `union uv__sockaddr_un` が `SOCK_MAXADDRLEN` (macOS は 255) まで広げたため (FreeBSD は除外されている)。libuv 1.52.1 の `pipe.c` は `struct sockaddr_un` (macOS の `sun_path` は 104) で、`namelen > sizeof(sun_path)` を `EINVAL` にする。公式の Node 26.13.1 は Linux の docker で libuv 1.52.1 を同梱していたので、公式の macOS バイナリは 104 までの見込み (未検証: 公式バイナリを取ってきて実行する操作が auto mode の classifier に止められたため。確かめ方は「未検証のこと」)
- 前の調査 ([2026-11-18](2026-11-18-ports-to-other-languages.md)) の「Node 26.13.1 は macOS で 253 まで」は Homebrew の libuv 1.53.0 の結果で、Node の版でなく libuv の版で決まる。同じく「Bun は 160 成功、210 で EINVAL」はファイル名の長さで境界が動いた結果と読める

#### 1-2. Bun は長いパスを自分で迂回する (カーネルが覚える綴りが変わる)

`packages/bun-usockets/src/bsd.c` (tag `bun-v1.4.4`) の `bsd_create_unix_socket_address`:

- Linux: パスが `sun_path` に入らなければ、親ディレクトリを `O_PATH | O_DIRECTORY` で開き、`/proc/self/fd/<fd>/<basename>` で bind / connect して fd を閉じる
- macOS: 親ディレクトリを `O_RDONLY | O_DIRECTORY` で開き、呼び出したスレッドで `__pthread_fchdir(fd)` → basename で bind / connect → `__pthread_fchdir(-1)` で戻す
- どちらも、親ディレクトリを開けない時も `ENAMETOOLONG` にする (無いディレクトリでも `ENOENT` にならない)

実測でカーネルが覚えた綴り:

```text
# macOS: 深いディレクトリ + 20 バイトのファイル名に Bun.listen、lsof -U で自分の fd を見る
total=300 file=20 Bun.listen=ok exists=true cwdSame=true lsof=["fffffffffffffff.sock", ...]
total=300 file=102 Bun.listen=ok ...
total=300 file=103 ERR(EINVAL)

# Linux: /proc/net/unix
total=200 file=20 bun: listen=ok ... kernel=["/proc/self/fd/5/fffffffffffffff.sock"] connect=ok:pong
total=300 file=100 bun: ERR(EINVAL)

# CPython の相手 (os.chdir してファイル名で connect) から見た getpeername
bun darwin [bun]  path=197: python getpeername -> 'zzzzzzzzzzzzzzzzzzzz.sock' len 25
bun linux  [bun]  path=197: python getpeername -> '/proc/self/fd/5/zzzzzzzzzzzzzzzzzzzz.sock' len 41
node darwin [node] path=197: python getpeername -> 'ppppppppppppppppppppp\x0bo\x01' len 107
```

- Bun の長いパスの bind の綴りは、DR-0017 が bind に使わないと決めた 2 つの形 (ファイル名だけ、`/proc/self/fd/<閉じた fd>/…`) そのもの
- Node の macOS の 104〜253 の bind は広げた sockaddr で、CPython の相手には途中で切れて後ろに無関係なバイトが付いた綴りが見える (DR-0017 の Context と同じ壊れ方)

#### 1-3. close / stop で何を消すか

`stop-unlink.mjs`: 長いパスと短いパスに listen した後、閉じた dirfd の番号を別のディレクトリ (`decoy`) で使い回させ、そこと cwd に同じ名前の無関係なファイルを置いてから close / stop する。

```text
macOS  bun long : after close: socketExists=false decoyFile=true cwdFile=true
macOS  node long: after close: socketExists=false decoyFile=true cwdFile=true
Linux  bun long : kernel=/proc/self/fd/5/victim.sock decoyFds=5,7,8 ... after close: socketExists=false decoyFile=true cwdFile=true
Linux  node short: after close: socketExists=false decoyFile=true cwdFile=true
```

- Node も Bun も、閉じる時は渡されたパスの文字列で unlink し、カーネルの綴りは使わない (fd 5 を使い回させても無関係なファイルは消えない)
- JS の口 (`server.address()`、`Bun.listen().unix`) も渡したパスを返す。カーネルの綴りが見えるのは、別の言語の相手の `getpeername`、運用の道具 (`ss`・`lsof`・`/proc/net/unix`) だけ
- 閉じる時の unlink は渡した綴りで行う: link-file の綴り (`G` → 未作成のファイル) に Node で listen して閉じると `G` (E) が消えソケットのファイルは残った (`afterClose G=false target=true`)。link-dir の綴りなら E を辿って元のパスの実体が消える。止める口 (Go の `SetUnlinkOnClose(false)` に当たるもの) は Node にも Bun にも見当たらない (`server.listen` の options に無い)
- 自前のソケットの fd を `listen({fd})` で取り込んだ listener は、閉じてもファイルを消さない (`fileAfterClose=true`、2-5)

#### 1-4. エラーの errno

```text
# 無いディレクトリの下 (短いパスと、150 バイトの長いパス)
bun  darwin: listen short=ENOENT listen long=EINVAL connect short=ENOENT connect long=EINVAL
node darwin: listen short=EACCES listen long=EACCES connect short=ENOENT connect long=ENOENT
bun  linux : listen short=ENOENT listen long=EINVAL connect short=ENOENT connect long=EINVAL
node linux : listen short=EACCES listen long=EINVAL connect short=ENOENT connect long=EINVAL
```

Node の listen が `EACCES` を返すのは libuv の `uv_pipe_bind2` の「Convert ENOENT to EACCES for compatibility with Windows.」(1.52.1 の `pipe.c` 133〜135 行)。SPEC の「ディレクトリが無い時は `ENOENT`」と、短いパスでの Node の標準の errno が違う。

#### 1-5. DGRAM

```text
node: dgram.createSocket("unix_dgram") -> ERR_SOCKET_BAD_TYPE Valid types are: udp4, udp6
bun : 同じ。Bun.udpSocket は UDP
```

Node と Bun の標準に Unix の DGRAM / SEQPACKET は無い。sockat-ts で写す標準は stream だけになる (確認済み)。

### 2. 経路の部品

#### 2-1. ディレクトリの fd と fs の操作

`t-fsparts.mjs` (Linux は uid 1000 で実行):

```text
bun 1.4.4 darwin / node v26.13.1 darwin:
  open(dir,'r')=fd4 cloexec=1
  open(0111 dir,'r')=EACCES
  open(0111 dir,O_SEARCH)=fd5 cloexec=1 fstat.isDir=true          # 数値の 0x40100000 を渡す
  fstat/lstat bigint dev+ino same=true
  /dev/fd/4/ traversable=ENOTDIR
  mkdir via /dev/fd: ENOENT
  ffi socket cloexec=0
bun 1.4.4 linux / node v26.13.1 linux:
  open(dir,'r')=fd5 cloexec=1
  open(0111 dir,O_PATH|O_DIRECTORY)=fd6 cloexec=1 fstat.isDir=true  # O_PATH は fs.constants に無いので数値 0o10000000
  /proc/self/fd mkdir+chmod+symlink: D1 mode=711 E->/tmp
  /proc/self/status Seccomp: 2
  ffi socket cloexec=1                                              # SOCK_CLOEXEC を付けて作った
```

- `fs.openSync(dir, 'r')` でディレクトリを開ける (close-on-exec 付き)。`O_PATH` / `O_SEARCH` は `fs.constants` に無いが、数値で渡せば開ける (Node・Bun とも)
- `(st_dev, st_ino)` は `{ bigint: true }` で fd と名前の両方から取れる。mkdir / chmod / symlink / lstat / readlink / rename / unlink / realpath は fs にある。`process.geteuid()` もある
- fs に `*at` 系 (`mkdirat`・`fchmodat`・`symlinkat`・`openat`) は無い。Linux は `/proc/self/fd/<fd>/<名前>` に fs の操作を向ければ同じことができる。macOS は `/dev/fd/N/` を辿れないので代わりが無く、確かめ済みの実パスで操作するか FFI が要る
- seccomp の filter の有無は Linux なら `/proc/self/status` の `Seccomp:` で JS だけで分かる (`prctl(PR_GET_SECCOMP)` の代わり)
- macOS で FFI の `socket()` は close-on-exec が付かない (`fcntl` で後から付ける。`SO_NOSIGPIPE` も同様に要る見込み)

#### 2-2. 綴りを標準に渡すだけの経路

`t-routes.mjs` / `t-relative.mjs`:

```text
node v26.13.1 linux [node:net] link-dir bind(65)=ok exists=true | via E connect=ok:re:hi | proc-direct connect(62)=ok:re:hi | procB connect(62)=ok:re:hi | link-file connect=ok:re:hi | ... | link-file bind=ERR EADDRINUSE
node v26.13.1 darwin [node:net] link-dir bind(86)=ok exists=true | via E connect=ok:re:hi | link-file connect=ok:re:hi | afterClose exists=false | link-file bind=ok targetExists=true G.isSymlink=true | afterClose G=false target=true
bun 1.4.4 darwin [node:net] ... link-file bind=ok targetExists=true G.isSymlink=true
bun 1.4.4 darwin [bun]      ... link-file bind=ERR EADDRINUSE
node v26.13.1 darwin: listen(relative 45)=ok | connect down(78 'rrrrrrrrrrrr…')=ok:re:hi | connect up(81 '../rrrrrrrrr…')=ok:re:hi
node v26.13.1 linux : listen(relative 45)=ok | connect down(107 …)=ok:re:hi | connect up(110 '../rrrrrrrrr…')=ERR EINVAL
bun 1.4.4 linux     : ... connect up(110 '../rrrrrrrrr…')=ok:re:hi   # 107 を超えた分は Bun 自身の /proc の迂回
```

- link-dir (`B/D/E/<名前>`、procB も)、proc-direct (`/proc/self/fd/<fd>/<名前>`)、relative、link-file の connect は、綴りを作って `net.createServer().listen()` / `net.connect()` / `Bun.listen()` に渡すだけで通る (JS だけ)
- link-file の bind は macOS で Node の node:net と Bun の node:net は通り (`bind` が最後の symlink を辿る)、`Bun.listen` だけ `EADDRINUSE` (原因は未調査)。Linux はどれも `EADDRINUSE` (辿らない。SPEC どおり)

#### 2-3. flock

標準 (Node の fs、Bun の API) に flock は無い。FFI で libc の `flock` を呼び、別のプロセス (CPython の `fcntl.flock(LOCK_EX|LOCK_NB)`) から見た (`t-flock.mjs`):

```text
bun 1.4.4 (macOS)    : openSync(dir,'r') fd=4 isDir=true flock(SH|NB)=0 | while held -> other:EX blocked 35 | flock(9999)=-1 errno=9 | after close -> other:EX acquired
node v26.13.1 (macOS): openSync(dir,'r') fd=11 isDir=true flock(SH|NB)=0 | while held -> other:EX blocked 35 | flock(9999)=-1 errno=9 | after close -> other:EX acquired
bun 1.4.4 (Linux)    : ... flock(SH|NB)=0 | while held -> other:EX blocked 11 | flock(9999)=-1 errno=9 | after close -> other:EX acquired
node v26.13.1 (Linux): ... flock(SH|NB)=0 | while held -> other:EX blocked 11 | flock(9999)=-1 errno=9 | after close -> other:EX acquired
```

- bun:ffi (`dlopen` で `/usr/lib/libSystem.B.dylib` / `libc.so.6`) と node:ffi (`dlopen(null, …)` で自分のプロセスの記号を引く) のどちらでも、他の言語の sweep と同じロックとして効く
- errno は `__error()` (macOS) / `__errno_location()` (Linux) が返す番地を読む。観測では正しく取れた (EBADF=9) が、FFI の呼び出しと読む間に errno が書き換わらない保証は無い (未検証)
- musl (`oven/bun:1.4.4-alpine`) でも bun:ffi の `dlopen("libc.so.6")` 等は通った (`libc.so.6 ok flock(9999)= -1`)

#### 2-4. スレッドの cwd を移す経路 (thread-cwd / thread-cwd-direct)

- worker の中の `process.chdir` は Node・Bun とも `ERR_WORKER_UNSUPPORTED_OPERATION` (確認済み)。プロセスの cwd を変える手は使えない
- FFI を使い捨ての `Worker` (worker_threads。JS のスレッドが 1 つの OS スレッド) の中で呼ぶ: Linux は seccomp を確かめて `unshare(CLONE_FS)` → `fchdir(fd)`、macOS は `__pthread_fchdir(fd)`。続けて FFI で `socket` → 相対の綴りで `bind`+`listen` / `connect` し、fd の番号を main に返して標準の型に取り込む (`t-threadcwd.mjs`、347 バイトのパス、ファイル名 65 バイト)

```text
bun 1.4.4 darwin pathLen=347: bind steps=__pthread_fchdir=0/0 fd=6 exists=true | connect steps=__pthread_fchdir=0/0 fd=5 reply=re:hi | main getcwd same=true process.cwd same=true realpath('.') same=true
node v26.13.1 darwin pathLen=347: (同じ)
bun 1.4.4 linux (docker 既定の seccomp)     : bind steps=seccomp=2 ERR seccomp filter present -> skip unshare
bun 1.4.4 linux (seccomp=unconfined)        : bind steps=seccomp=0,unshare=0/0,fchdir=0 fd=8 exists=true | connect ... reply=re:hi | main getcwd same=true ...
node v26.13.1 linux (seccomp=unconfined)    : (同じ)
```

- 手数: 1 回あたり Worker の起動込みでおよそ 9ms (`t-bench.mjs`、30 回の平均)。比べて、symlink を通した綴りの標準の connect は 0.1ms

```text
bun 1.4.4 darwin: ffi load=2.2ms | worker thread-cwd connect=9.44ms/op | standard connect via symlink=0.13ms/op
node v26.13.1 darwin: ffi load=3.2ms | worker thread-cwd connect=8.72ms/op | standard connect via symlink=0.08ms/op
bun 1.4.4 linux: ffi load=1.8ms | worker thread-cwd connect=8.63ms/op | standard connect via symlink=0.12ms/op
node v26.13.1 linux: ffi load=1.7ms | worker thread-cwd connect=9.12ms/op | standard connect via symlink=0.09ms/op
```

- 未検証: Worker の OS スレッドが終わった後に使い回されないこと、Worker のスレッドが `unshare` の後に新しいスレッドを作らないこと (作ると cwd を引き継ぐ)。Go 版は locked な goroutine を Unlock せずに捨てて同じ心配を消している ([sockat-go の DR-0004](https://github.com/kawaz/sockat-go/blob/main/docs/decisions/DR-0004-thread-cwd-route.md))
- Bun の macOS の標準は、同じことを呼び出し元のスレッドで `__pthread_fchdir(-1)` で戻す形で行っている (1-2)。SPEC-routes が避ける形だが、JS のスレッドに利用者が cwd を付けることは無いので JS では実害は見当たらない

#### 2-5. 自前のソケットを標準の型に取り込む

`t-import.mjs` / `t-bunsock.mjs`:

```text
== bun 1.4.4 darwin (linux も同じ)
  net.Server.listen({fd}): reply=re:hi address()={} fileAfterClose=true
  Bun.listen({fd}): reply=re:hi unix=undefined fileAfterStop=true
  new net.Socket({fd}): FAIL ERR_SOCKET_CLOSED Socket is closed
  Bun.connect({fd}): reply=re:hi
  widened connect 250B + net.Socket({fd}): FAIL ERR_SOCKET_CLOSED Socket is closed
== node v26.13.1 darwin
  net.Server.listen({fd}): reply=re:hi address()=null fileAfterClose=true
  new net.Socket({fd}): reply=re:hi addrs=[null,null,{}]
  widened connect 250B + net.Socket({fd}): len=250 bindWidened=0/0 reply=re:hi addrs=[null,{}]
== node v26.13.1 linux
  net.Server.listen({fd}): reply=re:hi address()=null fileAfterClose=true
  new net.Socket({fd}): reply=re:hi addrs=[null,null,{}]
```

- listen 済みの fd: Node は `server.listen({fd})`、Bun は node:net の `server.listen({fd})` と `Bun.listen({fd})` で取り込める。どれも `address()` がパスを返さない (Node は `null`、Bun は `{}` / `unix` が `undefined`)。閉じてもファイルを消さない
- connect 済みの fd: Node は `new net.Socket({fd})` で取り込める。Bun 1.4.4 の node:net は取り込めない (`ERR_SOCKET_CLOSED`。`net.connect({fd})`・`socket.connect({fd})`・`ready` を待つ形も試して全部 timeout か同じ失敗)。`Bun.connect({fd})` は取り込める
- macOS の広げた sockaddr: FFI で bind / connect し、Node の `net.Socket({fd})` に取り込んでも落ちず、`remoteAddress` は `null` (例外にならない)

#### 2-6. FFI と native addon

| 手段 | 確かめたこと |
|---|---|
| bun:ffi `dlopen` | macOS・Linux glibc・Linux musl で libc を引ける。読み込み 2ms。Bun の文書 (`docs/runtime/ffi.mdx`、bun-v1.4.4) は「`bun:ffi` is **experimental**, with known bugs and limitations. Do not rely on it in production. The most stable way to interact with native code from Bun is to write a Node-API module」と書く |
| bun:ffi `cc` (実行時に TinyCC で C をコンパイル) | macOS は通る (12〜47ms)。Linux は `tcc: error: library 'c' not found` (libc6-dev が無い普通の実行イメージでは使えない) |
| node:ffi | Node 26.1.0 で追加、Stability 1 (Experimental)。26.13.1 は既定で有効 (`--no-experimental-ffi` で無効)。読み込むと `ExperimentalWarning` を stderr に出す。Permission Model の下では `--allow-ffi` が要る。Node 24・22 には無い。26.13.1 は LTS (`process.release.lts` = `Lithium`) |
| N-API の addon | 最小の addon (flock を呼ぶ) を 1 つ build して、macOS で Node 26.13.1 と Bun 1.4.4 の両方で読めた。Linux も node:26 で build した `.node` を Node と `oven/bun:1.4.4` (glibc) で読めた。musl の Bun では `is linked against glibc ... cannot be loaded on Alpine/musl` で読めない (musl 向けを別に build する要がある) |

### 3. 1 つの npm package で Bun と Node を両方扱えるか

- 綴りを標準に渡すだけの部分 (B・E の作成、relative・proc-direct・link-dir・link-file) は node:net / node:fs の同じコードが Bun でも動く (2-2 の結果は Bun で node:net を使っても同じ)
- native の部分の出し分け
  - FFI: `typeof Bun` で `bun:ffi` と `node:ffi` を選ぶ層を 1 つ書けば、上の libc 呼び出し (flock・socket・bind・connect・listen・fcntl・unshare・fchdir・`__pthread_fchdir`・errno) は両方で同じ定義から動いた (実験の `libc.mjs`)。prebuilt は要らない
  - N-API の addon: 1 つの `.node` が Node と Bun の両方で読める。代わりに OS × CPU × libc (darwin-arm64・darwin-x64・linux-x64-gnu・linux-arm64-gnu・linux-x64-musl・linux-arm64-musl、FreeBSD を足すならさらに) の prebuilt を CI で作って配る (optionalDependencies か prebuildify 等)
- 返す標準の型の差
  - Bun では利用者が `Bun.listen` / `Bun.connect` を使うか node:net を使うかで型が違う。自前のソケットの connect は Bun の node:net に取り込めない (2-5) ので、Bun で node:net の `Socket` を返す形は、自前のソケットを使う経路 (thread-cwd-direct、widened) では作れない
  - 自前のソケットを取り込んだ listener は `address()` がパスを返さない (2-5)
- Node が FFI を持たない版 (22・24) は、JS だけで作れる経路に絞る形になる (下の表の「JS だけ」の列)

### 4. 経路の表

凡例: 「JS」= node:net / node:fs だけで作れる、「FFI」= bun:ffi か node:ffi (Node 26.1 以上) が要る、「addon」= FFI の代わりに N-API の addon でも作れる、「×」= 作れない、「(標準)」= その runtime の標準自身が同じことをする。全部 Linux と macOS で実測した範囲 (FreeBSD は未検証)。

D を作る経路 (bind の link-dir・link-file・thread-cwd・at、`resolve_for_bind`・`resolve_for_connect`) は、D を守る共有の flock に FFI / addon が要る。下の表の bind の行の「JS」は綴りを作って bind するところまでのこと。

bind の順:

| 順 | 経路 | OS | Bun | Node |
|---|---|---|---|---|
| 1 | standard | 全部 | JS。ただし Bun の標準は 103 (macOS) / 107 (Linux) を超えると自分の迂回でファイル名だけ / `/proc/self/fd` の綴りで bind する (1-2) | JS。macOS は libuv 1.53 以上なら 253 まで広げた sockaddr で bind する (1-1)。Linux の 22 は 108 を超えると切り詰める |
| 2 | link-dir (procB) | Linux | JS (+ D の flock は FFI) | JS (+ D の flock は FFI / addon) |
| 3 | link-dir (実パス) | 全部 | JS (+ flock は FFI) | JS (+ flock は FFI / addon) |
| 4 | link-file | macOS | node:net なら JS (+ flock は FFI)。`Bun.listen` は `EADDRINUSE` | JS (+ flock は FFI / addon) |
| 5 | thread-cwd | Linux・macOS | FFI (Worker + `unshare`/`fchdir` か `__pthread_fchdir` + 自前のソケット + `listen({fd})`) | FFI / addon (同じ形。addon ならスレッドを C の中で作れて Worker は要らない見込み、未検証) |
| 5 | at | FreeBSD | FFI (`bindat` + `listen({fd})`)、未検証 | FFI / addon、未検証 |

connect の順:

| 順 | 経路 | OS | Bun | Node |
|---|---|---|---|---|
| 1 | standard | 全部 | JS。ファイル名が収まれば Bun の標準自身が proc-direct (Linux) / thread-cwd-direct (macOS) に当たることをする | JS。macOS の libuv 1.53 以上は 253 まで (widened に当たる) |
| 2 | proc-direct | Linux | JS (`fs.openSync` に数値の `O_PATH` + `/proc/self/fd/<fd>/<名前>`) | JS |
| 2 | relative | Linux (`/proc` 無し)・macOS | JS | JS |
| 2 | widened | macOS | FFI (自前の connect + `Bun.connect({fd})`。node:net の `Socket` には取り込めない) | libuv 1.53 以上は標準が受ける。それより前は FFI / addon (自前の connect + `net.Socket({fd})`) |
| 2 | at-direct | FreeBSD | FFI、未検証 | FFI / addon、未検証 |
| 3 | thread-cwd-direct | Linux・macOS | FFI (Worker + 自前のソケット + `Bun.connect({fd})`) | FFI / addon (`net.Socket({fd})`) |
| 4 | link-file | 全部 | JS (D を作らない。B と E は fs で作れる) | JS |

置き場まわり:

| 部品 | Bun | Node |
|---|---|---|
| B を作る (`mkdirat`・`fchmodat`・`openat(O_NOFOLLOW)`) | Linux は `/proc/self/fd/<親の fd>/<名前>` で JS。macOS は確かめ済みの実パスへの fs の操作で JS (fd 基準でない分は SPEC-routes の手順から外れる) か FFI | 同じ |
| D の共有の flock、`sweep` の排他の flock | FFI | FFI / addon。Node 22・24 は × (外部コマンドの `flock(1)` を持たせる手は macOS に無い) |
| seccomp の判定 | JS (`/proc/self/status`) | JS |

## 暫定的な結論

### 確認できたこと

- 標準の上限は runtime と libuv の版で違い、その境界を超えた時の振る舞いもばらばら (Node 22 の Linux は黙って切り詰める、Node の macOS は libuv 1.53 以上で広げた sockaddr、Bun は自分の迂回で DR-0017 が bind に使わないと決めた綴りを作る)。sockat-ts は境界を runtime ごと・実行時に決める必要がある (DR-0004 の「標準自身で境界を試験する」)
- 綴りを標準に渡すだけの経路 (link-dir・link-file・relative・proc-direct、既定の connect の link-file) は Bun と Node の両方で JS だけで作れる。既定の connect は D を作らないので、全部 JS だけで済む
- D を守る flock は標準に無く、FFI か addon が要る。FFI の flock は bun:ffi と node:ffi の両方で他の言語のロックと同じに効いた
- スレッドの cwd を移す経路は Worker + FFI で両方作れる (1 回およそ 9ms)。自前のソケットの fd は Node は listen・connect とも、Bun は `Bun.listen` / `Bun.connect` と node:net の listen で取り込める。Bun の node:net の `Socket` だけ取り込めない
- N-API の addon は 1 つの `.node` で Node と Bun の両方から読めるが、glibc と musl で別の build が要る

### sockat-ts の DR と kawaz の裁定に回る論点

1. **標準に渡す長さを runtime の標準が受け付ける長さにするか**: Bun の標準は長いパスでもファイル名が収まれば受け付けるが、bind の綴りがファイル名だけ / `/proc/self/fd/<閉じた fd>/…` になる。Node の macOS (libuv 1.53 以上) は 104〜253 を広げた sockaddr で bind し、CPython の相手の `getpeername` が壊れる (1-2)。DR-0004 を字のとおりに当てると、どちらも sockat の経路に回らない。JS の側には綴りが漏れない (`address()` も close の unlink も元のパス) が、別の言語の相手と運用の道具には漏れる。「bind は `sun_path` − 1 (Node の Linux は 108) を標準に渡す長さとし、それを超えたら sockat の経路に回す」とするかを決める。connect は綴りが残らないので、標準が受けるなら渡してよい見込み
2. **listener を閉じた時の unlink**: Node と Bun は閉じる時に渡した綴りで unlink し、止める口が無い (1-3)。`bind_ex` の「閉じても消さない」を守るには自前のソケット + `listen({fd})` が要り、そうすると `address()` がパスを返さなくなる (2-5)。どちらを取るか
3. **Node の listen の無いディレクトリの errno**: 標準は `EACCES` (libuv が換える)、SPEC は `ENOENT`
4. **Bun で返す型**: `Bun.listen` / `Bun.connect` の型か、node:net の型か (両方出すか)。node:net の `Socket` は自前の connect の fd を取り込めない
5. **Node 22・24 の扱い**: node:ffi が無いので、FFI を前提にすると bind の長いパスが作れない (D の flock が無い)。addon で救うか、JS だけの範囲 (既定の connect の全部と、bind は `ENAMETOOLONG`) に絞るか

### 設計の選択肢

runtime の範囲 × native の持ち方の主な案。「届く範囲」は Linux と macOS の bind / connect の長いパスについて。

| 案 | runtime | native の持ち方 | 届く範囲 | 配布の重さ | 保守の重さ |
|---|---|---|---|---|---|
| A | Bun だけ | bun:ffi | SPEC の経路を全部 (FreeBSD は未検証、Bun の FreeBSD 対応も未確認) | 軽い (pure JS の package) | 低〜中。bun:ffi は Bun の文書で「experimental、本番で頼るな、安定した手は Node-API」 |
| B | Bun と Node | FFI (bun:ffi / node:ffi) を実行時に選ぶ。Node 26.1 未満は FFI の要る経路を「使えない」として飛ばす | Bun と Node 26.1 以上は全部。Node 22・24 は既定の connect の全部と、FFI の要らない経路の bind だけ (D の flock が無いので実質 bind の長いパスは `ENAMETOOLONG`) | 軽い (pure JS。prebuilt なし) | 中。node:ffi は Stability 1 で API が変わりうる。`ExperimentalWarning` を出す (FFI を要る経路に来た時だけ読み込めば、短いパスと既定の connect では出ない) |
| C | Bun と Node | N-API の addon 1 つを両方から読む | 全 runtime・全版で全部 (addon の中でスレッドを作れば Worker も要らない見込み) | 重い (OS × CPU × libc の prebuilt、glibc と musl を別に。Linux の musl の Bun は glibc 版を読めない) | 高。C のコード + build の CI の行列 + prebuilt の公開 |
| D | Bun と Node | Bun は bun:ffi、Node は addon | C と同じ | Node 向けだけ重い | 最も高い (native の層が 2 つ) |
| E | Bun と Node | native を持たない (JS だけ) | 既定の connect は全部。bind は link-dir・link-file を作れるが D に flock を掛けられず、他の言語の `sweep` や systemd-tmpfiles に生きている D を消されうる (SPEC から外れる)。thread-cwd・widened (libuv 1.53 未満)・at は作れない | 最も軽い | 最も低い |

推し (決定ではない): **B**。依頼元が Bun なので Bun で全部届くことを先に満たし、Node も 26 (LTS) では同じコードで全部届く。prebuilt を持たないので配布と CI が軽い。悪い面は、bun:ffi も node:ffi も experimental (Bun の文書は bun:ffi を本番で頼るなと明言し、Node-API を勧める。どちらも版上げで壊れうるので、sockat-ts の CI で Bun の最新と Node の current・LTS を回して早く気づく必要がある)、Node 22・24 で bind の長いパスが届かない (Node 22 の標準は黙って切り詰めるので、少なくとも sockat-ts がそれを `ENAMETOOLONG` に変えることには価値がある)、Worker を使い捨てる thread-cwd が 1 回およそ 9ms かかる (bind と、connect の 3 番目の経路だけなので普段の connect には効かない)。C は届く範囲と安定性 (Bun 自身が勧める Node-API) で勝るが、prebuilt の行列の保守が TypeScript 版の規模に見合うかは、Node 22・24 で長いパスに bind したい利用者がいるかと、bun:ffi の不安定さをどこまで許すか次第。FFI を呼ぶ層を 1 か所に閉じておけば、B から C へ後で移る時はその層の差し替えで済む見込み (FFI の関数と addon の関数を同じ形にそろえる前提)。

### 未検証のこと

| 項目 | 理由 | 確かめ方 |
|---|---|---|
| 公式の Node 26.13.1 の macOS バイナリの境界 (見込みは 104) | 公式バイナリを取ってきて実行する操作が auto mode の classifier に止められた | nodejs.org の `node-v26.13.1-darwin-arm64.tar.gz` を SHASUMS256 で確かめて展開し、`probe-net.mjs` を 103〜105・253 で流す |
| Worker のスレッドが終わった後に使い回されないこと、`unshare` の後に新しいスレッドを作らないこと | 観測の手段を用意していない | Linux で Worker の中の `gettid` と、終わった後の `/proc/self/task` を比べる |
| FFI の呼び出しと errno を読む間に errno が書き換わらないこと | 観測では正しかったが保証が無い | 失敗する呼び出しを大量に繰り返して errno が食い違わないか見る。addon なら C の中で読めるので心配が無い |
| `Bun.listen` だけ link-file の bind が `EADDRINUSE` になる原因 | 未調査 | Bun の `Bun.listen` の unix の前処理を読む |
| FreeBSD (`bindat` / `connectat`、Bun の FreeBSD 対応) | 実機が無い | sockat-rs / sockat-go と同じく CI の VM |
| Linux の `/proc` が無い環境での Bun の標準の振る舞い | 試していない | `/proc` を mount しない container で `Bun.listen` の長いパス |

## 関連

- [前の調査 (他言語)](2026-11-18-ports-to-other-languages.md) の JavaScript / TypeScript の節 (macOS の Node の 253 は libuv 1.53.0 の結果だった)
- [issue: TypeScript 版を作る](../issue/2026-11-21-typescript-port.md)
- [SPEC](../SPEC-ja.md)、[SPEC-routes](../SPEC-routes-ja.md)、[DR-0017](../decisions/DR-0017-resolve-through-persistent-base.md)、[DR-0004](../decisions/DR-0004-standard-length-per-language.md)、[DR-0003](../decisions/DR-0003-single-connect-when-standard-never-blocks.md)
- [sockat-go の DR-0004 (thread-cwd)](https://github.com/kawaz/sockat-go/blob/main/docs/decisions/DR-0004-thread-cwd-route.md)、[DR-0005 (widened を使わない)](https://github.com/kawaz/sockat-go/blob/main/docs/decisions/DR-0005-no-widened-sockaddr.md)、[DR-0006 (自前のソケットを標準に渡す)](https://github.com/kawaz/sockat-go/blob/main/docs/decisions/DR-0006-own-socket-into-net.md)
- 一次資料: [Bun の bsd.c (bun-v1.4.4)](https://github.com/oven-sh/bun/blob/bun-v1.4.4/packages/bun-usockets/src/bsd.c)、[libuv の pipe.c (v1.52.1)](https://github.com/libuv/libuv/blob/v1.52.1/src/unix/pipe.c)・[(v1.53.0)](https://github.com/libuv/libuv/blob/v1.53.0/src/unix/pipe.c)、Node の `src/pipe_wrap.cc` ([v22.23.5](https://github.com/nodejs/node/blob/v22.23.5/src/pipe_wrap.cc)・[v26.13.1](https://github.com/nodejs/node/blob/v26.13.1/src/pipe_wrap.cc))、[Node の node:ffi の文書 (v26.13.1)](https://github.com/nodejs/node/blob/v26.13.1/doc/api/ffi.md)
