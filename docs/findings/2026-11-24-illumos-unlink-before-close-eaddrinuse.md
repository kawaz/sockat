# illumos でソケットのファイルを unlink してから閉じると、無関係な bind が EADDRINUSE になる

- Date: 2026-11-24 (測定日)

sockat-rs の CI (illumos、OmniOS r151060 の VM) で、`tests/public_api.rs` の `concurrent_calls_leave_the_cwd_alone` が、新しい名前への `sockat::bind` で `EADDRINUSE` を受けて落ちた (run 45376995896、job 138385814665、commit 50d1595)。
パスは試験ごと・スレッドごと・round ごとに別で、パスの重なりでは説明できない。
illumos のカーネルのソースを読み、CI と同じ image の VM で再現と DTrace による観測をした。

## 判明した事実

### カーネルのソースで確かめた事

- illumos の AF_UNIX のソケットは、bind したソケットのファイルの vnode のポインタの値を、tl ドライバ (カーネル内の宛先の管理) に渡す「アドレス」に使う
- tl は、既に表にあるアドレスへの bind を `TADDRBUSY` で拒む。sockfs はそれを `EADDRINUSE` に変えて返す
- `sotpi_close` は、ソケットのファイルの vnode への参照を手放してから (`vn_rele_stream`)、`strclose` を呼ぶ。tl の表からアドレスを外す `tl_addr_unbind` は、`strclose` から呼ばれる `tl_close` の中で動く
- tmpfs は、最後の参照が手放され、かつリンク数が 0 の時だけ vnode を解放する (`tmp_inactive`)
- このため、ソケットのファイルを unlink してから閉じると、閉じる途中で vnode が解放され、そのアドレスはまだ tl の表に残っている。この間に別のスレッドやプロセスが作るファイルの vnode が同じアドレスになると、その bind は `TADDRBUSY` になりうる
- 閉じてから unlink する順と、ファイルを残して閉じる順では、閉じる時点でリンク数が残っているので、`sotpi_close` の中で vnode は解放されない。`tl_close` は `tl_close_ser` (アドレスを外す処理) の終わりを待ってから戻る
- 衝突にパスの重なりは要らない。システムのどこで作ったソケットのファイルでも、vnode のアドレスが同じなら衝突しうる
- `sotpi_bind` は、`vn_create` でソケットのファイルを作ってから tl に bind を頼む。tl が拒んでも、作ったファイルは消さない

### 実機で確かめた事 (OmniOS r151060、qemu の TCG)

- Python の再現 (`race.py`) で、unlink してから閉じる側を回しながら、新しい名前に bind すると、`EADDRINUSE` が 300 秒で 10 回出た (DTrace を当てた状態)
- 10 回とも、失敗した bind のパスにソケットのファイルが残っていた。bind の前の `lstat` では何も無かった
- 同じ時間帯に DTrace (`window.d`) で、`sotpi_close` の中で解放された vnode のアドレスが、`tl_addr_unbind` より前に `vn_alloc` から再び返る事象を 12 回数えた。run ごとに、この事象の数は `EADDRINUSE` の数以上だった
- 閉じてから unlink する順 (280 秒)、ファイルを残して閉じる順 (40 秒)、ハードリンクで名前を 1 つ残して unlink してから閉じる順 (120 秒) では、`EADDRINUSE` は 0 回、`sotpi_close` の中の vnode の解放も 0 回だった (いずれも DTrace を当てた状態)
- DTrace を当てない状態では、unlink してから閉じる順でも 110 秒で 0 回だった
- sockat-rs の試験そのものを VM で 300 回回すと (DTrace を当て、下の `pr_getf_maxtries` を 1000 にした状態)、1 回、CI と同じ形 (`tests/public_api.rs:315:53` で `EADDRINUSE`) で落ちた
- 別の 200 回では、Rust の `std` の `UnixListener::bind` (`std_drops_last_byte` の中) が `EADDRINUSE` で落ちた。その直前に、同じプロセスの `bind_ex_returns_the_socket_file_and_the_spelling` のスレッドが閉じて解放した vnode が、そのスレッドに `vn_alloc` から返っていた

### macOS と Linux

- macOS と Linux (docker) では、同じ Python の再現で、どの順番でも `EADDRINUSE` は 0 回だった
- sockat-rs の公開 API の試験を、macOS と Linux でそれぞれ 1000 回 (下の表の内訳) 回して、失敗は 0 回だった

### 試験の側の引き金

`tests/public_api.rs` の次の試験は、ソケットを開いたまま、そのソケットのファイルを消してから閉じる (commit 50d1595 の時点)。

- `bind_ex_returns_the_socket_file_and_the_spelling` (`bound.file.remove()` の後、関数の終わりで `bound.socket` を閉じる)
- `default_binds_in_one_directory_share_their_e` (`ex.file.remove()` の後、関数の終わりで `ex.socket` を閉じる)
- `resolved_spellings_go_to_std` (`file.remove()` の後、関数の終わりで `listener` を閉じる)
- `sweep_keeps_this_processs_d` (`bound.file.remove()` の後、関数の終わりで `bound.socket` を閉じる)
- `datagrams_at_long_paths` (`SOCK_DGRAM`。tl の表は、ストリームと DGRAM の socket の transport で別に作られる)

VM の DTrace (`attr.d`) で見た vnode の再利用は、どれも上の 4 つのストリームの試験のスレッドが閉じた時に解放された vnode だった。

### 過去の CI

- 2026-11-18 の run 44225797996 (job 134538538399、commit a18fba57、Release v0.2.4) の illumos で、同じ試験が同じ形で落ちている: `thread '<unnamed>' (12) panicked at tests/public_api.rs:276:53` / `Os { code: 125, kind: AddrInUse, message: "Address already in use" }`
- その時の `tests/public_api.rs` では、`bind_and_connect_work_at_any_length` と `a_short_path_behaves_exactly_like_std` が、listener を開いたまま `std::fs::remove_file` してから閉じていた
- sockat-rs の commit 19dc4fd (2026-11-18) が、この 2 つの試験を「閉じてから消す」順に変えた。commit message は「illumos では unlink の後に close すると、並行する別の試験の bind が EADDRINUSE になりうる (カーネルの競合、std の bind でも同じ)」
- 上の「試験の側の引き金」の試験は、sockat-rs の commit 3962477 (2026-11-21) で入った
- 2026-11-18 の時点の sockat-rs は、置き場 B・D・E を使う経路 (procB を含む) をまだ持っていない。`proc_spelling` は commit bf339c87 (v0.4.2) に無く、84e9d54a (v0.5.0) に有る

