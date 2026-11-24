# Linux で /proc/self/fd/<ディレクトリの fd>/<ファイル名> に bind した時の振る舞い

- Date: 2026-11-25 (測定日)

絶対パスが `sun_path` の上限 (108 バイト) を超える深いディレクトリの fd を開き、`/proc/self/fd/<fd>/s.sock` に Unix domain socket を bind した時の振る舞いを、Linux (docker のコンテナ) の実機で確かめた。

## 判明した事実

絶対パスが 262〜263 バイトのディレクトリ (50 文字のディレクトリ名を 5 段) で測った。fd の番号は 3 (10 の後半だけ 1000)。

| # | 項目 | 結果 |
|---|---|---|
| 1 | `/proc/self/fd/<fd>/s.sock` に `SOCK_STREAM` で bind・listen | 通る。ソケットのファイルは深いディレクトリの中にできる (`os.listdir` で `['s.sock']`、`S_ISSOCK` が真) |
| 2a | 別のプロセスが同じディレクトリを自分で開いて `/proc/self/fd/<自分の fd>/s.sock` で connect | 通る。1 往復できた |
| 2b | 別のプロセスが cwd をそのディレクトリに移して `./s.sock` で connect | 通る。1 往復できた |
| 3 | bind の直後にディレクトリの fd を閉じてから 2a・2b | どちらも通る。1 往復できた |
| 4 | `getsockname()` (bind した側) | fd を閉じる前も後も `'/proc/self/fd/3/s.sock'` (bind に渡した文字列そのまま) |
| 4 | `getpeername()` (connect した側) | 2a・2b、fd を閉じる前も後も `'/proc/self/fd/3/s.sock'` (listener が bind した文字列。connect に渡した文字列ではない。2b の `./s.sock` でも同じ) |
| 4 | accept した接続の `getsockname()` / `getpeername()` | `'/proc/self/fd/3/s.sock'` / `''` |
| 5 | `/proc/net/unix` | bind した文字列 `/proc/self/fd/3/s.sock` がパスの欄に出る。fd を閉じた後も同じ |
| 5 | `ss -xl` | `u_str LISTEN 0 5 /proc/self/fd/3/s.sock <inode> * 0`。fd を閉じた後も同じ |
| 6 | fd を開いたまま、bind した文字列で `os.unlink` | 通る。深いディレクトリの `s.sock` が消える |
| 7 | fd を閉じた後、同じ文字列で `os.unlink` | `FileNotFoundError` errno=2 (ENOENT)。深いディレクトリの `s.sock` は残る |
| 8 | fd を閉じ、別のディレクトリ (中に普通のファイル `s.sock`) を開いて同じ番号 3 を使い回させ、元の文字列で `os.unlink` | 通る。別のディレクトリの `s.sock` が消える。深いディレクトリの `s.sock` は残る |
| 9 | `SOCK_DGRAM` で bind | 通る。ソケットのファイルは深いディレクトリの中にできる。`getsockname()` は `'/proc/self/fd/3/s.sock'` |
| 10 | ファイル名の上限 | `/proc/self/fd/<fd>/` + ファイル名 の全体のバイト数で決まる。fd=3 (前置 16 バイト) では 91 バイトまで通り、92 バイトで通らない。fd=1000 (前置 19 バイト) では 88 バイトまで通り、89 バイトで通らない。どちらも全体が 107 バイトまで通り 108 バイトで落ちる。この落ち方は Python の `socket` 自身の検査 (`OSError: AF_UNIX path too long`、errno なし) による。カーネルは ctypes で直接 `bind(2)` した結果で、全体 108 バイトを NUL なし (addrlen = 2 + 108) なら通り、NUL 付き (addrlen = 2 + 108 + 1) や 109 バイトは `EINVAL` (errno 22) |
| 11a | 普通の形のコンテナ (`--pid=host` 無し) での 1 | 通る |
| 11b | `unshare --pid --fork --mount-proc` の中での 1 | 通る (`readlink /proc/self` が `1`。新しい pid namespace に入れている) |
| 11c | `unshare --mount` して `umount -l /proc` した状態 (`ls /proc` が空) での 1 | 通らない。`FileNotFoundError` errno=2 (ENOENT) |

