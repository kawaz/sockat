# CLI の置き場の fd と、消えた E の綴りの unlink

- Date: 2026-11-24 (測定日)

[DR-0018](../decisions/DR-0018-cli-resolve-with-reused-hashed-link.md) の未決と悪い面に残る 2 点を、実機で確かめた。

- A: 別のプロセスが開いたディレクトリの fd を、CLI の側が `/proc/<pid>/fd/<N>` で開いて置き場にできるか (Linux)
- B: 綴りの途中の E が消えた後、その綴りでの unlink と connect がどうなるか (Linux と macOS)

## 判明した事実

### A: `/proc/<pid>/fd/<N>` を置き場にできるか

- 同じ uid なら、別のプロセス (持ち主の子でも親でもない) が `/proc/<pid>/fd/9` を `O_RDONLY|O_DIRECTORY` で開け、その下に symlink を作れ (`symlinkat` もパスも)、綴り `/proc/<pid>/fd/9/<E>/<ソケットの名前>` (28 バイト) への bind・connect・unlink が通る。`hidepid` が 0・1・2 のどれでも同じ
- 別の uid は `open` の時点で失敗する。エラーは `hidepid=0` で `EACCES`、`hidepid=1` で `EPERM`、`hidepid=2` で `ENOENT` (`/proc/<pid>` 自体が見えない)
- root は `hidepid` によらず通る (3 通りとも)
- fd を持つシェルが終わると、`/proc/<pid>/fd/9` は `ENOENT` になり、同じ綴りへの bind も `ENOENT`
- ディレクトリの権限は、結果が権限に左右されないよう 777 にして測った。別の uid の失敗は、ディレクトリの権限でなく `/proc/<pid>/fd` の側の制限による

### B: E が消えた後の綴り

- E を消すと、その綴りでの unlink は `ENOENT` になり、元のパスのソケットのファイルが残る。Linux と macOS で同じ
- E が消えている間、listen 中のソケットへの綴りでの connect も `ENOENT` になる。Linux と macOS で同じ
- もう一度 `sockat <同じ長いパス>` を呼ぶと、同じ綴りが返り、E が作り直される。その後は connect も unlink も通り、ソケットのファイルも消える。Linux と macOS で同じ
- つまり DR-0018 の悪い面の「終了時の unlink が失敗してソケットのファイルが残りうる」は、E が消えれば実際に起きる。再び `sockat` を呼べば直せる

## 実用的な示唆 / ベストプラクティス

- `--base-fd` と `--base-pid` は、CLI が継いだ fd を持たなくても、同じ uid なら `/proc/<pid>/fd/<fd>` を自分で開いてディレクトリを掴める。親でないプロセスの fd も持ち主にできる。別の uid の持ち主は成り立たない
- 持ち主が終われば綴りが辿れなくなるのは、SPEC の `until: Process` のとおり
- E の消失に備えるなら、長く動くプログラムに渡した綴りが消えても、`sockat` を呼び直せば元に戻せる。プログラムが終了時に失敗した後でも、次に同じパスで `sockat` を呼べば E が戻り、綴りでの unlink が通る

## 検証の詳細

### 環境

| 項目 | 中身 |
|---|---|
| Linux | OrbStack の docker (Docker 29.8.2) の `rust:1` コンテナ (Debian GNU/Linux 13)。カーネル 7.2.12-orbstack-00394。Python 3.13.5。`rustc` は `rustc 1.100.0 (0ef1bc386 2026-11-09)` |
| Linux の sockat | `cargo install sockat-cli --version 0.6.2 --root <作業ディレクトリ>/linux-bin` で入れた 0.6.2 |
| macOS | macOS 26 (Darwin 25.5.0、arm64)。Python 3.15.2 |
| macOS の sockat | sockat-rs の作業コピーのデバッグビルド (`target/debug/sockat`、`--version` は 0.6.2) |
| 実験物の置き場 | `$TMPDIR` の下の `mktemp -d` のディレクトリ。コンテナは `--rm` |

### 指示と実物の違い