## 実用的な示唆

- illumos では、ソケットのファイルを unlink してから閉じる順は、同じシステムで同時に走る無関係な bind を、まれに `EADDRINUSE` で失敗させうる。言語やライブラリによらない
- 失敗した bind のパスには、カーネルが作ったソケットのファイルが残る。そのパスへ同じ bind をやり直すと、今度はファイルがあるための `EADDRINUSE` になる
- 閉じてから unlink する順なら、この窓は開かない。開いたままの unlink が要る場面では、別の名前のハードリンクを閉じた後まで残すと、Python の再現では窓が開かなかった
- [SPEC の `remove`](../SPEC-ja.md#remove) は「`remove` は listener を閉じる前に呼ぶ」ことを勧めている ([inode 番号の使い回しの findings](2026-11-19-inode-reuse-after-close.md))。その順は、illumos ではこの窓を開く順でもある

## 検証の詳細

### 環境

| 項目 | 中身 |
|---|---|
| ホスト | macOS 26 (Darwin 25.5.0、arm64)。QEMU 11.1.2 |
| illumos の VM | anyvm-org/omnios-builder v2.1.4 の `omnios-r151060.qcow2` (CI の vmactions/omnios-vm と同じ builder の版と release)。`uname -a` は `SunOS omnios 5.11 omnios-r151060-513bc64de92 i86pc i386 i86pc`。qemu の TCG (x86_64 を arm64 の上で模倣)、4 vCPU、6 GB。qemu のプロセスは負荷の下で 371% の CPU を使った (複数スレッドの TCG) |
| VM の `/tmp` | tmpfs (`df -n /tmp`) |
| VM の Python | 3.13.16 (`/usr/bin/python3`) |
| VM の Rust | `pkg install ooce/developer/rust build-essential` で入れた `rustc 1.100.0 (0ef1bc386 2026-11-09) (OmniOS/151060)` |
| VM の sockat-rs | commit 50d1595 (v0.6.4) を `git archive` で写した木。`cargo test --workspace --no-run` で build (TCG で 4 分 51 秒) |
| Linux | OrbStack の docker の `rust:1` コンテナ (Debian GNU/Linux 13)。カーネル 7.2.12-orbstack-00394。Python 3.13.5。`rustc 1.100.0 (0ef1bc386 2026-11-09)` |
| macOS の Python | `python3` (3.15.2) |
| CI の VM | vmactions/omnios-vm@v1、AnyVM 0.7.5、builder 2.1.4、`Target OS: omnios, Release: r151060`、`mem: 6144`、ホストの KVM の上 (ログの `Nested AMD KVM detected`)。vCPU の数はログに無い |
| 実験物の置き場 | ホストは `$TMPDIR` の下。VM は `/root` と `/tmp` |

### 判定のソース

illumos-gate の commit `7628d9650ab6469b56c1852eafce9b85631bf0f9`。OmniOS r151060 の illumos (`omniosorg/illumos-omnios` の branch r151060、commit `edb772c95084c0bcad18e7cf3bb68e827c4d4ee2`) の `socktpi.c`・`tl.c` は、この commit の物と同じ内容であることを `cmp` で確かめた。`tmp_vnops.c` はファイルとしては違うが、`tmp_inactive` の関数は同じ内容だった。

- [socktpi.c 962〜967 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/fs/sockfs/socktpi.c#L962-L967): `sotpi_bindlisten` (`sotpi_bind` の 1337 行から呼ばれる) が `vn_create(..., EXCL, ...)` でソケットのファイルを作る。`EEXIST` は `EADDRINUSE` にする
- [socktpi.c 995〜997 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/fs/sockfs/socktpi.c#L995-L997): `sti->sti_ux_laddr.soua_vp = (void *)sti->sti_ux_bound_vp;` と `SOU_MAGIC_EXPLICIT`。vnode のポインタの値を tl へのアドレスにする
- [socktpi.c 1234〜1243 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/fs/sockfs/socktpi.c#L1234-L1243): tl が返したアドレスが頼んだ物と違えば `EADDRINUSE`。この経路でも、上で作ったファイルを消す処理は無い
- [sockstr.c 984 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/fs/sockfs/sockstr.c#L984) と [proto_set.c 257 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/inet/proto_set.c#L257): `T_ERROR_ACK` の `TADDRBUSY` は `EADDRINUSE` になる
- [socktpi.c 5602〜5642 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/fs/sockfs/socktpi.c#L5602-L5642): `sotpi_close`。5639 行の `vn_rele_stream(ux_vp)` が 5641 行の `strclose(vp, flag, cr)` より先
- [tl.c 2599〜2616 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/io/tl.c#L2599-L2616): `tl_bind` が `mod_hash_insert_reserve(tep->te_addrhash, (mod_hash_key_t)ux_addr.soua_vp, ...)` に失敗すると `TADDRBUSY`
- [tl.c 1600〜1650 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/io/tl.c#L1600-L1650): `tl_close` は `tl_serializer_enter(tep, tl_close_ser, ...)` の後、`te_closewait` が下りるまで待つ
- [tl.c 1712〜1729 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/io/tl.c#L1712-L1729): `tl_close_ser` が `tl_addr_unbind(tep)` を呼ぶ
- [tl.c 6388〜6409 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/io/tl.c#L6388-L6409): `tl_addr_unbind` が表から `tep->te_vp` (578 行で `te_uxaddr.soua_vp`) を外す
- [tl.c 1069〜1075 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/io/tl.c#L1069-L1075): ストリームの 2 つの socket の transport (`sticots`・`sticotsord`) は同じ表を共有する。DGRAM (`sticlts`) は別の表
- [tmp_vnops.c 1664〜1743 行](https://github.com/illumos/illumos-gate/blob/7628d9650ab6469b56c1852eafce9b85631bf0f9/usr/src/uts/common/fs/tmpfs/tmp_vnops.c#L1664-L1743): `tmp_inactive`。1679 行の `if (vp->v_count > 1 || tp->tn_nlink != 0)` なら参照を減らすだけ。そうでなければ 1741 行の `vn_free(TNTOV(tp))`

### VM の起こし方

ホストで:

```sh
mkdir -p "$TMPDIR/omnios" && cd "$TMPDIR/omnios"
gh release download v2.1.4 -R anyvm-org/omnios-builder \
  -p 'omnios-r151060.qcow2.zst' -p 'omnios-r151060-host.id_rsa' -p 'omnios-r151060.qemu'
zstd -d --rm omnios-r151060.qcow2.zst          # 約 1.1 GB の qcow2 になる
chmod 600 omnios-r151060-host.id_rsa
qemu-system-x86_64 -name omnios -m 6144 -smp 4 -machine pc,accel=tcg,hpet=off -cpu max \
  -rtc base=utc,clock=host \
  -netdev user,id=net0,net=192.168.122.0/24,host=192.168.122.1,dhcpstart=192.168.122.254,ipv6=off,hostfwd=tcp:127.0.0.1:10022-192.168.122.254:22 \
  -device e1000,netdev=net0 -object rng-builtin,id=rng0 -device virtio-rng-pci,rng=rng0 \
  -drive file=omnios-r151060.qcow2,format=qcow2,if=virtio -display none -serial file:serial.log -monitor none &
```

- `omnios-r151060.qemu` は builder が KVM 用に書いた qemu の引数。上は、それを TCG 向けに `accel=tcg`・`-cpu max` に変え、ssh の転送先を 10022 にした物
- 起動から ssh が通るまで約 5 分。シリアルには何も出ないので、ssh が通るかで待つ
- ssh: `ssh -i omnios-r151060-host.id_rsa -p 10022 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@127.0.0.1`
- Rust: VM で `pkg install ooce/developer/rust build-essential` (取得は約 1 GB)。コマンドは `/opt/ooce/bin` に入り、非対話の ssh の `PATH` には入っていない
- sockat-rs の木: ホストで `git archive --format=tar.gz -o src.tar.gz 50d1595e` を作り、`scp -P 10022` で VM の `/root` に送って `/root/rs` に展開した。VM で `export PATH=/opt/ooce/bin:$PATH; cd /root/rs && cargo test --workspace --no-run`。試験のバイナリは `target/debug/build/sockat/<hash>/out/public_api-<hash>` にできる (OmniOS の Rust の配置。今回は `a20587fcc1249bad`)
- DTrace と `mdb -k` / `mdb -kw` は VM の root でそのまま使えた

### 手順 1: Python の再現 (`race.py`)

- 「消す側」のスレッド (`churners`) は、ストリームのソケットを bind・listen してから、指定の順番で閉じてファイルを消す、を繰り返す
- 「bind する側」のスレッド (`binders`) は、毎回新しい名前 (`lstat` で何も無いことを確かめる) に bind・listen し、閉じてから消す
- bind する側で `EADDRINUSE` を数え、その時パスにソケットのファイルがあれば `file_after` に数える
- `mode` は `unlink-then-close`・`close-then-unlink`・`keep-file` (閉じるだけでファイルは残す)・`link-unlink-then-close` (ハードリンクを作ってから元の名前を消し、閉じてからハードリンクを消す)・`none` (消す側を走らせない)
- `CONN=1` にすると、どちらの側も listen の後に接続を 1 本受けて 4 バイトずつ送り合う
- 測定の途中で `mode` の `link-unlink-then-close`、環境変数 `CONN` と `RACE_DIR` を足した。足す前の版で測った mode の振る舞いは、下の全文と同じ

`race.py`:

```python
"""Does a bind of a fresh, never-used path fail with EADDRINUSE while other
threads close stream sockets whose files they have unlinked (or not)?

usage: python3 -I race.py <mode> <seconds> [churners] [binders]
  mode: unlink-then-close | close-then-unlink | keep-file (close, file stays) | none
Binders bind a stream socket to a fresh unique name (lstat says nothing is
there), close it, then unlink it (the safe order). Each EADDRINUSE is counted,
with whether a socket file is at the path afterwards (sockfs created the file
and the transport refused the address).
"""
import errno, os, socket, stat, sys, tempfile, threading, time

mode = sys.argv[1]
secs = float(sys.argv[2])
churners = int(sys.argv[3]) if len(sys.argv) > 3 else 2
binders = int(sys.argv[4]) if len(sys.argv) > 4 else 4
conn = os.environ.get("CONN") == "1"

root = tempfile.mkdtemp(prefix="race-", dir=os.environ.get("RACE_DIR", "/tmp"))
stop = time.monotonic() + secs
lock = threading.Lock()
stats = {"churn": 0, "bind": 0, "eaddrinuse": 0, "file_after": 0, "other": {}}


def churn(k):
    d = os.path.join(root, f"c{k}")
    os.mkdir(d)
    n = 0
    while time.monotonic() < stop:
        p = os.path.join(d, f"{n}")
        n += 1
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(p)
        s.listen(1)
        if conn:
            c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            c.connect(p)
            a, _ = s.accept()
            c.sendall(b"ping"); a.recv(4); a.sendall(b"pong"); c.recv(4)
            a.close()
        if mode == "unlink-then-close":
            os.unlink(p)
            s.close()
        elif mode == "close-then-unlink":
            s.close()
            os.unlink(p)
        elif mode == "keep-file":
            s.close()
        elif mode == "link-unlink-then-close":
            # A second name holds the file's vnode until after the close.
            os.link(p, p + ".hold")
            os.unlink(p)
            s.close()
            os.unlink(p + ".hold")
        if conn:
            c.close()
        with lock:
            stats["churn"] += 1


def bind(k):
    d = os.path.join(root, f"b{k}")
    os.mkdir(d)
    n = 0
    while time.monotonic() < stop:
        p = os.path.join(d, f"{n}")
        n += 1
        assert not os.path.lexists(p)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.bind(p)
            s.listen(1)
            if conn:
                c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                c.connect(p)
                a, _ = s.accept()
                c.sendall(b"ping"); a.recv(4); a.sendall(b"pong"); c.recv(4)
                a.close(); c.close()
            with lock:
                stats["bind"] += 1
        except OSError as e:
            with lock:
                if e.errno == errno.EADDRINUSE:
                    stats["eaddrinuse"] += 1
                    try:
                        if stat.S_ISSOCK(os.lstat(p).st_mode):
                            stats["file_after"] += 1
                    except FileNotFoundError:
                        pass
                else:
                    stats["other"][e.errno] = stats["other"].get(e.errno, 0) + 1
        s.close()
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass


threads = [threading.Thread(target=churn, args=(k,)) for k in range(churners if mode != "none" else 0)]
threads += [threading.Thread(target=bind, args=(k,)) for k in range(binders)]
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f"{os.uname().sysname} conn={conn} mode={mode} secs={secs} churners={churners} binders={binders} {stats}")
```

`window.d` (`sotpi_close` の中で解放された vnode が、`tl_addr_unbind` の前に `vn_alloc` から返る事象を数える。最後の行の `tl_bind:return` の節は何もしない残り):

```d
/* A vnode freed while sotpi_close runs (the bound socket file's, after an
   unlink) whose pointer is still a key in tl's address hash until
   tl_addr_unbind; a vn_alloc returning it in between is the collision. */
fbt:sockfs:sotpi_close:entry { self->inclose = 1; }
fbt:sockfs:sotpi_close:return { self->inclose = 0; }
fbt:genunix:vn_free:entry /self->inclose/ { pend[arg0] = timestamp; @frees = count(); }
fbt:tl:tl_addr_unbind:entry /pend[(uintptr_t)((tl_endpt_t *)arg0)->te_uxaddr.soua_vp]/ {
  this->vp = (uintptr_t)((tl_endpt_t *)arg0)->te_uxaddr.soua_vp;
  @gap_ns = quantize(timestamp - pend[this->vp]);
  pend[this->vp] = 0;
}
fbt:genunix:vn_alloc:return /pend[arg1]/ {
  @reused = count();
  printf("vnode %p handed out again %d ns after free, before tl unbind (cpu %d, %s)\n", arg1, timestamp - pend[arg1], cpu, execname);
}
fbt:tl:tl_bind:return { }
```

VM での流し方:

```sh
# DTrace なし
for m in unlink-then-close close-then-unlink keep-file none; do python3 -I race.py $m 20; done
python3 -I race.py unlink-then-close 30 4 16; python3 -I race.py unlink-then-close 30 8 8
CONN=1 python3 -I race.py unlink-then-close 30 2 8; CONN=1 python3 -I race.py close-then-unlink 30 2 8
# DTrace あり (1 回目は集計を全部、2 回目からは数だけ)
dtrace -q -s window.d -c "python3 -I race.py unlink-then-close 20 2 8"
for m in unlink-then-close close-then-unlink keep-file unlink-then-close close-then-unlink keep-file; do
  dtrace -q -s window.d -c "python3 -I race.py $m 20 2 8" \
    -n "END{printa(\"frees in sotpi_close %@d\n\",@frees); printa(\"reused before unbind %@d\n\",@reused)}" \
    2>&1 | grep -E "SunOS|frees in|reused before|handed out"
done
# 同じ形で 120 秒: unlink-then-close close-then-unlink unlink-then-close close-then-unlink、続けて link-unlink-then-close
```

DTrace なしの 20 秒の 4 本は、VM で `pkg install` (取得) が並行して動いていた時間帯に流した。

macOS と Linux (docker) では `python3 -I race.py <mode> 5` を 4 つの mode で流し、macOS は `CONN=1 python3 -I race.py unlink-then-close 3` も流した。

### 手順 1 の出力 (illumos)

DTrace なし:

```
SunOS mode=unlink-then-close secs=20.0 churners=2 binders=4 {'churn': 8035, 'bind': 14127, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
SunOS mode=close-then-unlink secs=20.0 churners=2 binders=4 {'churn': 8313, 'bind': 14451, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
SunOS mode=keep-file secs=20.0 churners=2 binders=4 {'churn': 10722, 'bind': 15051, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
SunOS mode=none secs=20.0 churners=2 binders=4 {'churn': 0, 'bind': 20584, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
SunOS mode=unlink-then-close secs=30.0 churners=4 binders=16 {'churn': 7024, 'bind': 23759, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
SunOS mode=unlink-then-close secs=30.0 churners=8 binders=8 {'churn': 19576, 'bind': 17070, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
SunOS conn=True mode=unlink-then-close secs=30.0 churners=2 binders=8 {'churn': 2328, 'bind': 8767, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
SunOS conn=True mode=close-then-unlink secs=30.0 churners=2 binders=8 {'churn': 2540, 'bind': 9573, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
```

DTrace あり、1 回目 (集計の全部。`@frees` が 4223、`@gap_ns` が解放から `tl_addr_unbind` までの時間の分布、最後の 1 が `@reused`):

```
vnode fffffe092c5e2940 handed out again 516111 ns after free, before tl unbind (cpu 2, python3.13)
SunOS conn=False mode=unlink-then-close secs=20.0 churners=2 binders=8 {'churn': 4223, 'bind': 14757, 'eaddrinuse': 1, 'file_after': 1, 'other': {}}

             4223

           value  ------------- Distribution ------------- count    
            8192 |                                         0        
           16384 |@@@@                                     410      
           32768 |@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@        3434     
           65536 |@@                                       173      
          131072 |@                                        74       
          262144 |@                                        98       
          524288 |                                         20       
         1048576 |                                         8        
         2097152 |                                         2        
         4194304 |                                         2        
         8388608 |                                         1        
        16777216 |                                         1        
        33554432 |                                         0        

                1
```

DTrace あり、20 秒の 6 本 (集計が空の時は `printa` が何も出さない):

```
SunOS conn=False mode=unlink-then-close secs=20.0 churners=2 binders=8 {'churn': 4501, 'bind': 15999, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
frees in sotpi_close 4501

SunOS conn=False mode=close-then-unlink secs=20.0 churners=2 binders=8 {'churn': 4969, 'bind': 17069, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}

SunOS conn=False mode=keep-file secs=20.0 churners=2 binders=8 {'churn': 5306, 'bind': 14865, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}

vnode fffffe0929f1f600 handed out again 426092 ns after free, before tl unbind (cpu 3, python3.13)
SunOS conn=False mode=unlink-then-close secs=20.0 churners=2 binders=8 {'churn': 2458, 'bind': 17218, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
frees in sotpi_close 2458
reused before unbind 1

SunOS conn=False mode=close-then-unlink secs=20.0 churners=2 binders=8 {'churn': 5000, 'bind': 17363, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}

SunOS conn=False mode=keep-file secs=20.0 churners=2 binders=8 {'churn': 5679, 'bind': 15331, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
```

DTrace あり、120 秒の 4 本:

```
vnode fffffe0949934c00 handed out again 654141 ns after free, before tl unbind (cpu 0, python3.13)
vnode fffffe092c068500 handed out again 663143 ns after free, before tl unbind (cpu 3, python3.13)
vnode fffffe092d49ad80 handed out again 717155 ns after free, before tl unbind (cpu 3, python3.13)
vnode fffffe0949a1b880 handed out again 308066 ns after free, before tl unbind (cpu 0, python3.13)
vnode fffffe0949ad8b80 handed out again 466100 ns after free, before tl unbind (cpu 2, python3.13)
SunOS conn=False mode=unlink-then-close secs=120.0 churners=2 binders=8 {'churn': 22498, 'bind': 97635, 'eaddrinuse': 5, 'file_after': 5, 'other': {}}
frees in sotpi_close 22498
reused before unbind 5

SunOS conn=False mode=close-then-unlink secs=120.0 churners=2 binders=8 {'churn': 30698, 'bind': 104841, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}

vnode fffffe0948c57180 handed out again 346075 ns after free, before tl unbind (cpu 3, python3.13)
vnode fffffe0949ea0c40 handed out again 2116456 ns after free, before tl unbind (cpu 2, python3.13)
vnode fffffe094a2b3700 handed out again 861186 ns after free, before tl unbind (cpu 0, python3.13)
vnode fffffe094aa54e00 handed out again 330071 ns after free, before tl unbind (cpu 1, python3.13)
vnode fffffe094b8f9a40 handed out again 610132 ns after free, before tl unbind (cpu 0, python3.13)
SunOS conn=False mode=unlink-then-close secs=120.0 churners=2 binders=8 {'churn': 17727, 'bind': 88758, 'eaddrinuse': 4, 'file_after': 4, 'other': {}}
frees in sotpi_close 17727
reused before unbind 5

SunOS conn=False mode=close-then-unlink secs=120.0 churners=2 binders=8 {'churn': 28206, 'bind': 98202, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
```

DTrace あり、ハードリンクを残す順 120 秒:

```
SunOS conn=False mode=link-unlink-then-close secs=120.0 churners=2 binders=8 {'churn': 21479, 'bind': 107277, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
```

### 手順 1 の出力 (macOS と Linux)

macOS:

```
Darwin mode=unlink-then-close secs=5.0 churners=2 binders=4 {'churn': 22240, 'bind': 46590, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
Darwin mode=close-then-unlink secs=5.0 churners=2 binders=4 {'churn': 25016, 'bind': 46274, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
Darwin mode=keep-file secs=5.0 churners=2 binders=4 {'churn': 35024, 'bind': 47367, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
Darwin mode=none secs=5.0 churners=2 binders=4 {'churn': 0, 'bind': 84658, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
Darwin conn=True mode=unlink-then-close secs=3.0 churners=2 binders=4 {'churn': 9230, 'bind': 18543, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
```

Linux:

```
Linux mode=unlink-then-close secs=5.0 churners=2 binders=4 {'churn': 72371, 'bind': 125095, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
Linux mode=close-then-unlink secs=5.0 churners=2 binders=4 {'churn': 64018, 'bind': 116720, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
Linux mode=keep-file secs=5.0 churners=2 binders=4 {'churn': 76774, 'bind': 84380, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
Linux mode=none secs=5.0 churners=2 binders=4 {'churn': 0, 'bind': 141957, 'eaddrinuse': 0, 'file_after': 0, 'other': {}}
```

### 手順 1 の結果の表 (illumos)

| 消す側の順番 | DTrace | 時間の合計 | 新しい名前への bind の EADDRINUSE | うち失敗後にファイルが残った | `sotpi_close` の中の vnode の解放 | 解放した vnode が unbind 前に再び渡った |
|---|---|---|---|---|---|---|
| unlink→close | なし | 110 秒 | 0 | 0 | 測っていない | 測っていない |
| unlink→close | あり | 300 秒 | 10 | 10 | 毎回 (churn と同じ数) | 12 |
| close→unlink | なし | 50 秒 | 0 | 0 | 測っていない | 測っていない |
| close→unlink | あり | 280 秒 | 0 | 0 | 0 | 0 |
| ファイルを残して close | なし | 20 秒 | 0 | 0 | 測っていない | 測っていない |
| ファイルを残して close | あり | 40 秒 | 0 | 0 | 0 | 0 |
| ハードリンクを残して unlink→close | あり | 120 秒 | 0 | 0 | 0 | 0 |

macOS と Linux は、どの順番でも 0 (上の出力)。

### 手順 2: sockat-rs の試験を繰り返す (macOS と Linux)

- macOS: `cargo test -p sockat --no-run` と `cargo test --workspace --no-run` を別の `CARGO_TARGET_DIR` で作り、できた `public_api` のバイナリを直接繰り返した
- `--workspace` の build では、sockat のライブラリと試験に `feature="__cli-internal"` が付く (`cargo test --workspace --no-run -v` の `rustc` の引数で確かめた)
- Linux: 同じ事を `rust:1` のコンテナの中で (`docker run --rm -v <sockat-rs>:/work:ro ... rust:1 bash /linux.sh`)

macOS の `loop.sh`:

```bash
#!/bin/bash
# usage: loop.sh <binary> <n> <label> [filter]
bin=$1; n=$2; label=$3; filter=$4
cd <sockat-rs の作業コピー>
fail=0
for i in $(seq 1 $n); do
  if ! out=$("$bin" $filter 2>&1); then
    fail=$((fail+1)); echo "--- run $i failed" ; echo "$out" | grep -E "panicked|code:|FAILED" | head -5
  fi
done
echo "$label: $n runs, $fail failed"
```

Linux の `linux.sh`:

```sh
set -e
cd /work
run() { bin=$1; n=$2; label=$3; f=$4; fail=0; for i in $(seq 1 $n); do "$bin" $f >/tmp/o 2>&1 || { fail=$((fail+1)); grep -E "panicked|code:" /tmp/o | head -3; }; done; echo "$label: $n runs, $fail failed"; }
CARGO_TARGET_DIR=/tmp/tp cargo test -p sockat --no-run 2>&1 | tail -1
CARGO_TARGET_DIR=/tmp/tw cargo test --workspace --no-run 2>&1 | tail -1
P=$(ls /tmp/tp/debug/deps/public_api-* 2>/dev/null | grep -v '\.d$' | head -1); [ -n "$P" ] || P=$(find /tmp/tp -name 'public_api-*' -type f -perm -u+x | grep -v '\.' | head -1)
W=$(find /tmp/tw -name 'public_api-*' -type f -perm -u+x | grep -v '\.o$\|\.d$' | head -1)
echo "P=$P W=$W"
run $P 300 "linux -p single" concurrent_calls_leave_the_cwd_alone
run $W 300 "linux ws single" concurrent_calls_leave_the_cwd_alone
run $P 200 "linux -p whole"
run $W 200 "linux ws whole"
for m in unlink-then-close close-then-unlink keep-file none; do python3 -I /repro/race.py $m 5 2>&1 || true; done
```

出力:

```
mac -p single: 300 runs, 0 failed
mac ws single: 300 runs, 0 failed
mac -p whole: 200 runs, 0 failed
mac ws whole: 200 runs, 0 failed
```

```
linux -p single: 300 runs, 0 failed
linux ws single: 300 runs, 0 failed
linux -p whole: 200 runs, 0 failed
linux ws whole: 200 runs, 0 failed
```

`single` は `concurrent_calls_leave_the_cwd_alone` だけ、`whole` は `public_api` の全部 (CI と同じく試験が並行して走る)。

### 手順 3: sockat-rs の試験を VM で繰り返す

VM の `/root/vmloop.sh`:

```sh
# usage: vmloop.sh <label> <binary> <n> [filter]
cd /root/rs
label=$1; bin=$2; n=$3; f=$4
fail=0
for i in $(seq 1 $n); do
  if ! $bin $f > /root/run.out 2>&1; then
    fail=$((fail+1)); echo "--- $label run $i failed"; grep -E "panicked|code:" /root/run.out | head -4
  fi
done
echo "$label: $n runs, $fail failed"
```

`attr.d` (解放した vnode を誰が解放し誰が受け取ったかと、`EADDRINUSE` (125) で終わった `sotpi_bind`。スレッドの名前は Rust の試験の名前で、無名は `?`):

```d
/* Which thread's close freed a vnode still used as a tl address, which
   thread got it back from vn_alloc before the tl unbind, and every bind
   that failed with EADDRINUSE (125). */
fbt:sockfs:sotpi_close:entry { self->inclose = 1; }
fbt:sockfs:sotpi_close:return { self->inclose = 0; }
fbt:genunix:vn_free:entry /self->inclose/ {
  pend[arg0] = timestamp;
  freer[arg0] = curthread->t_name != NULL ? stringof(curthread->t_name) : "?";
  @frees[execname] = count();
}
fbt:tl:tl_addr_unbind:entry /pend[(uintptr_t)((tl_endpt_t *)arg0)->te_uxaddr.soua_vp]/ {
  pend[(uintptr_t)((tl_endpt_t *)arg0)->te_uxaddr.soua_vp] = 0;
}
fbt:genunix:vn_alloc:return /pend[arg1]/ {
  printf("REUSE vp=%p %dns after free; freed by thread [%s], handed to thread [%s] pid %d\n", arg1, timestamp - pend[arg1], freer[arg1], curthread->t_name != NULL ? stringof(curthread->t_name) : "?", pid);
}
fbt:sockfs:sotpi_bind:return /arg1 == 125/ {
  printf("EADDRINUSE from sotpi_bind in thread [%s] pid %d\n", curthread->t_name != NULL ? stringof(curthread->t_name) : "?", pid);
}
```

`long_path_errors_through_the_public_api` と `an_ex_error_keeps_the_errno_and_the_routes` は、既にあるファイルへの bind の `EADDRINUSE` を確かめる試験なので、下の出力ではその 2 つのスレッドの `EADDRINUSE` の行を除いた。

VM の試験は、別の findings ([procfs の lookup の ENOENT](2026-11-24-illumos-procfs-lookup-enoent-under-contention.md)) の `ENOENT` で先に落ちて `EADDRINUSE` が隠れるので、`EADDRINUSE` を探す回では `echo "pr_getf_maxtries/W 0t1000" | mdb -kw` で `pr_getf_maxtries` を 3 から 1000 にした。

300 回の回の `/root/catch.sh`:

```sh
echo "pr_getf_maxtries/W 0t1000" | mdb -kw >/dev/null
cd /root
rm -f /root/attr3.out
dtrace -q -s attr.d -o /root/attr3.out & D=$!
sleep 4
sh /root/vmloop.sh "illumos ws whole maxtries=1000 (catch)" /root/rs/target/debug/build/sockat/a20587fcc1249bad/out/public_api-a20587fcc1249bad 300 | grep -E "runs,|code:|panicked at" | sed -E "s/thread .* panicked/panicked/" | sort | uniq -c
kill -TERM $D; sleep 3
grep -E "REUSE|EADDRINUSE" /root/attr3.out | grep -v -E "long_path_errors|an_ex_error_keeps" | cut -c1-200
echo "pr_getf_maxtries/W 0t3" | mdb -kw >/dev/null
```

200 回の回は、同じ形で `attr.d` の出力を `/root/attr2.out` にし、回数を 200 にした。

### 手順 3 の出力

300 回 (`pr_getf_maxtries` は 1000):

```
   1 called `Result::unwrap()` on an `Err` value: Os { code: 125, kind: AddrInUse, message: "Address already in use" }
   1 illumos ws whole maxtries=1000 (catch): 300 runs, 1 failed
   1 panicked at tests/public_api.rs:315:53:
   1 panicked at tests/public_api.rs:324:18:
REUSE vp=fffffe092577b440 808174ns after free; freed by thread [bind_ex_returns_the_socket_file], handed to thread [?] pid 2711
REUSE vp=fffffe092577b440 3354723ns after free; freed by thread [bind_ex_returns_the_socket_file], handed to thread [?] pid 2711
REUSE vp=fffffe0925449840 783169ns after free; freed by thread [default_binds_in_one_directory_], handed to thread [?] pid 2711
REUSE vp=fffffe0925201380 333071ns after free; freed by thread [resolved_spellings_go_to_std], handed to thread [?] pid 2755
REUSE vp=fffffe0920a3a940 1081233ns after free; freed by thread [sweep_keeps_this_processs_d], handed to thread [?] pid 2774
REUSE vp=fffffe0923f3f080 729157ns after free; freed by thread [resolved_spellings_go_to_std], handed to thread [?] pid 2778
REUSE vp=fffffe09229d6680 303065ns after free; freed by thread [sweep_keeps_this_processs_d], handed to thread [?] pid 2778
EADDRINUSE from sotpi_bind in thread [?] pid 2783
REUSE vp=fffffe0925638e40 816176ns after free; freed by thread [sweep_keeps_this_processs_d], handed to thread [?] pid 2802
REUSE vp=fffffe0925638e40 3002647ns after free; freed by thread [sweep_keeps_this_processs_d], handed to thread [?] pid 2802
REUSE vp=fffffe0924479c00 2931632ns after free; freed by thread [sweep_keeps_this_processs_d], handed to thread [?] pid 2840
REUSE vp=fffffe0923cd2d40 883190ns after free; freed by thread [default_binds_in_one_directory_], handed to thread [?] pid 2842
REUSE vp=fffffe0924a21380 1410304ns after free; freed by thread [sweep_keeps_this_processs_d], handed to thread [?] pid 2842
REUSE vp=fffffe0924a21380 3113671ns after free; freed by thread [sweep_keeps_this_processs_d], handed to thread [?] pid 2842
REUSE vp=fffffe0924f78980 12300651ns after free; freed by thread [default_binds_in_one_directory_], handed to thread [?] pid 2878
REUSE vp=fffffe09248f7280 252054ns after free; freed by thread [resolved_spellings_go_to_std], handed to thread [?] pid 2879
REUSE vp=fffffe09258f7580 692149ns after free; freed by thread [sweep_keeps_this_processs_d], handed to thread [?] pid 2879
REUSE vp=fffffe0922467340 2710584ns after free; freed by thread [default_binds_in_one_directory_], handed to thread [?] pid 2927
REUSE vp=fffffe09245c4900 1299280ns after free; freed by thread [default_binds_in_one_directory_], handed to thread [?] pid 2932
REUSE vp=fffffe09211ae100 1915413ns after free; freed by thread [sweep_keeps_this_processs_d], handed to thread [?] pid 2932
REUSE vp=fffffe09245b9a40 593128ns after free; freed by thread [bind_ex_returns_the_socket_file], handed to thread [?] pid 2963
REUSE vp=fffffe09254b1080 970209ns after free; freed by thread [default_binds_in_one_directory_], handed to thread [?] pid 2963
REUSE vp=fffffe0924955580 11256426ns after free; freed by thread [default_binds_in_one_directory_], handed to thread [?] pid 2967
REUSE vp=fffffe0925563c80 1274274ns after free; freed by thread [resolved_spellings_go_to_std], handed to thread [?] pid 2967
REUSE vp=fffffe0925563c80 1799387ns after free; freed by thread [resolved_spellings_go_to_std], handed to thread [?] pid 2967
REUSE vp=fffffe092463b840 2702583ns after free; freed by thread [sweep_keeps_this_processs_d], handed to thread [?] pid 2967
```

200 回 (`pr_getf_maxtries` は 1000):

```
   1 called `Result::unwrap()` on an `Err` value: Os { code: 125, kind: AddrInUse, message: "Address already in use" }
   2 called `Result::unwrap()` on an `Err` value: Os { code: 2, kind: NotFound, message: "No such file or directory" }
   1 illumos ws whole maxtries=1000: 200 runs, 3 failed
   1 panicked at tests/public_api.rs:145:36:
   2 panicked at tests/public_api.rs:315:53:
   2 panicked at tests/public_api.rs:324:18:
REUSE vp=fffffe0925a30b80 1965423ns after free; freed by thread [bind_ex_returns_the_socket_file], handed to thread [datagrams_at_long_paths] pid 1363
EADDRINUSE from sotpi_bind in thread [datagrams_at_long_paths] pid 1363
REUSE vp=fffffe0924970e40 998215ns after free; freed by thread [default_binds_in_one_directory_], handed to thread [?] pid 1414
REUSE vp=fffffe0924106600 1043224ns after free; freed by thread [default_binds_in_one_directory_], handed to thread [?] pid 1470
REUSE vp=fffffe0924380700 1226264ns after free; freed by thread [default_binds_in_one_directory_], handed to thread [?] pid 1472
REUSE vp=fffffe0925547580 1955421ns after free; freed by thread [default_binds_in_one_directory_], handed to thread [?] pid 1500
REUSE vp=fffffe0924702340 10102177ns after free; freed by thread [bind_ex_returns_the_socket_file], handed to thread [?] pid 1549
REUSE vp=fffffe0924e05940 1134244ns after free; freed by thread [default_binds_in_one_directory_], handed to thread [?] pid 1549
```

`tests/public_api.rs:145` は `std_drops_last_byte` の中の `UnixListener::bind(&p).unwrap()` (Rust の `std` の bind)。`datagrams_at_long_paths` が呼ぶ。2 件の `NotFound` は別の findings の件。

`pr_getf_maxtries` が 3 のまま `attr.d` を当てた 150 回では、39 回が落ち、出力の末尾に見えた分はどれも `tests/public_api.rs:315:53` の `NotFound` だった。この 150 回の `REUSE` の行は 14 行で、解放したスレッドは `resolved_spellings_go_to_std` か `sweep_keeps_this_processs_d` だった。上の 2 つの試験を除いた `EADDRINUSE` の行は無かった。

### 手順 3 の結果の表

| 回 | `pr_getf_maxtries` | DTrace | 回数 | `EADDRINUSE` で落ちた | `NotFound` で落ちた |
|---|---|---|---|---|---|
| 1 | 3 | `attr.d` | 150 | 0 | 39 のうち確かめた分の全部 |
| 2 | 1000 | `attr.d` | 200 | 1 (Rust の `std` の bind、`public_api.rs:145`) | 2 |
| 3 | 1000 | `attr.d` | 300 | 1 (`public_api.rs:315:53`、CI と同じ形) | 0 |

### CI の出力

run 45376995896 の job 138385814665 (commit 50d1595、`cargo test --workspace --no-fail-fast`):

```
     Running tests/public_api.rs (target/debug/build/sockat/4b954ab9c1c3916d/out/public_api-4b954ab9c1c3916d)

running 15 tests
test an_empty_path_is_invalid_input_everywhere ... ok
test a_short_path_behaves_exactly_like_std ... ok
test an_ex_error_keeps_the_errno_and_the_routes ... ok
test a_datagram_connect_to_a_socket_nobody_holds_fails_as_std_does ... ok
test bind_ex_returns_the_socket_file_and_the_spelling ... ok
test datagrams_at_long_paths ... ok
test default_binds_in_one_directory_share_their_e ... ok
test long_path_errors_through_the_public_api ... ok
test options_base_holds_b ... ok
test sweep_keeps_this_processs_d ... ok
test resolved_spellings_go_to_std ... ok
test the_results_are_ordinary_std_sockets ... ok
test the_address_of_a_long_path_bind_fits_sun_path ... ok
test bind_and_connect_work_at_any_length ... ok
test concurrent_calls_leave_the_cwd_alone ... FAILED

failures:

---- concurrent_calls_leave_the_cwd_alone stdout ----

thread '<unnamed>' (14) panicked at tests/public_api.rs:315:53:
called `Result::unwrap()` on an `Err` value: Os { code: 125, kind: AddrInUse, message: "Address already in use" }
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace

thread 'concurrent_calls_leave_the_cwd_alone' (8) panicked at tests/public_api.rs:324:18:
called `Result::unwrap()` on an `Err` value: Any { .. }


failures:
    concurrent_calls_leave_the_cwd_alone

test result: FAILED. 14 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.06s
```

run 44225797996 の job 134538538399 (commit a18fba57) の該当行:

```
     Running tests/public_api.rs (target/debug/deps/public_api-dbc447d05cfbbc7a)
test concurrent_calls_leave_the_cwd_alone ... FAILED
---- concurrent_calls_leave_the_cwd_alone stdout ----
thread '<unnamed>' (12) panicked at tests/public_api.rs:276:53:
called `Result::unwrap()` on an `Err` value: Os { code: 125, kind: AddrInUse, message: "Address already in use" }
thread 'concurrent_calls_leave_the_cwd_alone' (5) panicked at tests/public_api.rs:285:18:
    concurrent_calls_leave_the_cwd_alone
test result: FAILED. 6 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.08s
```

## 推測 (確かめていない)

- `EADDRINUSE` が、DTrace を当てた時だけ VM で出たのは、fbt の probe が `sotpi_close` から `tl_addr_unbind` までの時間を延ばして窓を広げたためと考えている。CI (KVM の上、DTrace なし) では同じ形の失敗が 2 回 (2026-11-18 と 2026-11-24) 出ている
- 「同じアドレスの vnode が渡る」のは、kmem のキャッシュが、解放したばかりの物を次の割り当てに返すためと考えている。kmem の振る舞いは読んでいない
- CI の失敗で、どの試験が閉じた vnode が渡ったかは、ログからは分からない。commit 50d1595 の `public_api` で unlink してから閉じるストリームの試験は上の 4 つで、VM で観測した再利用もこの 4 つからだけだった

## 確かめられなかった事

- 手順 3 の 300 回の 1 回 (pid 2783) では、`attr.d` に、その pid に渡った再利用の行が無かった。`attr.d` が拾うのは `sotpi_close` を実行中のスレッドが解放した vnode だけで、最後の参照を別のスレッドが手放した場合 (同じパスを lookup していたスレッド等) は拾わない。その回がそれに当たるかは確かめていない。DTrace の drop の表示は出ていなかった
- DTrace を当てない状態で、VM で `EADDRINUSE` を出す事は出来なかった (Python で 110 秒、Rust の試験は `NotFound` で先に落ちる)
- CI の VM (KVM) での起きやすさは測っていない。CI の VM の vCPU の数も分からない
- tmpfs 以外 (ZFS 等) でソケットのファイルを残して閉じた時に、`sotpi_close` の中で vnode が解放されるかは測っていない (`race.py` に `RACE_DIR` を足したが、流していない)
- `SOCK_DGRAM` のソケットを unlink してから閉じた場合は、Python で再現していない (tl の表がストリームと別であることは、ソースで確かめただけ)
- illumos に、この順番の問題が既に報告されているかは調べていない
- 他の illumos の配布物 (SmartOS、OpenIndiana 等) は測っていない