6・7・8 から、bind したソケットのファイルを消す unlink は、bind に渡した文字列を bind の時のファイルシステム上の位置に結びつけて覚えていない。unlink の時点で `/proc/self/fd/<fd>` が何を指しているかで決まる。fd が閉じていれば ENOENT で何も消えず、同じ番号が別のディレクトリに使い回されていれば、そのディレクトリの同じ名前のファイルを消す。

## 実用的な示唆

- bind したソケットの `getsockname()`、`getpeername()` (相手側)、`/proc/net/unix`、`ss` には、深いディレクトリの実パスでなく、bind に渡した `/proc/self/fd/<fd>/<ファイル名>` の文字列がそのまま出る。この文字列は fd を閉じた後も変わらない
- fd を閉じた後でも、listener は接続を受け続け、別のプロセスは深いディレクトリを自分で開く (2a) か cwd を移す (2b) ことで繋げる
- bind に渡した文字列での unlink は、fd が開いている間だけ元のソケットのファイルを消す。閉じた後は ENOENT で何も消えず、fd の番号が別のディレクトリに使い回されていれば、そのディレクトリの同じ名前のファイルを消す
- `/proc` が mount されていない環境では、この形の bind は ENOENT で通らない
- ファイル名に付けられる長さは、`/proc/self/fd/<fd>/` を含めた全体で決まる。fd の番号の桁が増えるとその分だけ短くなる

## 検証の詳細

### 環境

| 項目 | 中身 |
|---|---|
| ホスト | macOS 26 (Darwin 25.5.0)、OrbStack の docker 29.8.2 |
| コンテナ | `python:3-slim` (Debian GNU/Linux 13 trixie、aarch64)、Python 3.15.2 |
| カーネル | 7.2.12-orbstack-00394 |
| ソケットを置いたファイルシステム | コンテナの `/tmp` (`stat -f -c %T /tmp` が `overlayfs`) |
| `ss` | `python:3-slim` には無い。5 は同じイメージで `apt-get install iproute2` した `ss` で測った |
| 実験物の置き場 | コンテナの `/tmp/w<pid>` の下 (スクリプトは `$TMPDIR/<mktemp -d>` から `-v …:/s` で渡した) |

### 指示と実物の違い

- 4 の `getpeername()` は connect に渡した文字列でなく、listener が bind した文字列が返った (指示は返った文字列を記録するだけなので、そのまま記録した)
- 10 の落ち方は、Python 自身の検査が先に働く。カーネルの上限は別に ctypes で測った (`k.py`)
- 11b の `--pid=host` 無し・`unshare` は `--privileged` のコンテナで測った。11a は `--privileged` 無しの普通の形
- 5 の `ss` は、`python:3-slim` には入っていないため `iproute2` を入れたコンテナで測った (そのため 5 の 1 回目の `ss` 出力は空だった)
- ソケットを置いたファイルシステムは overlayfs の 1 種類だけ。`-v` でマウントしたディレクトリ (bind mount、virtiofs 等) や tmpfs では測っていない

### 手順

```sh
W=$(mktemp -d)    # t.py と k.py を置く
docker run --rm -v $W:/s python:3-slim python3 -u /s/t.py main       # 1〜10
docker run --rm -v $W:/s python:3-slim sh -c 'apt-get update -qq >/dev/null 2>&1; apt-get install -y -qq iproute2 >/dev/null 2>&1; python3 -u /s/t.py main'   # 5 の ss
docker run --rm -v $W:/s python:3-slim python3 -u /s/k.py            # 10 のカーネルの上限
docker run --rm -v $W:/s python:3-slim python3 -u /s/t.py item1      # 11a
docker run --rm --privileged -v $W:/s python:3-slim sh -c 'unshare --pid --fork --mount-proc python3 -u /s/t.py item1'                     # 11b
docker run --rm --privileged -v $W:/s python:3-slim sh -c 'unshare --mount sh -c "umount -l /proc; ls /proc | head -3; python3 -u /s/t.py item1"'   # 11c
```

待ち合わせに sleep は使っていない。listener が listen した後に client の子プロセスを起こし、親が `accept` する (接続は backlog に積まれるので順序は問題ない)。

`t.py`:

```python
import os, socket, subprocess, sys, errno, stat

def deepdir(base):
    d = base
    for c in "abcde":
        d = os.path.join(d, c * 50)
    os.makedirs(d)
    return d

def err(e):
    return f"{type(e).__name__} errno={e.errno}({errno.errorcode.get(e.errno)}) {e}"

def client(mode, d, msg="ping"):
    # runs in child process
    if mode == "a":
        fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
        path = f"/proc/self/fd/{fd}/s.sock"
    else:
        os.chdir(d)
        path = "./s.sock"
    c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        c.connect(path)
    except OSError as e:
        print(f"  client[{mode}] connect({path}) FAIL {err(e)}"); return
    c.sendall(msg.encode())
    r = c.recv(100)
    print(f"  client[{mode}] connect({path}) OK echo={r!r} getpeername={c.getpeername()!r} getsockname={c.getsockname()!r}")

def roundtrip(srv, mode, d):
    p = subprocess.Popen([sys.executable, __file__, "client", mode, d], stdout=subprocess.PIPE, text=True)
    conn, _ = srv.accept()
    data = conn.recv(100)
    conn.sendall(data)
    print(f"  server accepted data={data!r} conn.getsockname={conn.getsockname()!r} conn.getpeername={conn.getpeername()!r}")
    conn.close()
    out = p.communicate()[0]
    print(out, end="")

def bind_listen(fd, name="s.sock", typ=socket.SOCK_STREAM):
    s = socket.socket(socket.AF_UNIX, typ)
    path = f"/proc/self/fd/{fd}/{name}"
    s.bind(path)
    if typ == socket.SOCK_STREAM:
        s.listen(5)
    return s, path

def item1_only(base):
    d = deepdir(base)
    print("deep dir len", len(d))
    fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
    try:
        s, path = bind_listen(fd)
        print("bind/listen OK", path, "exists in deep:", os.path.exists(os.path.join(d, "s.sock")), "isSock:", stat.S_ISSOCK(os.stat(os.path.join(d, "s.sock")).st_mode))
    except OSError as e:
        print("bind FAIL", err(e))

def main(base):
    d = deepdir(base)
    print("== env"); print("deep dir len", len(d)); print("path:", d)
    print("== 1")
    fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
    print("fd", fd)
    s, path = bind_listen(fd)
    print("bind/listen OK", path)
    f = os.path.join(d, "s.sock")
    print("exists in deep dir:", os.path.exists(f), "isSock:", stat.S_ISSOCK(os.stat(f).st_mode))
    print("ls deep:", os.listdir(d))
    print("== 4 (before close) getsockname:", repr(s.getsockname()))
    print("== 2a/2b (fd open)")
    roundtrip(s, "a", d); roundtrip(s, "b", d)
    print("== 5 /proc/net/unix + ss (fd open)")
    os.system("grep -n 's.sock' /proc/net/unix | cut -c1-400; echo ---; ss -xl 2>&1 | grep -E 's.sock|State' | cut -c1-400")
    print("== 3 close fd after bind")
    os.close(fd)
    print("== 4 (after close) getsockname:", repr(s.getsockname()))
    roundtrip(s, "a", d); roundtrip(s, "b", d)
    print("== 5 (after close)")
    os.system("grep -n 's.sock' /proc/net/unix | cut -c1-400; echo ---; ss -xl 2>&1 | grep -E 's.sock' | cut -c1-400")
    s.close(); os.unlink(f)

    print("== 6 unlink with fd open")
    fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
    s, path = bind_listen(fd)
    print("exists before:", os.path.exists(f))
    try:
        os.unlink(path); print("unlink OK")
    except OSError as e:
        print("unlink FAIL", err(e))
    print("exists after:", os.path.exists(f), os.listdir(d))
    s.close(); os.close(fd)

    print("== 7 unlink after fd closed")
    fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
    s, path = bind_listen(fd)
    os.close(fd)
    try:
        os.unlink(path); print("unlink OK")
    except OSError as e:
        print("unlink FAIL", err(e), "path:", path)
    print("deep s.sock still exists:", os.path.exists(f))
    s.close(); os.unlink(f)

    print("== 8 fd reuse")
    other = os.path.join(base, "other"); os.makedirs(other)
    with open(os.path.join(other, "s.sock"), "w") as fh: fh.write("regular")
    fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
    s, path = bind_listen(fd)
    print("bound via fd", fd, path)
    os.close(fd)
    fd2 = os.open(other, os.O_RDONLY | os.O_DIRECTORY)
    print("new fd", fd2, "same number:", fd2 == fd)
    print("before: other/s.sock exists:", os.path.exists(os.path.join(other, "s.sock")), " deep/s.sock exists:", os.path.exists(f))
    try:
        os.unlink(path); print("unlink OK (old string)")
    except OSError as e:
        print("unlink FAIL", err(e))
    print("after: other/s.sock exists:", os.path.exists(os.path.join(other, "s.sock")), " deep/s.sock exists:", os.path.exists(f))
    os.close(fd2); s.close()
    if os.path.exists(f): os.unlink(f)

    print("== 9 DGRAM")
    fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
    try:
        s, path = bind_listen(fd, typ=socket.SOCK_DGRAM)
        print("DGRAM bind OK", path, "exists:", os.path.exists(f), "getsockname:", repr(s.getsockname()))
        s.close(); os.unlink(f)
    except OSError as e:
        print("DGRAM bind FAIL", err(e))
    print("== 10 name length limit")
    for label, target in (("fd=%d" % fd, fd), ("fd=1000", None)):
        if target is None:
            os.dup2(fd, 1000); target = 1000
        prefix = f"/proc/self/fd/{target}/"
        last_ok = None; first_fail = None
        for n in range(1, 301):
            name = "n" * n
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                s.bind(prefix + name)
                last_ok = n
                os.unlink(name, dir_fd=fd)
            except OSError as e:
                if first_fail is None:
                    first_fail = (n, err(e), len(prefix + name))
                    break
            finally:
                s.close()
        print(f"{label} prefix={prefix!r} (len {len(prefix)}) longest ok name={last_ok} (path len {len(prefix)+last_ok}) first fail={first_fail}")
    # beyond: all failures categories
    prefix = f"/proc/self/fd/{fd}/"
    for n in (100, 107 - len(prefix), 108 - len(prefix), 109 - len(prefix), 200, 255, 256):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.bind(prefix + "m" * n); print(f"  name len {n} (path {len(prefix)+n}): OK"); os.unlink("m" * n, dir_fd=fd)
        except OSError as e:
            print(f"  name len {n} (path {len(prefix)+n}): {err(e)}")
        s.close()

if __name__ == "__main__":
    if sys.argv[1] == "client":
        client(sys.argv[2], sys.argv[3])
    else:
        base = os.path.join("/tmp", "w" + str(os.getpid())); os.makedirs(base)
        if sys.argv[1] == "item1": item1_only(base)
        else: main(base)
```

