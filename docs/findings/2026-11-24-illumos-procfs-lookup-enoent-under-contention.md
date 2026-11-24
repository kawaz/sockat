# illumos で `/proc/<pid>/fd/<fd>/…` を通す lookup が、並行の lookup で ENOENT になる

- Date: 2026-11-24 (測定日)

sockat-rs の試験を、CI と同じ OmniOS r151060 の image の VM (qemu の TCG) で繰り返したところ、`tests/public_api.rs` の `concurrent_calls_leave_the_cwd_alone` が、`sockat::bind` の `NotFound` (`ENOENT`) で落ちる事が多かった。
落ちた bind の綴りは procB の形 `/proc/<pid>/fd/<B の fd>/<D>/<E>/<名前>` で、その間に E も E の指す先も消されていなかった。
illumos の procfs のソースを読み、DTrace と `mdb` で確かめた。
CI の `EADDRINUSE` の失敗 ([別の findings](2026-11-24-illumos-unlink-before-close-eaddrinuse.md)) とは別の件。

## 判明した事実

### カーネルのソースで確かめた事

- `/proc/<pid>/fd/<n>` の lookup は `pr_lookup_fddir` が行い、その中で `pr_getf` がプロセスの fd の表から file を取る
- `pr_getf` は、file の参照の数を増やすために `mutex_tryenter(&fp->f_tlock)` を使う。取れなければやり直し、`pr_getf_maxtries` 回 (既定は 3) 取れなければ NULL を返す
- `pr_lookup_fddir` は、`pr_getf` が NULL なら NULL を返し、`prlookup` は NULL を `ENOENT` にする
- このため、同じ file (同じ fd) の `f_tlock` を他のスレッドが持っている間に 3 回続けて取れないと、fd がちゃんと開いていても lookup は `ENOENT` になる

### 実機で確かめた事 (OmniOS r151060、qemu の TCG、4 vCPU)

- sockat-rs (commit 50d1595) の `public_api` の試験を DTrace なしで 60 回流すと、22 回落ちた。末尾に見えた分は `tests/public_api.rs:315:53` の `NotFound` と、`tests/public_api.rs:356:5` (`long_path_errors_through_the_public_api` の errno の比較) だった
- 落ちた 1 回を DTrace で syscall ごとに記録した。`ENOENT` の bind の綴りの E は、同じ E を通る 1 つ前の bind が通ってから失敗するまでの間に、消されても作り直されてもいなかった。B の fd (4) と D の fd (7) の close も無かった
- `sdt:::pr_getf_tryfail` で、`pr_getf` が `pr_getf_maxtries` に達して諦めた回数を数えると、`/proc` を通る bind の `ENOENT` の回数と一致した (40 回中 1 回、200 回中 2 回)
- `mdb -kw` で `pr_getf_maxtries` を 1000 にすると、200 回で 0 回だった。その時 `mutex_tryenter` の試行は最大 257 回に達した
- `flock(LOCK_SH)` を持った fd と同じディレクトリを別の fd で開き、同じプロセスから `LOCK_EX|LOCK_NB` を掛けると拒まれた (open file description ごとのロック)。同じプロセスの `sweep` が自分の D を消す筋は無い

### 誇張と未測定

- qemu の TCG (x86_64 を arm64 の上で模倣) では、ロックを持つ時間が KVM や実機より長く、競合は誇張されている。1000 の設定で試行が 257 回に達したのはこのため
- CI の VM (KVM の上) での頻度は測っていない。sockat-rs の CI の illumos で、この形の失敗は見つけていない (確かめたのは 2026-11-18 以降の失敗した illumos の job のログ)
- `pr_getf_maxtries` を 1000 にした状態でも、重い DTrace (`attr.d`、別の findings) を当てた 200 回では `NotFound` で 2 回落ちた。その 2 回の原因は追っていない

### 影響する sockat-rs の版

