# systemd-tmpfiles は使用中の symlink を消すか

- Date: 2026-11-24 (測定日)

[DR-0018](../decisions/DR-0018-cli-resolve-with-reused-hashed-link.md) の CLI は、置き場 B の直下に symlink E (ソケットのディレクトリを指す) を置いて使い回す。Linux の systemd-tmpfiles の掃除 (`q /tmp 1777 root root 10d`) が、辿られている E と、B を消すかを実機で確かめた。[調査](../research/2026-11-20-tmp-cleaners-and-persistent-base.md) に残っていた「symlink の age 掃除の実機の再現は無い」を答えで置き換える。

## 判明した事実

実測 (systemd 257.13、Linux 7.2.12) の結果。

- 古い symlink E (lstat の atime・mtime・ctime が全部 age より古い) は、`systemd-tmpfiles --clean` で消える。overlay、tmpfs、ext4 の全部で同じ
- 掃除は symlink の atime・mtime・ctime・btime (作成時刻) のどれか 1 つでも新しければ消さない。atime が新しいだけで、ctime が古くても残る
- E の atime が新しくなる使い方は、E を辿るパスの解決 (`connect`) と `readlink`。mount が `relatime` か `strictatime` なら更新され、E は残った。`noatime` なら更新されず、E は消えた
- E を辿って 1 回 `bind` しただけ (bind の後は触らない) では、E の atime は更新されなかった。listen 中のソケットがあっても E は消えた。ソケットのファイルが /tmp の外にあるので、`unix_socket_alive` の保護は E に及ばない
- `lstat` だけでは atime は更新されず、E は消えた
- E の時刻を新しくする手段は、`utimensat(AT_SYMLINK_NOFOLLOW)` (mtime と ctime も新しくなる) と作り直しで、どちらも掃除を避けられた。mount のオプションによらない
- `relatime` では、E が作られた直後の最初の辿りで atime が更新され、5 秒後の 2 回目の辿りでは更新されなかった。`strictatime` では 2 回目も更新された。24 時間より古い atime が更新される `relatime` の規則は確かめていない
- B は、古い空の B なら消える。E を消した掃除の同じ回で、空になった B も消えた。E が残る B は消えない
- B の配下に別のプロセスが `flock(LOCK_SH)` を掛けていると、掃除は B の中に降りず、古い E も消えない。2 回の掃除で同じだった
- 空の B の mtime を新しくすると、その回は消えず、age が過ぎた次の回で消えた

## 実用的な示唆

- E を使い回すだけの CLI は、`relatime` の既定の mount なら、E を辿る使用が age (10 日) より短い間隔であれば E の atime が更新され、E は消えない。ただし `noatime` の mount では辿っても更新されず、10 日で消える。消えた後は、同じパスで `sockat` を呼び直せば E が戻る ([前の findings](2026-11-24-cli-base-fd-and-vanished-link.md))
- 辿られていない E (作った後に `bind` を 1 回しただけ、`lstat` だけ) は、10 日で消える。ソケットが生きていても関係しない
- `noatime` でも確実に避けたいなら、E の時刻を `utimensat(AT_SYMLINK_NOFOLLOW)` で新しくするか、E を作り直す
- B は、E が残る間は消えない。B の flock を持ち続ける手は、B ごと掃除から外せる (Linux の systemd v242 以上の仕様どおり)

## 検証の詳細

### 環境

