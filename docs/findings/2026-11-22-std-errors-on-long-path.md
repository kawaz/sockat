# 長すぎる Unix domain socket のパスを各言語の標準ライブラリに渡した時に出るもの

- Date: 2026-11-22 (測定日)

Rust・Python・Go・Node.js・Bun の標準ライブラリ (sockat は使わない) で、`sun_path` の上限前後のパスを bind / connect し、エラーの型・コード・文言、またはエラーにならずに通る様子を実機で採った。利用者向け README の冒頭に載せる「見覚えのあるエラー」と、検索語の材料にする。

## 判明した事実

- Rust・Python・Go は、macOS で 104 バイト以上、Linux で 108 バイト以上のパスを bind / connect で必ず断る。上限ちょうど (macOS 103 / Linux 107) は通る
- 断り方は 3 言語で違う。Rust は `io::ErrorKind::InvalidInput` で OS のエラー番号が無く (`raw_os_error()` が `None`)、文言は `path must be shorter than SUN_LEN`。Python は `OSError` (errno は `None`) で文言は `AF_UNIX path too long`。Go は `*net.OpError` の中身が `*os.SyscallError` で、errno は 22 (`EINVAL`)、文言は `listen unix <path>: bind: invalid argument` / `dial unix <path>: connect: invalid argument`
- Rust と Python は socket のシステムコールの前に自前の長さの検査で断る (errno が付かない)。Go は検査せずに `bind` / `connect` を呼び、OS から `EINVAL` を受け取る
- 上の断り方は macOS と Linux で同じ。変わるのは境目だけ (103 / 104 と 107 / 108)
- Python は `asyncio.start_unix_server(path=...)` と `asyncio.open_unix_connection(path)` でも同じ `OSError('AF_UNIX path too long')`
- Node.js は断らずに通すことがある。macOS では 253 バイトまで bind / connect とも通り、254 バイト以上で `EINVAL`。Linux では 108 バイトまで通り (NUL の入らない 108 バイトも通る)、109 バイト以上で `EINVAL`
- Node.js の境目は Node の版でなく、同梱の libuv の版で決まる。測った macOS の Node は Homebrew の物で libuv 1.53.0 (104〜253 バイトを広げた sockaddr で通す)、Linux の `node:latest` は同じ Node 26.13.1 で libuv 1.52.1。libuv 1.52 以前を同梱する macOS の Node は 104 バイトから `EINVAL` の見込み (未測定)。仕組みは [TypeScript 版の調査](../research/2026-11-21-typescript-port.md) の 1-1
- Node.js が通した socket のファイルは、渡したパスそのままの場所にできた (切り詰められた別名のファイルは無かった。macOS の 104・105・200・253 と Linux の 108 で確認)。通った時のエラーは無く、`server.address()` も渡したパスを返す
- Node.js が断る時は例外ではなく `'error'` イベント。ハンドラが無いと `Unhandled 'error' event` で落ちる。コードは `EINVAL` (errno -22)、syscall は bind が `listen`、connect が `connect`
- Bun は `Bun.listen` / `Bun.connect` も `node:net` も、測った全部の長さ (macOS 900 バイトまで、Linux 3000 バイトまで) で bind / connect とも通った。socket のファイルは渡したパスそのままの場所にできた
- Bun の結果は、ファイル名が `s.sock` (6 バイト) でディレクトリだけを深くした場面のもの。Bun は長いパスを自分で迂回し、通るかはパス全体でなくファイル名の長さで決まる (macOS は 102 バイトまで、Linux はおよそ 91 バイトまで。超えると `EINVAL`)。ファイル名の長い場面はこの測定に無く、[TypeScript 版の調査](../research/2026-11-21-typescript-port.md) の 1-2 にある
- connect は、相手の socket を相対パス `s.sock` で bind して置いてから、絶対パスで試した。Rust・Python・Go は上限を超えると相手がいても connect の前に断る。通る言語 (Node.js の通る範囲、Bun) は相手に繋がった
- 測った Node.js 26.13.1 は、どの長さでもパスを切り詰めなかった (通る時は渡したパスのまま、通らない時は `EINVAL`)。黙って 108 バイトに切り詰めて成功を返すのは Linux の Node 22 ([TypeScript 版の調査](../research/2026-11-21-typescript-port.md) の 1-1 の実測) で、この測定には無い

## 表