- `sockat --help-all` の出力に、DR-0018 と [cli.md](../design/cli.md) にある進んだオプション (`--base-fd`・`--base-pid`・`--route`) と `bind`・`connect` のサブコマンドが載っていない。0.6.2 は「手法の名指しと手法を試すサブコマンドは未着手」とあり、実装がまだのため。`--help` と `--help-all` の出力は同じだった
- A は CLI を使わず OS の振る舞いだけを測った。別の uid は `useradd` / `su` でなく、Python の `setuid` で数値の uid (1000 と 1001) に落とした子プロセスで試した
- macOS の B は、`$TMPDIR` が長くて置き場として使えなかった (`--base` が 103 バイトに収まらず `sockat` がエラー)。置き場だけ `/private/tmp/sk.<乱数>` の `mktemp -d` に置いた。共有の `/tmp/sockat-<uid>` は触っていない。長いパスのソケット側は `$TMPDIR` の下

### A の手順

`a.py` は root で動き、子プロセスを数値の uid に落として試す。持ち主 (uid 1000) は `sh -c 'exec 9<$BASE; echo $$; read x'` で、標準入力が閉じるまで fd 9 を持つ。`runA.sh` が `hidepid` を 0・2・1 の順に `mount -o remount` で変えて `a.py` を流す (`--privileged` のコンテナ)。

`runA.sh`:

```sh
set -u
uname -r; python3 -V; cat /etc/os-release | head -2; id
mount | grep ' /proc '
export PROCDIR=/proc
python3 /s/a.py /work/a0 hidepid=0
echo "=== remount hidepid=2"
mount -o remount,hidepid=2 /proc && mount | grep ' /proc '
python3 /s/a.py /work/a2 hidepid=2
echo "=== remount hidepid=1"
mount -o remount,hidepid=1 /proc && mount | grep ' /proc '
python3 /s/a.py /work/a1 hidepid=1
```

`a.py`:

```python
# 確かめる事 A: 別プロセスが開いたディレクトリの fd を /proc/<pid>/fd/<N> で開けるか
import os, sys, socket, subprocess, errno, time, shutil

ROOT = sys.argv[1]            # 作業ディレクトリ (コンテナの中)
HOLDER_UID = 1000
LABEL = sys.argv[2]           # 表の見出し (例 "hidepid=0")
BASE = os.path.join(ROOT, "base")
LONG = os.path.join(ROOT, *["d" * 60, "e" * 60, "f" * 60])   # 約 200 バイトの深さ
os.makedirs(LONG, exist_ok=True)
os.makedirs(BASE, exist_ok=True)
for p in (ROOT, BASE, os.path.join(ROOT, "d" * 60), os.path.join(ROOT, "d" * 60, "e" * 60), LONG):
    os.chmod(p, 0o777)        # 権限の違いで失敗が混ざらないよう全員に書き込みを許す
print(f"[{LABEL}] LONG bytes = {len(LONG.encode())}")

def clean_base():
    for n in os.listdir(BASE):
        os.unlink(os.path.join(BASE, n))
    for n in os.listdir(LONG):
        os.unlink(os.path.join(LONG, n))

def start_holder():
    # holder (uid 1000) のシェルが exec 9< で開いて、stdin が閉じるまで待つ
    def demote():
        os.setgid(HOLDER_UID); os.setuid(HOLDER_UID)
    p = subprocess.Popen(["sh", "-c", f"exec 9<{BASE}; echo $$; read x"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, preexec_fn=demote, text=True)
    pid = int(p.stdout.readline())
    return p, pid

def err(e):
    return f"{errno.errorcode.get(e.errno, e.errno)}"

def probe(uid, pid, tag, name):
    """子プロセスを uid に落として、各手順を試し、結果を行で返す"""
    r, w = os.pipe()
    cpid = os.fork()
    if cpid == 0:
        os.close(r)
        out = []
        def rec(step, fn):
            try:
                v = fn(); out.append(f"{step}: ok{(' ' + str(v)) if v is not None else ''}")
                return True
            except OSError as e:
                out.append(f"{step}: {err(e)}")
            except Exception as e:
                out.append(f"{step}: {type(e).__name__} {e}")
            return False
        if uid != 0:
            os.setgroups([]); os.setgid(uid); os.setuid(uid)
        proc = os.environ["PROCDIR"]
        fdp = f"{proc}/{pid}/fd/9"
        st = {}
        def open_dir():
            st["fd"] = os.open(fdp, os.O_RDONLY | os.O_DIRECTORY)
        ok_open = rec("open(O_RDONLY|O_DIRECTORY)", open_dir)
        # symlinkat 経由 (開けた時のみ)
        if ok_open:
            rec("symlinkat(dirfd)", lambda: os.symlink(LONG, "E-at-" + name, dir_fd=st["fd"]))
        # パス経由
        rec("symlink(path)", lambda: os.symlink(LONG, f"{fdp}/E-" + name))
        spell = f"{fdp}/E-{name}/s.sock"
        out.append(f"spelling bytes={len(spell.encode())}")
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        okb = rec("bind(spelling)", lambda: srv.bind(spell))
        if okb:
            srv.listen(1)
            rec("exists at long path", lambda: os.stat(os.path.join(LONG, "s.sock")).st_mode)
            c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            rec("connect(spelling)", lambda: c.connect(spell))
            # 綴りで unlink
            rec("unlink(spelling)", lambda: os.unlink(spell))
        os.write(w, ("\n".join(out)).encode())
        os._exit(0)
    os.close(w)
    data = b""
    while True:
        b = os.read(r, 4096)
        if not b: break
        data += b
    os.waitpid(cpid, 0)
    print(f"[{LABEL}] prober uid={uid} ({tag}) holder pid={pid}")
    for l in data.decode().splitlines():
        print("    " + l)

for uid, tag in ((1000, "same uid as holder"), (1001, "different uid"), (0, "root")):
    clean_base()
    hp, pid = start_holder()
    probe(uid, pid, tag, f"u{uid}")
    if uid == 1000:
        # holder 終了後
        try:
            hp.stdin.close(); hp.wait()
        except Exception: pass
        time.sleep(0.2)
        # 終了後に同じ pid の fd 9 を開く / 綴りで bind
        print(f"[{LABEL}] after holder exit (uid 1000 prober, pid={pid})")
        probe(1000, pid, "after holder exit", "after")
    else:
        hp.stdin.close(); hp.wait()
```