| 項目 | 中身 |
|---|---|
| コンテナ | OrbStack の docker (Docker 29.8.2) の `debian:stable` (`debian@sha256:a32b8984739287d78c4783b0825bdaaad187d157b16a98e0c0c5e5f2675d81fa`、Debian GNU/Linux 13 trixie) に `apt-get install systemd python3 e2fsprogs util-linux` を足した image |
| systemd | systemd 257 (257.13-1~deb13u1)。`systemd-tmpfiles --clean <設定ファイル>` を手で実行 (PID 1 は systemd でない) |
| カーネル | 7.2.12-orbstack-00394 |
| Python | 3.13.5 (標準ライブラリだけ) |
| 実物の設定 | `/usr/lib/tmpfiles.d/tmp.conf` は `q /tmp 1777 root root 10d` と `q /var/tmp 1777 root root 30d` |
| 試験用の設定 | `q /tmp 1777 root root 20s` (実物の行の age だけを 20 秒に変えた) |
| /tmp の種類 | overlay (relatime、コンテナの既定)、tmpfs (relatime)、tmpfs (noatime)、tmpfs (strictatime)、ext4 のループバック (relatime)、ext4 のループバック (noatime)。tmpfs と ext4 は `--privileged` のコンテナで `mount -t tmpfs` / `mount -o loop` して /tmp に重ねた |
| 実験物の置き場 | `$TMPDIR` の下の `mktemp -d` のディレクトリ (`s/` にスクリプト)。コンテナは `--rm` |

### 判定のソース