セルは「通った」(socket のファイルは渡したパスの場所にできた) か、エラーの要点。文言の全文は次の節。macOS は 103 / 104 / 105 / 200 バイト、Linux は 107 / 108 / 109 / 200 バイト。

### bind

| 言語・API | macOS 103 | macOS 104 | macOS 105 | macOS 200 | Linux 107 | Linux 108 | Linux 109 | Linux 200 |
|---|---|---|---|---|---|---|---|---|
| Rust `UnixListener::bind` | 通った | `InvalidInput` `path must be shorter than SUN_LEN` | 同左 | 同左 | 通った | 同左 | 同左 | 同左 |
| Python `socket.bind` | 通った | `OSError` `AF_UNIX path too long` | 同左 | 同左 | 通った | 同左 | 同左 | 同左 |
| Python `asyncio.start_unix_server` | 通った | `OSError` `AF_UNIX path too long` | 同左 | 同左 | 通った | 同左 | 同左 | 同左 |
| Go `net.Listen("unix")` | 通った | `listen unix …: bind: invalid argument` (EINVAL 22) | 同左 | 同左 | 通った | 同左 | 同左 | 同左 |
| Node.js `server.listen(path)` | 通った | 通った | 通った | 通った | 通った | 通った | `listen EINVAL: invalid argument …` | 同左 |
| Bun `Bun.listen({unix})` | 通った | 通った | 通った | 通った | 通った | 通った | 通った | 通った |
| Bun の上の `node:net` | 通った | 通った | 通った | 通った | 通った | 通った | 通った | 通った |

### connect

| 言語・API | macOS 103 | macOS 104 | macOS 105 | macOS 200 | Linux 107 | Linux 108 | Linux 109 | Linux 200 |
|---|---|---|---|---|---|---|---|---|
| Rust `UnixStream::connect` | 通った | `InvalidInput` `path must be shorter than SUN_LEN` | 同左 | 同左 | 通った | 同左 | 同左 | 同左 |
| Python `socket.connect` | 通った | `OSError` `AF_UNIX path too long` | 同左 | 同左 | 通った | 同左 | 同左 | 同左 |
| Python `asyncio.open_unix_connection` | 通った | `OSError` `AF_UNIX path too long` | 同左 | 同左 | 通った | 同左 | 同左 | 同左 |
| Go `net.Dial("unix")` | 通った | `dial unix …: connect: invalid argument` (EINVAL 22) | 同左 | 同左 | 通った | 同左 | 同左 | 同左 |
| Node.js `net.connect(path)` | 通った | 通った | 通った | 通った | 通った | 通った | `connect EINVAL … - Local (undefined:undefined)` | 同左 |
| Bun `Bun.connect({unix})` | 通った | 通った | 通った | 通った | 通った | 通った | 通った | 通った |
| Bun の上の `node:net` | 通った | 通った | 通った | 通った | 通った | 通った | 通った | 通った |

Node.js と Bun の追加の長さ (bind / connect とも同じ結果):

| 環境 | 長さ | Node.js | Bun |
|---|---|---|---|
| macOS | 250 / 251 / 252 / 253 | 通った | 未測定 (200・500・900 は通った) |
| macOS | 254 / 255 / 256 / 300 / 400 / 500 | `EINVAL` | 500 は通った |
| macOS | 900 | 未測定 | 通った |
| Linux | 3000 | 未測定 | 通った |

## 言語ごとの出力

パスは `/tmp/se-XXXXXX/D…/D…/d/s.sock` のように途中を省略した (文言は変えていない)。端末に出る形は、例外・panic・`'error'` イベントを捕まえずに出した時の物と、Go のように `err` をそのまま表示した物。

### Rust (`std::os::unix::net`、macOS 104 バイト、Linux 108 バイトでも同じ)

```text
kind=InvalidInput raw_os_error=None
Display: path must be shorter than SUN_LEN
Debug: Error { kind: InvalidInput, message: "path must be shorter than SUN_LEN" }
```

`unwrap()` した時の端末の出力:

```text
thread 'main' panicked at rs/main.rs:10:115:
called `Result::unwrap()` on an `Err` value: Error { kind: InvalidInput, message: "path must be shorter than SUN_LEN" }
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
```

### Python (`socket` と `asyncio`、macOS 104 バイト、Linux 108 バイトでも同じ)