`k.py` (10 のカーネルの上限):

```python
import os, ctypes, socket, errno
libc = ctypes.CDLL(None, use_errno=True)
d = "/tmp/kd"; os.makedirs(d)
fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
prefix = f"/proc/self/fd/{fd}/"
for total in (107, 108, 109):
    name = "k" * (total - len(prefix))
    path = (prefix + name).encode()
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    # struct sockaddr_un: sa_family(2) + sun_path(108)
    for alen_extra, label in ((0, "no NUL (addrlen=2+len)"), (1, "with NUL (addrlen=2+len+1)")):
        buf = ctypes.create_string_buffer(2 + max(len(path)+1, 108))
        ctypes.memmove(buf, (1).to_bytes(2, "little"), 2)
        ctypes.memmove(ctypes.addressof(buf)+2, path, len(path))
        alen = 2 + len(path) + alen_extra
        r = libc.bind(s.fileno(), buf, alen)
        e = ctypes.get_errno()
        print(f"path len {len(path)} {label}: bind ret={r} errno={e}({errno.errorcode.get(e)})")
        if r == 0:
            print("  created:", os.listdir(d)); os.unlink(name, dir_fd=fd)
            s.close(); s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
```

### 決め手になった実出力

6・7・8 (`t.py main`):

```
== 6 unlink with fd open
exists before: True
unlink OK
exists after: False []
== 7 unlink after fd closed
unlink FAIL FileNotFoundError errno=2(ENOENT) [Errno 2] No such file or directory: '/proc/self/fd/3/s.sock' path: /proc/self/fd/3/s.sock
deep s.sock still exists: True
== 8 fd reuse
bound via fd 3 /proc/self/fd/3/s.sock
new fd 3 same number: True
before: other/s.sock exists: True  deep/s.sock exists: True
unlink OK (old string)
after: other/s.sock exists: False  deep/s.sock exists: True
```