流し方: `docker run --rm --privileged -v <scripts>:/s -v <work>:/work rust:1 sh /s/runA.sh`

### A の出力

```
7.2.12-orbstack-00394-gbecdd6130068
Python 3.13.5
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
NAME="Debian GNU/Linux"
uid=0(root) gid=0(root) groups=0(root)
proc on /proc type proc (rw,nosuid,nodev,noexec,relatime)
[hidepid=0] LONG bytes = 191
[hidepid=0] prober uid=1000 (same uid as holder) holder pid=14
    open(O_RDONLY|O_DIRECTORY): ok
    symlinkat(dirfd): ok
    symlink(path): ok
    spelling bytes=28
    bind(spelling): ok
    exists at long path: ok 49663
    connect(spelling): ok
    unlink(spelling): ok
[hidepid=0] after holder exit (uid 1000 prober, pid=14)
[hidepid=0] prober uid=1000 (after holder exit) holder pid=14
    open(O_RDONLY|O_DIRECTORY): ENOENT
    symlink(path): ENOENT
    spelling bytes=28
    bind(spelling): ENOENT
[hidepid=0] prober uid=1001 (different uid) holder pid=17
    open(O_RDONLY|O_DIRECTORY): EACCES
    symlink(path): EACCES
    spelling bytes=28
    bind(spelling): EACCES
[hidepid=0] prober uid=0 (root) holder pid=19
    open(O_RDONLY|O_DIRECTORY): ok
    symlinkat(dirfd): ok
    symlink(path): ok
    spelling bytes=25
    bind(spelling): ok
    exists at long path: ok 49663
    connect(spelling): ok
    unlink(spelling): ok
=== remount hidepid=2
proc on /proc type proc (rw,nosuid,nodev,noexec,relatime,hidepid=invisible)
[hidepid=2] LONG bytes = 191
[hidepid=2] prober uid=1000 (same uid as holder) holder pid=25
    open(O_RDONLY|O_DIRECTORY): ok
    symlinkat(dirfd): ok
    symlink(path): ok
    spelling bytes=28
    bind(spelling): ok
    exists at long path: ok 49663
    connect(spelling): ok
    unlink(spelling): ok
[hidepid=2] after holder exit (uid 1000 prober, pid=25)
[hidepid=2] prober uid=1000 (after holder exit) holder pid=25
    open(O_RDONLY|O_DIRECTORY): ENOENT
    symlink(path): ENOENT
    spelling bytes=28
    bind(spelling): ENOENT
[hidepid=2] prober uid=1001 (different uid) holder pid=28
    open(O_RDONLY|O_DIRECTORY): ENOENT
    symlink(path): ENOENT
    spelling bytes=28
    bind(spelling): ENOENT
[hidepid=2] prober uid=0 (root) holder pid=30
    open(O_RDONLY|O_DIRECTORY): ok
    symlinkat(dirfd): ok
    symlink(path): ok
    spelling bytes=25
    bind(spelling): ok
    exists at long path: ok 49663
    connect(spelling): ok
    unlink(spelling): ok
=== remount hidepid=1
proc on /proc type proc (rw,nosuid,nodev,noexec,relatime,hidepid=noaccess)
[hidepid=1] LONG bytes = 191
[hidepid=1] prober uid=1000 (same uid as holder) holder pid=36
    open(O_RDONLY|O_DIRECTORY): ok
    symlinkat(dirfd): ok
    symlink(path): ok
    spelling bytes=28
    bind(spelling): ok
    exists at long path: ok 49663
    connect(spelling): ok
    unlink(spelling): ok
[hidepid=1] after holder exit (uid 1000 prober, pid=36)
[hidepid=1] prober uid=1000 (after holder exit) holder pid=36
    open(O_RDONLY|O_DIRECTORY): ENOENT
    symlink(path): ENOENT
    spelling bytes=28
    bind(spelling): ENOENT
[hidepid=1] prober uid=1001 (different uid) holder pid=39
    open(O_RDONLY|O_DIRECTORY): EPERM
    symlink(path): EPERM
    spelling bytes=28
    bind(spelling): EPERM
[hidepid=1] prober uid=0 (root) holder pid=41
    open(O_RDONLY|O_DIRECTORY): ok
    symlinkat(dirfd): ok
    symlink(path): ok
    spelling bytes=25
    bind(spelling): ok
    exists at long path: ok 49663
    connect(spelling): ok
    unlink(spelling): ok
```