- sockat-rs が置き場 B を `/proc/<pid>/fd/<B の fd>` で綴る (`proc_spelling`) のは v0.5.0 から。commit bf339c87 (v0.4.2) の `src/route.rs` に `proc_spelling` は無く、84e9d54a (v0.5.0)・251f7061 (v0.5.1)・6cf056c4 (v0.6.2) に有る
- v0.6.2 の `forms` は、`cross_uid` でなければ procB の形を B の実パスの形より先に置く

## 実用的な示唆

- illumos で、同じ fd を通る `/proc/<pid>/fd/<fd>/…` の lookup を多くのスレッドが同時に行うと、まれに `ENOENT` を受けうる。fd が開いていて、指す先が全部あっても起きる
- この `ENOENT` は、パスの上の何かが無い事を意味しない。同じ綴りでやり直せば通りうる (やり直しで通るかは測っていない)
- `pr_getf_maxtries` は `/etc/system` で変えられる値だが、利用者のシステムの設定を当てにする事は出来ない

## 検証の詳細

### 環境

[別の findings の「環境」と「VM の起こし方」](2026-11-24-illumos-unlink-before-close-eaddrinuse.md#環境) と同じ VM・同じ sockat-rs の build (`cargo test --workspace --no-run`、試験のバイナリは `/root/rs/target/debug/build/sockat/a20587fcc1249bad/out/public_api-a20587fcc1249bad`)。試験は root で流したので、B は `/tmp/sockat-0`。

### 判定のソース

illumos-gate の commit `7628d9650ab6469b56c1852eafce9b85631bf0f9`。OmniOS r151060 の illumos (`omniosorg/illumos-omnios` の branch r151060、commit `edb772c95084c0bcad18e7cf3bb68e827c4d4ee2`) の `pr_getf` は、この commit の物と同じ内容であることを diff で確かめた。`pr_getf_maxtries = 3` も同じ (r151060 の `prsubr.c` では 1582 行)。

- [prvnops.c 4295〜4367 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/fs/proc/prvnops.c#L4295-L4367): `pr_lookup_fddir`。4331 行で `pr_getf(p, fd, NULL)`、NULL なら 4346 行から NULL を返す
- [prvnops.c 3695〜3697 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/fs/proc/prvnops.c#L3695-L3697): `prlookup` は、lookup の関数が NULL を返せば `ENOENT`
- [prsubr.c 1575 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/fs/proc/prsubr.c#L1575): `int pr_getf_maxtries = 3;  /* So you can tune it from /etc/system */`
- [prsubr.c 1578〜1645 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/fs/proc/prsubr.c#L1578-L1645): `pr_getf`。1597 行の `mutex_tryenter(&fp->f_tlock)` が取れなければ 1617 行で `DTRACE_PROBE2(pr_getf_tryfail, file_t *, fp, int, tries)`、1634 行の `if (tries < pr_getf_maxtries)` でやり直す。fd の場所が空なら 1624 行の `pr_getf_emptyslot` で、やり直さない

`pr_getf` の、`f_tlock` を取る他の呼び手 (どの操作が同じ file の `f_tlock` を持つか) は、全部は読んでいない。

### 手順 1: 落ちた回の syscall を記録する

`enoent.d`:

```d
#pragma D option strsize=1100
#pragma D option bufsize=64m
#pragma D option switchrate=50hz
syscall::bind:entry /pid == $target/ { self->path = copyinstr(arg1 + 2); }
syscall::bind:return /pid == $target && self->path != NULL/ {
  printf("%d BIND errno=%d [%s] %s\n", timestamp, errno, curthread->t_name != NULL ? stringof(curthread->t_name) : "?", self->path);
  self->path = 0;
}
syscall::unlinkat:entry /pid == $target/ {
  printf("%d UNLINKAT fd=%d flags=%x [%s] %s\n", timestamp, arg0, arg2, curthread->t_name != NULL ? stringof(curthread->t_name) : "?", copyinstr(arg1));
}
syscall::renameat:entry /pid == $target/ {
  printf("%d RENAME [%s] %s -> %s\n", timestamp, curthread->t_name != NULL ? stringof(curthread->t_name) : "?", copyinstr(arg1), copyinstr(arg3));
}
syscall::symlinkat:entry /pid == $target/ {
  printf("%d SYMLINK fd=%d [%s] %s -> %s\n", timestamp, arg1, curthread->t_name != NULL ? stringof(curthread->t_name) : "?", copyinstr(arg2), copyinstr(arg0));
}
syscall::mkdirat:entry /pid == $target/ {
  printf("%d MKDIRAT fd=%d [%s] %s\n", timestamp, arg0, curthread->t_name != NULL ? stringof(curthread->t_name) : "?", copyinstr(arg1));
}
syscall::close:entry /pid == $target/ { printf("%d CLOSE fd=%d [%s]\n", timestamp, arg0, curthread->t_name != NULL ? stringof(curthread->t_name) : "?"); }
```

`enoent-loop.sh` (315 行で落ちるまで最大 40 回):

```sh
cd /root/rs
B=./target/debug/build/sockat/a20587fcc1249bad/out/public_api-a20587fcc1249bad
for i in $(seq 1 40); do
  dtrace -q -s /root/enoent.d -o /root/enoent.out -c "$B" > /root/run.out 2>&1
  if grep -q "315:53" /root/run.out; then echo "caught at run $i"; grep -E "panicked|code:" /root/run.out | head -3; exit 0; fi
done
echo "not caught"
```

`dtrace -o` は追記するので、落ちた回の分は、その回の最初の bind の時刻以降を `awk` で切り出して `last.out` にした。

### 手順 1 の出力

```
caught at run 5
thread '<unnamed>' (13) panicked at tests/public_api.rs:315:53:
called `Result::unwrap()` on an `Err` value: Os { code: 2, kind: NotFound, message: "No such file or directory" }
```

`last.out` (2908 行) の、E `23` と、その E が指すディレクトリ (`/tmp/srt-blt5py/…`) に関わる行。長い `d` の並びは先頭 8 文字の後を `…` に縮めた。左の番号は、E `23` を作った行を 1 とした行番号:

```
1:2070567564302 SYMLINK fd=7 [?] 23 -> /tmp/srt-blt5py/dddddddd…/dddddddd…/dddddddd…/dddddddd…/dddddddd…/dddddddd…/dddddddd…
6:2070568168432 BIND errno=0 [?] /proc/1247/fd/4/G0wgbhEJsN/23/13.sock
15:2070573425565 SYMLINK fd=4 [?] SZ4WKDo7e3 -> /tmp/srt-blt5py/dddddddd…/dddddddd…/dddddddd…/dddddddd…/dddddddd…/dddddddd…/dddddddd…/13.sock
51:2070584603974 SYMLINK fd=4 [?] c1xvKguZS1 -> /tmp/srt-blt5py/dddddddd…/…/14.soc
117:2070598154895 SYMLINK fd=4 [?] Q1Rgshyi9Y -> /tmp/srt-blt5py/dddddddd…/dddddddd…/15.sock
175:2070609088251 SYMLINK fd=4 [?] VQsOCnUSsE -> /tmp/srt-blt5py/dddddddd…/dddddddd…/dddddddd…/dddddddd…/16.sock
198:2070614081327 BIND errno=2 [?] /proc/1247/fd/4/G0wgbhEJsN/23/17.sock
```

- fd 4 は B (`/tmp/sockat-0`)、fd 7 は D (`G0wgbhEJsN`)。E の名前の `23`・`24`… は fd 7 に順に作られていた
- `fd=4` の `SYMLINK` は、connect の link-file が B の直下に作る E
- 13.sock と 17.sock は、同じスレッドの、同じ長さの round (同じディレクトリ)
- 1 行目から 198 行目の間の `UNLINKAT` は全部 `fd=4` の、B の直下の connect の E の片付けで、`23` を消す行は無かった。`RENAME` も無かった
- `last.out` の全体に、`CLOSE fd=4` と `CLOSE fd=7` は無かった

### 手順 2: `pr_getf` の諦めと ENOENT を数える

`getf.d`:

```d
sdt:::pr_getf_tryfail { @tryfail[arg1] = count(); }
sdt:::pr_getf_tryfail /arg1 >= `pr_getf_maxtries/ { @gaveup[execname] = count(); }
syscall::bind:entry { self->p = copyinstr(arg1 + 2); }
syscall::bind:return /self->p != NULL && errno == 2 && strstr(self->p, "/proc/") != NULL/ { @bind_enoent_via_proc = count(); }
syscall::bind:return { self->p = 0; }
```

`getf-loop.sh` (`vmloop.sh` は別の findings の手順 3 にある物):

```sh
cd /root/rs
B=./target/debug/build/sockat/a20587fcc1249bad/out/public_api-a20587fcc1249bad
dtrace -q -s /root/getf.d -o /root/getf.out & D=$!
sleep 4
sh /root/vmloop.sh "illumos ws whole (getf trace)" $B 40 | grep -E "runs|code:" | sort | uniq -c
kill -INT $D; sleep 2; cat /root/getf.out
```

非対話のシェルの背景のジョブは `SIGINT` を無視するので、`kill -INT` では dtrace は止まらなかった。後から `kill -TERM` で止めて集計を出した。

出力 (40 回、`pr_getf_maxtries` は既定の 3):

```
   1 called `Result::unwrap()` on an `Err` value: Os { code: 2, kind: NotFound, message: "No such file or directory" }
   1 illumos ws whole (getf trace): 40 runs, 1 failed
```

```
                2                1
                3                1
                1               47
  public_api-a2058                                                  1
                1
```

- 1 つ目の集計 (`@tryfail`、左が試行の回数): 1 回目で取れなかったのが 47、2 回目が 1、3 回目が 1
- 2 つ目 (`@gaveup`): 諦めたのは `public_api` で 1 回
- 3 つ目 (`@bind_enoent_via_proc`): `/proc` を通る bind の `ENOENT` が 1 回

### 手順 3: `pr_getf_maxtries` を変えて比べる

`getf2.d`:

```d
sdt:::pr_getf_tryfail { @maxtry = max(arg1); }
sdt:::pr_getf_tryfail /arg1 >= `pr_getf_maxtries/ { @gaveup = count(); }
sdt:::pr_getf_emptyslot { @emptyslot = count(); }
syscall::bind:entry { self->p = copyinstr(arg1 + 2); }
syscall::bind:return /self->p != NULL && errno == 2 && strstr(self->p, "/proc/") != NULL/ { @bind_enoent_via_proc = count(); printf("ENOENT %s\n", self->p); }
syscall::bind:return { self->p = 0; }
END { printa("max tries %@d\n", @maxtry); printa("gave up %@d\n", @gaveup); printa("empty slot %@d\n", @emptyslot); printa("bind ENOENT via /proc %@d\n", @bind_enoent_via_proc); }
```

`getf2-loop.sh`:

```sh
cd /root/rs
B=./target/debug/build/sockat/a20587fcc1249bad/out/public_api-a20587fcc1249bad
dtrace -q -s /root/getf2.d -o /root/getf2.out & D=$!
sleep 4
sh /root/vmloop.sh "illumos ws whole (getf2, maxtries=$(echo pr_getf_maxtries/D | mdb -k | tail -1 | awk '{print $2}'))" $B 60 | grep -E "runs|code:" | sort | uniq -c
kill -TERM $D; sleep 3; cat /root/getf2.out
```

`ab.sh` (`getf2-loop.sh` の回数を 200 に書き換えてから、1000 と 3 で 1 本ずつ):

```sh
for mt in 1000 3; do
  echo "pr_getf_maxtries/W 0t$mt" | mdb -kw >/dev/null
  sed -i "s/ 60 | grep/ 200 | grep/" /root/getf2-loop.sh
  sh /root/getf2-loop.sh
  echo ====
done
```

`mdb` で値を変える前の値:

```
pr_getf_maxtries:
pr_getf_maxtries:               3               
pr_getf_tryfails:
pr_getf_tryfails:               1000                 
pr_getf_maxtries:               0x3             =       0x3e8
pr_getf_maxtries:
pr_getf_maxtries:               1000
```

(`pr_getf_tryfails` は起動からの累計で、この時点で 1000。)

### 手順 3 の出力

`ab.sh` の前に、`pr_getf_maxtries` を 1000 にして `getf2-loop.sh` を 60 回で 1 本流した:

```
   1 illumos ws whole (getf2, maxtries=1000): 60 runs, 0 failed

max tries 1
```

`ab.sh` の出力。`dtrace -o` は同じファイルに追記するので、`cat` は前の回の `END` の出力も含む。各回の分は、新しく増えた行:

```
   1 illumos ws whole (getf2, maxtries=1000): 200 runs, 0 failed

max tries 1


max tries 257

====
   2 called `Result::unwrap()` on an `Err` value: Os { code: 2, kind: NotFound, message: "No such file or directory" }
   1 illumos ws whole (getf2, maxtries=3): 200 runs, 2 failed

max tries 1


max tries 257

ENOENT /proc/1893/fd/5/KCZJo0CQ3U/21/16.sock
ENOENT /proc/1949/fd/7/ReokkcC9uT/1w/11.sock

max tries 3
gave up 2
bind ENOENT via /proc 2

====
```

### 結果の表

| `pr_getf_maxtries` | DTrace | 回数 | `NotFound` で落ちた | `pr_getf` が諦めた | `/proc` を通る bind の `ENOENT` | `pr_getf_emptyslot` | 試行の最大 |
|---|---|---|---|---|---|---|---|
| 3 | なし | 60 | 22 (末尾に見えた分は 315 行と 356 行) | 測っていない | 測っていない | 測っていない | 測っていない |
| 3 | `getf.d` | 40 | 1 | 1 | 1 | 測っていない | 3 |
| 3 | `getf2.d` | 200 | 2 | 2 | 2 | 0 | 3 |
| 1000 | `getf2.d` | 60 | 0 | 0 | 0 | 0 | 1 |
| 1000 | `getf2.d` | 200 | 0 | 0 | 0 | 0 | 257 |
| 3 | `attr.d` (別の findings) | 150 | 39 (末尾に見えた分は 315 行) | 測っていない | 測っていない | 測っていない | 測っていない |
| 1000 | `attr.d` (別の findings) | 200 | 2 | 測っていない | 測っていない | 測っていない | 測っていない |

### 同じプロセスの `flock` の確かめ

```sh
python3 -I -c "
import os,fcntl,tempfile
d=tempfile.mkdtemp(dir=\"/tmp\")
a=os.open(d,os.O_RDONLY); b=os.open(d,os.O_RDONLY)
fcntl.flock(a,fcntl.LOCK_SH|fcntl.LOCK_NB)
try:
  fcntl.flock(b,fcntl.LOCK_EX|fcntl.LOCK_NB); print(\"exclusive on 2nd fd TAKEN (same process)\")
except OSError as e: print(\"exclusive on 2nd fd refused\", e)
"
```

```
exclusive on 2nd fd refused [Errno 11] Resource temporarily unavailable
```

## 推測 (確かめていない)

- 同じ B の fd の `f_tlock` を取り合っているのは、並行する他のスレッドの `/proc/<pid>/fd/<B の fd>` の lookup (それぞれが `pr_getf` で `f_tlock` を取る) と考えている。他にどの操作が同じ file の `f_tlock` を取るかは読んでいない
- KVM や実機では、ロックを持つ時間が短いので、頻度は TCG より低いと考えている。数は無い
- connect の link-file も B を procB の形で綴る場合は、同じく `ENOENT` を受けうると考えている。connect を `/proc` で通した回の数は取っていない

## 確かめられなかった事

- CI の VM (KVM) と illumos の実機での頻度
- `pr_getf_maxtries` が 1000 で `attr.d` を当てた 200 回の、`NotFound` の 2 回の原因
- DTrace なしの 60 回の 22 回のうち、末尾に見えなかった分の内訳。`tests/public_api.rs:356:5` (`long_path_errors_through_the_public_api`) で落ちた回の errno の中身
- 同じ綴りでやり直した時に通るか
- `pr_getf_tryfail` の数が、どのスレッドとどの fd の取り合いから出たか (`@tryfail` は file を区別していない)
- 他の illumos の配布物 (SmartOS、OpenIndiana 等)