1〜4 (fd を開いたまま / 閉じた後):

```
== 1
fd 3
bind/listen OK /proc/self/fd/3/s.sock
exists in deep dir: True isSock: True
ls deep: ['s.sock']
== 4 (before close) getsockname: '/proc/self/fd/3/s.sock'
== 2a/2b (fd open)
  server accepted data=b'ping' conn.getsockname='/proc/self/fd/3/s.sock' conn.getpeername=''
  client[a] connect(/proc/self/fd/3/s.sock) OK echo=b'ping' getpeername='/proc/self/fd/3/s.sock' getsockname=''
  server accepted data=b'ping' conn.getsockname='/proc/self/fd/3/s.sock' conn.getpeername=''
  client[b] connect(./s.sock) OK echo=b'ping' getpeername='/proc/self/fd/3/s.sock' getsockname=''
== 3 close fd after bind
== 4 (after close) getsockname: '/proc/self/fd/3/s.sock'
  (2a・2b とも上と同じ出力)
```

5 (`ss` を入れたコンテナ。fd を開いたまま・閉じた後とも同じ):

```
2:000000004080b3ba: 00000002 00000000 00010000 0001 01 7951209 /proc/self/fd/3/s.sock
Netid State  Recv-Q Send-Q          Local Address:Port    Peer Address:Port
u_str LISTEN 0      5      /proc/self/fd/3/s.sock 7951209            * 0
```

9・10:

```
== 9 DGRAM
DGRAM bind OK /proc/self/fd/3/s.sock exists: True getsockname: '/proc/self/fd/3/s.sock'
== 10 name length limit
fd=3 prefix='/proc/self/fd/3/' (len 16) longest ok name=91 (path len 107) first fail=(92, 'OSError errno=None(None) AF_UNIX path too long', 108)
fd=1000 prefix='/proc/self/fd/1000/' (len 19) longest ok name=88 (path len 107) first fail=(89, 'OSError errno=None(None) AF_UNIX path too long', 108)
```

10 のカーネルの上限 (`k.py`):

```
path len 107 no NUL (addrlen=2+len): bind ret=0 errno=0(None)
path len 107 with NUL (addrlen=2+len+1): bind ret=0 errno=0(None)
path len 108 no NUL (addrlen=2+len): bind ret=0 errno=0(None)
path len 108 with NUL (addrlen=2+len+1): bind ret=-1 errno=22(EINVAL)
path len 109 no NUL (addrlen=2+len): bind ret=-1 errno=22(EINVAL)
path len 109 with NUL (addrlen=2+len+1): bind ret=-1 errno=22(EINVAL)
```

11 (`t.py item1`):

```
11a  bind/listen OK /proc/self/fd/3/s.sock exists in deep: True isSock: True
11b  bind/listen OK /proc/self/fd/3/s.sock exists in deep: True isSock: True   (readlink /proc/self が 1)
11c  (ls /proc が空)  bind FAIL FileNotFoundError errno=2 [Errno 2] No such file or directory
```

## 未確認

- Linux 以外 (macOS・BSD 系には `/proc/self/fd` が無い)
- overlayfs 以外のファイルシステム (`-v` の bind mount、tmpfs、ext4 等)
- 別のカーネルの版・ディストリビューション・Python 以外の言語 (C の `bind(2)` の直接呼びは 10 の上限の確認だけ)
- 10 の `NAME_MAX` (255) 側の上限。全体が 108 バイトで先に止まるため、`/proc/self/fd/<fd>/` 経由では届かない
- 11c で `/proc` を mount せずに bind できる別の手段
- 2 の接続が listener の側にとって別 uid・別の user namespace・別の mount namespace からだった場合
- ディレクトリの fd を `O_PATH` で開いた場合