### A の結果の表

行は試した相手、列は `hidepid` (`/proc` の mount オプション)。各セルは `open` → symlink 作成 → bind → connect → unlink の結果。

| 場面 | `hidepid=0` | `hidepid=1` (noaccess) | `hidepid=2` (invisible) |
|---|---|---|---|
| 同じ uid の別プロセス | 全部成功 | 全部成功 | 全部成功 |
| 別の uid | `open` が `EACCES` | `open` が `EPERM` | `open` が `ENOENT` |
| root | 全部成功 | 全部成功 | 全部成功 |
| 持ち主が終わった後 (同じ uid) | `open`・`symlink`・`bind` が `ENOENT` | 同じ | 同じ |

### B の手順

長いパス (ディレクトリ 195 バイト、ソケット込みで 204 バイト。macOS は 274・283 バイト) を決め、`sockat --base <置き場> <長いパス>` で綴りを得て、Python の `socket` で bind・listen する。E (置き場の直下のハッシュの名前の symlink) を `os.unlink` で消し、綴りでの connect と unlink を試す。次に `sockat` を呼び直して E が戻るかを見る。

`runB.sh` (Linux):

```sh
uname -sr; python3 -V; /out/bin/sockat --version
rm -rf /work/b; mkdir -p /work/b
python3 /s/b.py /out/bin/sockat /work/b
```

`b.py`:

```python
# 確かめる事 B: 綴りの途中の E が消えた後の unlink / connect
import os, sys, socket, subprocess, errno, json

SOCKAT, WORK = sys.argv[1], sys.argv[2]
BASE = sys.argv[3] if len(sys.argv) > 3 else os.path.join(WORK, "base")
LONGDIR = os.path.join(os.path.realpath(WORK), "long", *["d" * 60, "e" * 60, "f" * 60])
os.makedirs(LONGDIR, exist_ok=True)
LONGSOCK = os.path.join(LONGDIR, "app.sock")
print(f"dir bytes={len(LONGDIR.encode())} sockpath bytes={len(LONGSOCK.encode())}")

def e(ex): return errno.errorcode.get(ex.errno, str(ex.errno))
def resolve(*extra):
    r = subprocess.run([SOCKAT, "--base", BASE, *extra, LONGSOCK], capture_output=True, text=True)
    print(f"$ sockat --base $BASE {' '.join(extra)} <long>  -> rc={r.returncode} stdout={r.stdout.strip()!r} stderr={r.stderr.strip()!r}")
    return r.stdout.strip()

print("== 1. resolve")
sp = resolve()
resolve("--json")
print("spelling bytes =", len(sp.encode()))
print("== 2. bind + listen by spelling")
srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
srv.bind(sp); srv.listen(5)
print("long path socket exists:", os.path.exists(LONGSOCK), oct(os.stat(LONGSOCK).st_mode))
print("== control: connect via spelling while E exists")
c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); c.connect(sp); print("  ok"); c.close()
link = os.path.dirname(sp)
print("E =", link, "->", os.readlink(link))
print("== 3. remove E (the symlink)")
os.unlink(link)
print("E exists:", os.path.lexists(link))
print("== 6. connect via spelling while E is gone (server still listening)")
c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try: c.connect(sp); print("  connect ok")
except OSError as ex: print("  connect:", e(ex), ex)
print("  connect via original long path (cwd-relative short is not used) for contrast: skipped")
print("== 4. unlink via spelling while E is gone")
try: os.unlink(sp); print("  unlink ok")
except OSError as ex: print("  unlink:", e(ex), ex)
print("socket file at long path remains:", os.path.exists(LONGSOCK))
print("== 5. resolve again")
sp2 = resolve()
print("same spelling:", sp == sp2, "| E recreated:", os.path.islink(link), "->", os.readlink(link) if os.path.islink(link) else None)
print("== 5b. connect via spelling after re-resolve (server still listening)")
c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try: c.connect(sp); print("  connect ok")
except OSError as ex: print("  connect:", e(ex), ex)
c.close()
print("== 5c. unlink via spelling after re-resolve")
try: os.unlink(sp); print("  unlink ok")
except OSError as ex: print("  unlink:", e(ex), ex)
print("socket file at long path remains:", os.path.exists(LONGSOCK))
srv.close()
```

流し方:

- Linux: `docker run --rm -v <scripts>:/s -v <work>:/work -v <linux-bin>:/out rust:1 sh /s/runB.sh`
- macOS: `python3 b.py $SOCKAT_RS/target/debug/sockat <作業ディレクトリ> /private/tmp/sk.<乱数>/base`

### B の出力 (Linux)

```
Linux 7.2.12-orbstack-00394-gbecdd6130068
Python 3.13.5
sockat 0.6.2
dir bytes=195 sockpath bytes=204
== 1. resolve
$ sockat --base $BASE  <long>  -> rc=0 stdout='/work/b/base/559c5ca74f64/app.sock' stderr=''
$ sockat --base $BASE --json <long>  -> rc=0 stdout='{\n  "path": "/work/b/base/559c5ca74f64/app.sock",\n  "bytes": 34,\n  "limit": 107,\n  "original": "/work/b/long/dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff/app.sock",\n  "original_bytes": 204,\n  "route": "link-dir",\n  "link": "/work/b/base/559c5ca74f64",\n  "target": "/work/b/long/dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",\n  "for": ["bind", "connect"],\n  "warnings": []\n}' stderr=''
spelling bytes = 34
== 2. bind + listen by spelling
long path socket exists: True 0o140777
== control: connect via spelling while E exists
  ok
E = /work/b/base/559c5ca74f64 -> /work/b/long/dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
== 3. remove E (the symlink)
E exists: False
== 6. connect via spelling while E is gone (server still listening)
  connect: ENOENT [Errno 2] No such file or directory
  connect via original long path (cwd-relative short is not used) for contrast: skipped
== 4. unlink via spelling while E is gone
  unlink: ENOENT [Errno 2] No such file or directory: '/work/b/base/559c5ca74f64/app.sock'
socket file at long path remains: True
== 5. resolve again
$ sockat --base $BASE  <long>  -> rc=0 stdout='/work/b/base/559c5ca74f64/app.sock' stderr=''
same spelling: True | E recreated: True -> /work/b/long/dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
== 5b. connect via spelling after re-resolve (server still listening)
  connect ok
== 5c. unlink via spelling after re-resolve
  unlink ok
socket file at long path remains: False
```