```text
type=builtins.OSError errno=None str=AF_UNIX path too long repr=OSError('AF_UNIX path too long')
```

捕まえない時の端末の出力 (`s.bind(path)`):

```text
Traceback (most recent call last):
  File "t.py", line 9, in <module>
    s=socket.socket(socket.AF_UNIX); (s.bind if mode=="bind" else s.connect)(p)
                                     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^
OSError: AF_UNIX path too long
```

### Go (`net.Listen` / `net.Dial`、macOS 104 バイト、Linux 108 バイトでも同じ)

bind:

```text
type=*net.OpError
Error(): listen unix /tmp/se-XXXXXX/D…/D…/d/s.sock: bind: invalid argument
%#v: &net.OpError{Op:"listen", Net:"unix", Source:net.Addr(nil), Addr:(*net.UnixAddr)(0x…), Err:(*os.SyscallError)(0x…)}
OpError Op="listen" Net="unix" Addr=/tmp/se-XXXXXX/D…/D…/d/s.sock Err=*os.SyscallError(bind: invalid argument)
errno=22 (invalid argument)
```

connect:

```text
type=*net.OpError
Error(): dial unix /tmp/se-XXXXXX/D…/D…/d/s.sock: connect: invalid argument
OpError Op="dial" Net="unix" Addr=/tmp/se-XXXXXX/D…/D…/d/s.sock Err=*os.SyscallError(connect: invalid argument)
errno=22 (invalid argument)
```

### Node.js (macOS 254 バイト、Linux 109 バイトでも同じ形)

`'error'` イベントで受けた時 (bind、Linux 109 バイト):

```text
type=Error code=EINVAL errno=-22 syscall=listen address=/tmp/se-XXXXXX/D…/D…/ddd/d/s.sock message=listen EINVAL: invalid argument /tmp/se-XXXXXX/D…/D…/ddd/d/s.sock
```

connect (Linux 109 バイト):

```text
type=Error code=EINVAL errno=-22 syscall=connect address=/tmp/se-XXXXXX/D…/D…/ddd/d/s.sock message=connect EINVAL /tmp/se-XXXXXX/D…/D…/ddd/d/s.sock - Local (undefined:undefined)
```

ハンドラが無い時の端末の出力 (bind、macOS 254 バイト。スタックの後半は省略):

```text
node:events:505
    throw er; // Unhandled 'error' event
    ^

Error: listen EINVAL: invalid argument /tmp/se-XXXXXX/D…/D…/d/s.sock
    at Server.setupListenHandle [as _listen2] (node:net:2368:21)
    at listenInCluster (node:net:2499:12)
    at Server.listen (node:net:2641:5)
    …
Emitted 'error' event on Server instance at:
    at emitErrorNT (node:net:2478:8)
    at process.processTicksAndRejections (node:internal/process/task_queues:90:21) {
  code: 'EINVAL',
  errno: -22,
  …
```

connect (macOS 254 バイト) の先頭:

```text
node:events:505
    throw er; // Unhandled 'error' event
    ^

Error: connect EINVAL /tmp/se-XXXXXX/D…/D…/d/s.sock - Local (undefined:undefined)
    at internalConnect (node:net:1468:16)
    …
```

### Bun

測った範囲ではエラーが出なかった。通った時の出力 (macOS 104 バイト、`Bun.listen`):

```text
OK Bun.listen /tmp/se-XXXXXX/D…/D…/d/s.sock
```

`Bun.connect` は `open` ハンドラが呼ばれ (`open`)、`OK Bun.connect`。

### ファイル名が長い時の Bun と Node.js (追加の測定、macOS)

ディレクトリは短く (`/tmp/se-XXXXXX`)、ファイル名を 145 バイトにしたパス (全体 160 バイト) に listen した。

```text
runtime: bun 1.4.4 | path bytes: 160 | name bytes: 145
node:net listen -> EINVAL | listen EINVAL: invalid argument /tmp/se-X/nnn…n.sock
Bun.listen -> EINVAL | Failed to listen at /tmp/se-X/nnn…n.sock
runtime: node v26.13.1 | path bytes: 160 | name bytes: 145
node:net listen -> ok
```

- Bun はファイル名が長いと断る。コードは `EINVAL` で、`node:net` を通した時の文言は Node.js と同じ `listen EINVAL: invalid argument <パス>`、`Bun.listen` は `Failed to listen at <パス>`
- 同じパスを Node.js (libuv 1.53.0) は通す。同じコードが、ランタイムによって通ったり断られたりする

