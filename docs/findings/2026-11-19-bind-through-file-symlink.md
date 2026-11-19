# ファイルを指す symlink を通した bind の実測 (macOS / Linux)

2026-11-19。[docs/issue/archive/2026-11-19-bind-through-file-symlink.md](../issue/archive/2026-11-19-bind-through-file-symlink.md) の「確かめること」のうち、手元の macOS と Linux (docker) で確かめられるものを実測した。

## 目的

短い置き場に、まだ無い長い元のパスを指す symlink を作り、その symlink に bind すると、辿る OS では元のパスにソケットができるか、できた後に何ができるかを確かめる。

## 環境

- macOS 26 (Darwin 25.5.0)、Python 3 標準ライブラリだけ (`python3 -I`)
- Linux: `docker run --rm -v <dir>:/p:ro python:3.13-slim python -I /p/t.py` (カーネルは docker の VM のもの)
- 元のパス: macOS は全体 336 バイト・ファイル名 150 バイト、Linux は全体 229 バイト・ファイル名 150 バイト (どちらも 60 バイトのディレクトリ名 + 150 バイトのファイル名を `mkdtemp` の下に作った)
- 置き場: macOS は `getconf DARWIN_USER_TEMP_DIR` の下 (symlink のパス 69 バイト) と `/tmp` の下 (25 バイト)。Linux は `/tmp` の下 (25 バイト)。どちらも `mkdtemp` で作った専用ディレクトリで、終わりに `rmtree` した
- 元のパスは sun_path の上限を超えるので、元のパスそのものでは bind も connect もできない (Python が `OSError('AF_UNIX path too long')`)。「元のパスに connect できるか」は、元のパスを指す別の symlink 経由での connect で見た

## 結果の表

| 場面 | macOS | Linux (docker) |
|---|---|---|
| 1. まだ無い先を指す symlink に bind | 通る。元のパスにソケットができる (`lstat` が socket)。symlink は symlink のまま残る | `EADDRINUSE`。元のパスには何もできない (ENOENT のまま) |
| 1. 元のパスのソケットに symlink 経由で connect | 通る (別プロセス) | 該当なし (ソケットができない。symlink 経由は ENOENT) |
| 2. `getsockname()` | symlink のパス (元のパスではない) | 該当なし (bind が失敗) |
| 2. カーネルが返す長さとバイト列 | 置き場が `$TMPDIR` (69 バイト): 長さ 72、`\x48\x01` + symlink のパス + NUL。`/tmp` (25 バイト): 長さ 28、`\x1c\x01` + パス + NUL | 該当なし |
| 2. `fstat(fd)` の `(st_dev, st_ino)` と元のパスの `lstat` | 一致しない (`st_dev` が -1) | 該当なし |
| 3. symlink を消した後 | 既存の接続は生きたまま通信できる。元のパスのソケットは残る。同じ元のパスを指す新しい symlink を作ると connect できる | 該当なし |
| 4a. 元のパスに通常ファイルがある | `EADDRINUSE`。通常ファイルの中身はそのまま。symlink もそのまま | `EADDRINUSE` (先が無い時と同じエラー)。通常ファイルの中身はそのまま |
| 4b. 元のパスに生きたソケットがある | `EADDRINUSE`。元のソケットはそのまま (symlink 経由の connect は通る) | `EADDRINUSE`。元のソケットはそのまま (symlink 経由の connect は通る) |
| 4b. 元のパスに閉じた後の古いソケットのファイルがある | `EADDRINUSE`。ファイルはそのまま | `EADDRINUSE`。ファイルはそのまま |
| 5. 2 段の symlink (置き場 → 置き場 → 元のパス) | 通る。元のパスにソケットができ、最初の symlink 経由で connect できる。`getsockname` は最初の symlink のパス (長さ 75 / `/tmp` で 31) | `EADDRINUSE`。元のパスには何もできない |
| 6. 置き場が `$TMPDIR` か `/tmp` か | 挙動は同じ。違いは綴りの長さだけ (69 バイトと 25 バイト、カーネルが返す長さも 72 と 28) | 該当なし (`/tmp` のみ) |
| 7. 辿らない OS で bind した後に残るもの | 該当なし (辿る) | 何も作られない。元のパスもそのディレクトリも空のまま。symlink を消せば置き場は空 |

## 場面ごとの詳細

実験のコードは `$TMPDIR` の下に置いて終わりに片付けた (リポには置いていない)。要点のコード片は次の通り。

```python
sym = os.path.join(place, "sockat.s1")
os.symlink(orig, sym)          # orig はまだ無い 200 バイト以上のパス
s = socket.socket(socket.AF_UNIX)
s.bind(sym); s.listen(16)
```