### B の出力 (macOS)

```
dir bytes=274 sockpath bytes=283
== 1. resolve
$ sockat --base $BASE  <long>  -> rc=0 stdout='/private/tmp/sk.pGjGUa/base/8bce1e66381b/app.sock' stderr=''
$ sockat --base $BASE --json <long>  -> rc=0 stdout='{\n  "path": "/private/tmp/sk.pGjGUa/base/8bce1e66381b/app.sock",\n  "bytes": 49,\n  "limit": 103,\n  "original": "$TMPDIR/…/mac-b/long/dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff/app.sock",\n  "original_bytes": 283,\n  "route": "link-dir",\n  "link": "/private/tmp/sk.pGjGUa/base/8bce1e66381b",\n  "target": "$TMPDIR/…/mac-b/long/dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",\n  "for": ["bind", "connect"],\n  "warnings": []\n}' stderr=''
spelling bytes = 49
== 2. bind + listen by spelling
long path socket exists: True 0o140700
== control: connect via spelling while E exists
  ok
E = /private/tmp/sk.pGjGUa/base/8bce1e66381b -> $TMPDIR/…/mac-b/long/dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
== 3. remove E (the symlink)
E exists: False
== 6. connect via spelling while E is gone (server still listening)
  connect: ENOENT [Errno 2] No such file or directory
  connect via original long path (cwd-relative short is not used) for contrast: skipped
== 4. unlink via spelling while E is gone
  unlink: ENOENT [Errno 2] No such file or directory: '/private/tmp/sk.pGjGUa/base/8bce1e66381b/app.sock'
socket file at long path remains: True
== 5. resolve again
$ sockat --base $BASE  <long>  -> rc=0 stdout='/private/tmp/sk.pGjGUa/base/8bce1e66381b/app.sock' stderr=''
same spelling: True | E recreated: True -> $TMPDIR/…/mac-b/long/dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
== 5b. connect via spelling after re-resolve (server still listening)
  connect ok
== 5c. unlink via spelling after re-resolve
  unlink ok
socket file at long path remains: False
```

### B の結果の表

| 場面 | Linux | macOS |
|---|---|---|
| 綴りの長さ (上限) | 34 バイト (107) | 49 バイト (103) |
| 綴りで bind し、元の長いパスにソケットのファイルができる | できた | できた |
| E がある間の connect (対照) | 通った | 通った |
| E を消した後の connect (listen 中) | `ENOENT` | `ENOENT` |
| E を消した後の unlink | `ENOENT` | `ENOENT` |
| 上の unlink の後、元のパスのソケットのファイル | 残った | 残った |
| `sockat` を呼び直した時の綴り | 同じ | 同じ |
| 呼び直した後の E | 作り直された (同じ先を指す) | 作り直された (同じ先を指す) |
| 呼び直した後の connect | 通った | 通った |
| 呼び直した後の unlink | 通った (ソケットのファイルも消えた) | 通った (ソケットのファイルも消えた) |

## 確かめられなかったこと

- 持ち主の uid が違う場合の `CAP_SYS_PTRACE` 無しの root 相当 (capability を落とした root) は測っていない
- ユーザー名前空間・別の PID 名前空間 (別のコンテナ) をまたぐ場合は測っていない。DR-0018 の「同じ PID 名前空間」の条件は、この実験が同じコンテナ内だけだったため、この測定の外
- `sudo`・`setuid` 後や `dumpable` が 0 のプロセスが持ち主の場合は測っていない
- `hidepid` の `gid=` オプションは測っていない
- カーネルは OrbStack の 1 種類だけ。他のディストリビューションの標準のカーネルでは測っていない
- B は Linux と macOS の 1 台ずつ。OS の掃除そのもの (`tmpreaper`・macOS の `/tmp` の掃除) が E を消す挙動は再現せず、E は手で消した
- B の 6 (E が消えている間の connect) は、持ち主のソケットが listen 中の場合だけ測った