## 環境と版

| 項目 | macOS | Linux (docker) |
|---|---|---|
| OS | macOS 26.5.2 (Darwin 25.5.0)、arm64 | Debian GNU/Linux 13 (trixie) のコンテナ、OrbStack のカーネル 7.2.12、arm64、root、既定の seccomp |
| Rust | rustc 1.100.0 | rustc 1.100.0 (`rust:latest`) |
| Python | 3.15.2 | 3.15.2 (`python:latest`) |
| Go | go1.27.3 darwin/arm64 | go1.27.4 linux/arm64 (`golang:latest`) |
| Node.js | v26.13.1 (Homebrew、libuv 1.53.0) | v26.13.1 (`node:latest`、libuv 1.52.1) |
| Bun | 1.4.4 | 1.4.5 (`oven/bun:latest` から取り出した実行ファイルを `node:latest` のコンテナで実行) |

## 手順

作業場所は `$TMPDIR/std-errors/`。長さを正確に作るための深いディレクトリは `mktemp -d /tmp/se-XXXXXX` の下に作り、終わったら消した。

1. 長さ N のパスを作る (`mk.py`): `/tmp/se-XXXXXX` の下にディレクトリ (名前は `d` の繰り返し、1 段 40 文字まで) を深く作り、`<ディレクトリ>/s.sock` の全長を N バイトにする
2. bind: そのパスで socket を作る。成功したら 1 秒保持し、保持中に `find <基点> -type s -o -type f -o -type l` で実際にできたファイルの場所と長さを出す。エラーならエラーの型・コード・文言を出す
3. connect: ディレクトリに `cd` して Python で相対パス `s.sock` を bind・listen し、accept して接続を保持する相手を置いてから、絶対パスで connect する。成功したらファイルの場所を出す
4. 試験用のプログラム (標準ライブラリだけ):
   - Rust: `UnixListener::bind(p)` / `UnixStream::connect(p)`。`rustc -O` でビルド
   - Python: `socket.socket(AF_UNIX).bind(p)` / `.connect(p)`、`asyncio.start_unix_server(lambda r, w: None, path=p)` / `asyncio.open_unix_connection(p)`
   - Go: `net.Listen("unix", p)` / `net.Dial("unix", p)`。`go build`
   - Node.js: `net.createServer().listen(p)` / `net.connect(p)`
   - Bun: `Bun.listen({unix: p, socket: {data() {}}})` / `await Bun.connect({unix: p, socket: {data() {}, open() {}}})`、および Bun で同じ Node.js の試験を実行 (`bun t.js …`)
5. 長さは macOS が 103・104・105・200、Linux が 107・108・109・200。追加で Node.js を macOS の 250〜256・300・400・500、Bun を macOS の 500・900 と Linux の 3000
6. Linux は言語ごとの公式イメージのコンテナ (`docker run --rm -v <作業場所>:/w <イメージ> bash /w/run.sh <長さ>`)。Rust と Go はコンテナの中でビルドした実行ファイルを使い、Bun は `oven/bun` から `docker cp` した実行ファイルを `node` のコンテナに載せて実行した

## 未確認

- Linux は arm64 の docker (root、既定の seccomp、OrbStack のカーネル) だけ。x86_64 と一般ユーザは測っていない
- macOS 103 と Linux 107 より短いパスは測っていない (通ることを前提にした対照)
- Node.js と Bun が長いパスを通す手段 (システムコールの使い方、カーネルが覚える綴り) は、この測定では観測していない。「渡したパスの場所にファイルができた」までがこの測定の事実で、手段は [TypeScript 版の調査](../research/2026-11-21-typescript-port.md) にある
- libuv 1.52 以前を同梱する macOS の Node.js (公式のバイナリ等) の境目
- Bun のディレクトリだけが深いパスの上限 (macOS 900 より上、Linux 3000 より上)。macOS は `PATH_MAX` (1024) のために深いディレクトリを作れず、900 までしか試していない
- Rust の `fn main() -> Result<(), io::Error>` で `?` に流した時の端末の出力 (`Error: …` の形) は採っていない。`unwrap()` の panic と `Display` / `Debug` だけ
- Go で `err` を `fmt.Println` 以外 (ログのライブラリ等) で出した形は採っていない
- Windows は対象外