[systemd v257.13](https://github.com/systemd/systemd/tree/70b5d110be7702afc4dbce012f60d49506d513da) の `src/tmpfiles/tmpfiles.c` (コミット 70b5d110be7702afc4dbce012f60d49506d513da) を読んだ。

| 内容 | 場所 |
|---|---|
| 既定で見る時刻。ファイルは atime・btime・ctime・mtime の 4 つ、ディレクトリは ctime を除く 3 つ | [L128-L129](https://github.com/systemd/systemd/blob/70b5d110be7702afc4dbce012f60d49506d513da/src/tmpfiles/tmpfiles.c#L128-L129) |
| `needs_cleanup`。見る時刻のどれか 1 つでも cutoff 以上なら消さない | [L614-L666](https://github.com/systemd/systemd/blob/70b5d110be7702afc4dbce012f60d49506d513da/src/tmpfiles/tmpfiles.c#L614-L666) |
| 子を `statx(AT_SYMLINK_NOFOLLOW)` で見る (symlink は symlink 自身の時刻) | [L711-L716](https://github.com/systemd/systemd/blob/70b5d110be7702afc4dbce012f60d49506d513da/src/tmpfiles/tmpfiles.c#L711-L716) |
| ディレクトリに `flock(LOCK_EX|LOCK_NB)` して、取れなければ配下ごと飛ばす | [L801-L805](https://github.com/systemd/systemd/blob/70b5d110be7702afc4dbce012f60d49506d513da/src/tmpfiles/tmpfiles.c#L801-L805) |
| ディレクトリを `unlinkat(AT_REMOVEDIR)` し、`ENOTEMPTY` は無視 | [L831-L842](https://github.com/systemd/systemd/blob/70b5d110be7702afc4dbce012f60d49506d513da/src/tmpfiles/tmpfiles.c#L831-L842) |
| `unix_socket_alive` はソケットのファイル (`S_ISSOCK`) にだけ使う。symlink には使わない | [L865](https://github.com/systemd/systemd/blob/70b5d110be7702afc4dbce012f60d49506d513da/src/tmpfiles/tmpfiles.c#L865) |
| 通常のファイル・symlink に `needs_cleanup`。symlink は `O_NOFOLLOW` で開いて `ELOOP` になり、flock はしない | [L882-L897](https://github.com/systemd/systemd/blob/70b5d110be7702afc4dbce012f60d49506d513da/src/tmpfiles/tmpfiles.c#L882-L897) |

行番号は v257.13 のタグのファイルで確かめた。

### 手順

試験用の設定 `test.conf`:

```
q /tmp 1777 root root 20s
```

`exp.py` (全文)。場面ごとに B (`/tmp/B-<名前>`、0700) の中に E を作る。E の指す先 D (`/var/dd/<名前>`) は /tmp の外で、listen 中のソケットがある。作ってから 25 秒待って (E の 4 つの時刻が全部 20 秒より古くなる)、場面ごとの使い方をし、すぐ 1 回目の掃除。さらに 22 秒待って 2 回目の掃除 (使い方の後に 20 秒以上経つ)。

| 場面 | 使い方 |
|---|---|
| ctl | 何もしない (対照) |
| a | 作ってから 25 秒後に、綴り `B/E/s.sock` へ `connect` を 1 回 |
| a2 | a と同じ。5 秒後にもう 1 回 `connect` |
| b | 作った直後に、綴り `B/E/s.sock` で `bind` と listen。その後は触らない |
| c | 25 秒後に `readlink` |
| d | 25 秒後に `lstat` |
| e | 25 秒後に `os.utime(follow_symlinks=False)` (`utimensat(AT_SYMLINK_NOFOLLOW)`) |
| f | 25 秒後に E を消して作り直す |
| lock | E は未使用。B に `flock(LOCK_SH)` を掛け続ける |
| empty | 空の B。何もしない |
| etouch | 空の B。25 秒後に `os.utime` で B の mtime を新しくする |

```python
import os, socket, subprocess, sys, time

AGE = 20
T0 = time.time()
def rel(ns): return f"{ns/1e9 - T0:+7.2f}"
def lst(p):
    try:
        s = os.lstat(p)
    except FileNotFoundError:
        return "GONE"
    return f"a={rel(s.st_atime_ns)} m={rel(s.st_mtime_ns)} c={rel(s.st_ctime_ns)}"
def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True)

os.makedirs("/var/dd", exist_ok=True)
# 場面 -> (B, E, D)。D は /tmp の外 (掃除の対象外)
scen = ["ctl", "a", "a2", "b", "c", "d", "e", "f"]
extra = ["lock"]
servers = []
for n in scen:
    B = f"/tmp/B-{n}"; D = f"/var/dd/{n}"
    os.makedirs(D, exist_ok=True)
    os.mkdir(B, 0o700)
    os.symlink(D, f"{B}/E")
    s = socket.socket(socket.AF_UNIX)
    if n == "b":
        s.bind(f"{B}/E/s.sock")     # E を辿って bind (作った直後の 1 回)
    else:
        s.bind(f"{D}/s.sock")
    s.listen(5)
    servers.append(s)
os.mkdir("/tmp/B-empty", 0o700)
os.mkdir("/tmp/B-etouch", 0o700)
# flock の場面: E は未使用 (ctl と同じ) だが、B に LOCK_SH を掛け続ける
import fcntl
os.mkdir("/tmp/B-lock", 0o700); os.symlink("/var/dd/ctl", "/tmp/B-lock/E")
lockfd = os.open("/tmp/B-lock", os.O_RDONLY | os.O_DIRECTORY); fcntl.flock(lockfd, fcntl.LOCK_SH)
# E が消えて空になる場面ではなく、最初から空の B と、E を持たない古い B
t_create = time.time()
print(f"# fs: {sh('findmnt -T /tmp -no FSTYPE,OPTIONS').stdout.strip()}")
print("# 作成直後 (T0 からの相対秒)")
for n in scen: print(f"  E {n:4}", lst(f"/tmp/B-{n}/E"))
print("  B-empty", lst("/tmp/B-empty"))

time.sleep(AGE + 5)
print(f"# T0+{time.time()-T0:.0f}s: 使う前")
for n in scen: print(f"  E {n:4}", lst(f"/tmp/B-{n}/E"))

# 使う
def conn(n):
    c = socket.socket(socket.AF_UNIX); c.connect(f"/tmp/B-{n}/E/s.sock"); c.close()
os.utime("/tmp/B-etouch", None)
conn("a"); conn("a2")
os.readlink("/tmp/B-c/E")
os.lstat("/tmp/B-d/E")
os.utime("/tmp/B-e/E", None, follow_symlinks=False)         # utimensat(AT_SYMLINK_NOFOLLOW)
os.unlink("/tmp/B-f/E"); os.symlink("/var/dd/f", "/tmp/B-f/E")  # 作り直し
print(f"# T0+{time.time()-T0:.0f}s: 使った直後")
for n in scen: print(f"  E {n:4}", lst(f"/tmp/B-{n}/E"))
time.sleep(5)
conn("a2")                                                    # a2 は 5 秒後にもう一度
print(f"# T0+{time.time()-T0:.0f}s: a2 の 2 回目の後")
print("  E a2  ", lst("/tmp/B-a2/E"))

def clean(label):
    env = dict(os.environ, SYSTEMD_LOG_LEVEL="debug")
    r = subprocess.run(["systemd-tmpfiles", "--clean", "/s/test.conf"], env=env, capture_output=True, text=True)
    print(f"# T0+{time.time()-T0:.0f}s: {label}")
    for l in (r.stdout + r.stderr).splitlines():
        if "/tmp/B-" in l and ("Removing" in l or "lock" in l or "too new" in l or "Couldn" in l): print("   log|", l)
    print("   残った物:", sorted(x for x in os.listdir("/tmp") if x.startswith("B-")))
    for n in scen + extra:
        if os.path.isdir(f"/tmp/B-{n}"): print(f"  E {n:4}", lst(f"/tmp/B-{n}/E"))
clean("1 回目の掃除")
# 掃除後に消えた E への connect / 残った E の connect
for n in ["ctl", "a", "b"]:
    try: conn(n); print(f"  connect {n}: ok")
    except OSError as e: print(f"  connect {n}: {e}")
time.sleep(AGE + 2)
clean("2 回目の掃除 (最後の使用から 20 秒以上後)")
```

実行 (コンテナごとに /tmp を変える。ext4 は `-o loop,noatime` も):

```sh
docker run --rm --privileged -v $TMPDIR/s:/s sk-tmpfiles sh -c "python3 /s/exp.py"                      # overlay
docker run --rm --privileged -v $TMPDIR/s:/s sk-tmpfiles sh -c "mount -t tmpfs tmpfs /tmp && chmod 1777 /tmp; python3 /s/exp.py"   # tmpfs relatime
# tmpfs: -o noatime / -o strictatime も同様
docker run --rm --privileged -v $TMPDIR/s:/s sk-tmpfiles sh -c "truncate -s 64M /img && mkfs.ext4 -q /img && mount -o loop,relatime /img /tmp && chmod 1777 /tmp && python3 /s/exp.py"
```

### 出力 (overlay、relatime)

時刻は T0 (E を作った時) からの相対秒。`a` `m` `c` は lstat の atime・mtime・ctime。ログの行は `SYSTEMD_LOG_LEVEL=debug` の出力から、`/tmp/B-` を含む行だけ。`Removing directory` の行は rmdir を試す前に出るので、E が残る B では ENOTEMPTY で失敗して B は残る (「残った物」が実際の結果)。

```
# fs: overlay rw,relatime,lowerdir=…
# 作成直後 (T0 からの相対秒)
  E ctl  a=  +0.00 m=  +0.00 c=  +0.00
  E a    a=  +0.00 m=  +0.00 c=  +0.00
  E a2   a=  +0.00 m=  +0.00 c=  +0.00
  E b    a=  +0.00 m=  +0.00 c=  +0.00
  E c    a=  +0.00 m=  +0.00 c=  +0.00
  E d    a=  +0.00 m=  +0.00 c=  +0.00
  E e    a=  +0.00 m=  +0.00 c=  +0.00
  E f    a=  +0.00 m=  +0.00 c=  +0.00
  B-empty a=  +0.00 m=  +0.00 c=  +0.00
# T0+25s: 使う前
  E ctl  a=  +0.00 m=  +0.00 c=  +0.00
  E a    a=  +0.00 m=  +0.00 c=  +0.00
  E a2   a=  +0.00 m=  +0.00 c=  +0.00
  E b    a=  +0.00 m=  +0.00 c=  +0.00
  E c    a=  +0.00 m=  +0.00 c=  +0.00
  E d    a=  +0.00 m=  +0.00 c=  +0.00
  E e    a=  +0.00 m=  +0.00 c=  +0.00
  E f    a=  +0.00 m=  +0.00 c=  +0.00
# T0+25s: 使った直後
  E ctl  a=  +0.00 m=  +0.00 c=  +0.00
  E a    a= +25.01 m=  +0.00 c=  +0.00
  E a2   a= +25.01 m=  +0.00 c=  +0.00
  E b    a=  +0.00 m=  +0.00 c=  +0.00
  E c    a= +25.01 m=  +0.00 c=  +0.00
  E d    a=  +0.00 m=  +0.00 c=  +0.00
  E e    a= +25.01 m= +25.01 c= +25.01
  E f    a= +25.01 m= +25.01 c= +25.01
# T0+30s: a2 の 2 回目の後
  E a2   a= +25.01 m=  +0.00 c=  +0.00
# T0+30s: 1 回目の掃除
   log| Removing "/tmp/B-ctl/E"
   log| Removing directory "/tmp/B-ctl"
   log| File "/tmp/B-a/E": access time Tue 2026-11-24 09:31:34.391585 UTC is too new.
   log| Removing directory "/tmp/B-a"
   log| File "/tmp/B-a2/E": access time Tue 2026-11-24 09:31:34.391585 UTC is too new.
   log| Removing directory "/tmp/B-a2"
   log| Removing "/tmp/B-b/E"
   log| Removing directory "/tmp/B-b"
   log| File "/tmp/B-c/E": access time Tue 2026-11-24 09:31:34.391585 UTC is too new.
   log| Removing directory "/tmp/B-c"
   log| Removing "/tmp/B-d/E"
   log| Removing directory "/tmp/B-d"
   log| File "/tmp/B-e/E": modify time Tue 2026-11-24 09:31:34.391585 UTC is too new.
   log| Removing directory "/tmp/B-e"
   log| File "/tmp/B-f/E": modify time Tue 2026-11-24 09:31:34.391585 UTC is too new.
   log| Directory "/tmp/B-f": modify time Tue 2026-11-24 09:31:34.391585 UTC is too new.
   log| Removing directory "/tmp/B-empty"
   log| Directory "/tmp/B-etouch": modify time Tue 2026-11-24 09:31:34.391585 UTC is too new.
   log| Couldn't acquire shared BSD lock on directory "/tmp/B-lock", skipping: Resource temporarily unavailable
   残った物: ['B-a', 'B-a2', 'B-c', 'B-e', 'B-etouch', 'B-f', 'B-lock']
  E a    a= +25.01 m=  +0.00 c=  +0.00
  E a2   a= +25.01 m=  +0.00 c=  +0.00
  E c    a= +25.01 m=  +0.00 c=  +0.00
  E e    a= +25.01 m= +25.01 c= +25.01
  E f    a= +25.01 m= +25.01 c= +25.01
  E lock a=  +0.00 m=  +0.00 c=  +0.00
  connect ctl: [Errno 2] No such file or directory
  connect a: ok
  connect b: [Errno 2] No such file or directory
# T0+52s: 2 回目の掃除 (最後の使用から 20 秒以上後)
   log| Removing "/tmp/B-a/E"
   log| Removing directory "/tmp/B-a"
   log| Removing "/tmp/B-a2/E"
   log| Removing directory "/tmp/B-a2"
   log| Removing "/tmp/B-c/E"
   log| Removing directory "/tmp/B-c"
   log| Removing "/tmp/B-e/E"
   log| Removing directory "/tmp/B-e"
   log| Removing "/tmp/B-f/E"
   log| Removing directory "/tmp/B-f"
   log| Removing directory "/tmp/B-etouch"
   log| Couldn't acquire shared BSD lock on directory "/tmp/B-lock", skipping: Resource temporarily unavailable
   残った物: ['B-lock']
  E lock a=  +0.00 m=  +0.00 c=  +0.00
```

### 結果の表

E の atime が変わったか / 1 回目の掃除で E が消えたか (使った後は、E の ctime・mtime が古いまま)。

| 場面 | overlay relatime | tmpfs relatime | tmpfs strictatime | tmpfs noatime | ext4 relatime | ext4 noatime |
|---|---|---|---|---|---|---|
| ctl (何もしない) | 変わらず / 消えた | 変わらず / 消えた | 変わらず / 消えた | 変わらず / 消えた | 変わらず / 消えた | 変わらず / 消えた |
| a (connect) | 更新 / 残った | 更新 / 残った | 更新 / 残った | 変わらず / 消えた | 更新 / 残った | 変わらず / 消えた |
| a2 の 2 回目 (5 秒後) | 変わらず | 変わらず | 更新 | 変わらず | 変わらず | 変わらず |
| b (bind 1 回) | 変わらず / 消えた | 変わらず / 消えた | 変わらず / 消えた | 変わらず / 消えた | 変わらず / 消えた | 変わらず / 消えた |
| c (readlink) | 更新 / 残った | 更新 / 残った | 更新 / 残った | 変わらず / 消えた | 更新 / 残った | 変わらず / 消えた |
| d (lstat) | 変わらず / 消えた | 変わらず / 消えた | 変わらず / 消えた | 変わらず / 消えた | 変わらず / 消えた | 変わらず / 消えた |
| e (utimensat nofollow) | 3 つとも更新 / 残った | 同左 | 同左 | 同左 | 同左 | 同左 |
| f (作り直し) | 新しい物 / 残った | 同左 | 同左 | 同左 | 同左 | 同左 |

2 回目の掃除 (最後の使用から 20 秒以上後) では、a・a2・c・e・f の E も全部消えた (どの mount でも)。

B の側 (全 mount で同じ):

| 場面 | 1 回目 | 2 回目 |
|---|---|---|
| E が消えた B (ctl・b・d) | E と一緒に B も消えた | |
| E が残った B (a・a2・c・e・f) | 残った | E が消えた回に B も消えた |
| empty (古い空の B) | 消えた | |
| etouch (mtime を新しくした空の B) | 残った | 消えた |
| lock (B に LOCK_SH) | 残った。E も残った | 残った。E も残った |

「残った物」の一覧 (1 回目 / 2 回目):

- overlay: 1 回目 `['B-a', 'B-a2', 'B-c', 'B-e', 'B-etouch', 'B-f', 'B-lock']`、2 回目 `['B-lock']`
- tmpfs-default: 1 回目 `['B-a', 'B-a2', 'B-c', 'B-e', 'B-etouch', 'B-f', 'B-lock']`、2 回目 `['B-lock']`
- tmpfs-noatime: 1 回目 `['B-e', 'B-etouch', 'B-f', 'B-lock']`、2 回目 `['B-lock']`
- tmpfs-strictatime: 1 回目 `['B-a', 'B-a2', 'B-c', 'B-e', 'B-etouch', 'B-f', 'B-lock']`、2 回目 `['B-lock']`
- ext4-relatime: 1 回目 `['B-a', 'B-a2', 'B-c', 'B-e', 'B-etouch', 'B-f', 'B-lock']`、2 回目 `['B-lock']`
- ext4-noatime: 1 回目 `['B-e', 'B-etouch', 'B-f', 'B-lock']`、2 回目 `['B-lock']`

### 確かめられなかった事

- 実際の age (10 日) では試していない。age を 20 秒にして、E を 25 秒待って古くした。判定の式は同じ (cutoff = 今 - age)
- `touch -h` コマンドそのものは使っていない。同じ `utimensat(AT_SYMLINK_NOFOLLOW)` を Python の `os.utime(follow_symlinks=False)` で呼んだ
- `relatime` の「24 時間より古い atime は辿った時に更新される」規則は試していない (24 時間待てず、時計も変えていない)。E を 10 日の間に 24 時間おきより細かく使えば、その規則で atime が更新されると推測しているが、実測ではない
- 他の systemd の版 (v252 など古い版、v257 以外) と、systemd-tmpfiles-clean.timer からの実行、`tmp.mount` が tmpfs の実機は試していない。コンテナの PID 1 は systemd でない
- 他のファイルシステム (xfs・btrfs・NFS) と、`PrivateTmp` の /tmp は試していない
- `unix_socket_alive` は /tmp の中のソケットのファイルにだけ使われる (ソースで確認)。今回のソケットのファイルは /tmp の外なので、実測では E に及ばないことだけを見た
- `btime` が判定を決める場面は無かった (E の btime は作成時刻で、他の時刻より先に古くなる)