getsockname(2) を直接呼ぶ部分:

```python
libc = ctypes.CDLL(None, use_errno=True)
buf = ctypes.create_string_buffer(512); ln = ctypes.c_uint32(512)
libc.getsockname(s.fileno(), buf, ctypes.byref(ln))
```

### 1. まだ無い先を指す symlink に bind

macOS (`$TMPDIR` の下):

```
[1] symlink len=69; bind OK
[1] after: symlink=symlink orig=socket
[1] connect via orig directly: ERR OSError('AF_UNIX path too long')
[1] connect via symlink: OK
```

Linux:

```
[1] symlink len=25; bind ERR errno=98(EADDRINUSE) Address already in use
[1] after: symlink=symlink orig=なし(ENOENT)
[1] connect via symlink: ERR FileNotFoundError(2, 'No such file or directory')
[7] after failed bind: symlink=symlink orig=なし(ENOENT) origdir entries=[] place entries=['sockat.s1']
[7] place entries after cleanup: []
```

元のパスのディレクトリが空のまま (7)。symlink を消せば置き場に何も残らない。

### 2. getsockname

macOS (`$TMPDIR` の下):

```
[2] getsockname() str: '/var/folders/.../T/sk3l2mm02l/sockat.s1'
[2] ctypes getsockname ret=0 len=72 raw=b'H\x01/var/folders/.../T/sk3l2mm02l/sockat.s1\x00'
[2] fstat(dev,ino)=(-1, 2769243) lstat(orig)=(16777231, 594061109)
```

`/tmp` の下: `len=28 raw=b'\x1c\x01/tmp/ski3f7sybo/sockat.s1\x00'`。長さは先頭 2 バイト (`sun_len`, `sun_family`) + パス + NUL で、どちらも bind に渡した symlink のパスで元のパスは出てこない。

### 3. symlink を消した後 (macOS)

```
[3] after unlink symlink: symlink=なし(ENOENT) orig=socket
[3] existing conn recv: b'hi'
[3] connect via orig directly: ERR OSError('AF_UNIX path too long')
[3] connect via new symlink: OK
```

`unlink` した後も、symlink 経由で張った接続は通信できる。元のパスのソケットのファイルは自動では消えない (listener を閉じても残る)。

### 4. 元のパスに既に物がある

macOS:

```
[4a] regular file at orig: bind ERR errno=48(EADDRINUSE) ...; orig=通常ファイル content='keep' symlink=symlink
[4b] live socket: bind ERR errno=48(EADDRINUSE) ...; orig=socket symlink=symlink; connect via symlink:OK
[4b] stale socket (listener closed): bind ERR errno=48(EADDRINUSE) ...; orig=socket
```

Linux は同じ 3 行で errno が 98 (`EADDRINUSE`)。元の物は壊れない。macOS の `EADDRINUSE` は「辿った先に既に物がある」、Linux の `EADDRINUSE` は「symlink 自体が既にある」で、同じ errno の別の理由である。4b の既存ソケットは、短い名前で bind して `rename` で元のパスへ動かして作った。

### 5. 2 段の symlink

macOS:

```
[5] 2-level: bind OK; orig=socket mid=symlink top=symlink
[5] connect via top: OK
[5] getsockname len=75 raw=b'K\x01/.../sockat.s5top\x00'
```

Linux: `bind ERR errno=98(EADDRINUSE)`、`orig=なし(ENOENT)`。

### 6. `$TMPDIR` と `/tmp`

macOS の `$TMPDIR` はユーザーごとの `/var/folders/.../T/`。`/tmp` は `/private/tmp`。上の全場面で、どちらの置き場でも通る・通らないは同じだった (違うのは綴りの長さとカーネルが返す長さだけ)。

## 未確認

- FreeBSD・NetBSD・OpenBSD・illumos で辿るか (手元に無い)
- Linux のカーネルを複数 (docker の VM の 1 つしか見ていない)
- Linux で `/tmp` 以外の置き場、macOS の共有でも持ち主だけでもない置き場 (権限の違いによる差は見ていない)
- sockat-rs など実装側の API を通した動き (ここでは Python の標準ライブラリで素のシステムコールを見ただけ)
- 元のパスの最後の要素に bind の前から symlink が置かれていた場合 (責務の外としてイシューに記載済み)
- 片付けでの `unlink` の仕方 (どの綴りを消すと何が残るか) の方針は決めていない。この実験では symlink の `unlink` だけを確かめ、元のパスのソケットのファイルは macOS で残ることを見た
