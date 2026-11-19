# SOCK_DGRAM と SOCK_SEQPACKET の長いパス (2026-11-19 調査)

## 目的

- [issue](../issue/2026-11-18-datagram-and-seqpacket.md) の受け入れ条件のうち、1 つ目 (型ごとの経路の当て方と API の形) と 3 つ目 (需要) の材料を作る
- 決めるのは kawaz。この文書は候補と推しを並べるだけで、SPEC・DR は直さない
- 「実測」は下の実測の表で確かめたもの。「一次資料」は URL の資料で確かめたもの。「推測」はどちらでもないもの

## 需要

- 調べたのは公開ソースと issue (2026-11-19 時点の main)。「見つからない」はその検索の範囲での話で、0 件の断定ではない
- 需要の強さの所感: DGRAM は中、SEQPACKET は弱〜中

### 長いパスに当たって迂回を持つ・壊れた実例

| 対象 | 型 | 中身 | 一次資料 |
|---|---|---|---|
| crun (コンテナの実行環境) | DGRAM | sd_notify の中継用の `<state_dir>/notify/notify` を DGRAM で bind する。長いパスは親ディレクトリを `O_PATH` で開き `/proc/self/fd/<dirfd>/<名前>` で bind する。2021 年に `/proc/self/fd` 化し、2026-03 にソケット自身の fd を使っていた誤りを直した (PR 本文: 「long container IDs or deep `XDG_RUNTIME_DIR`」で 108 バイトを超える) | [crun#2050](https://github.com/containers/crun/pull/2050)、[utils.c](https://github.com/containers/crun/blob/main/src/libcrun/utils.c) |
| conmon (コンテナの監視) | DGRAM と SEQPACKET | notify (`notify/notify.sock`、DGRAM) と attach (SEQPACKET) を `/proc/self/fd/<dirfd>/<名前>` で bind する。ホストの `NOTIFY_SOCKET` への宛先は `strncpy` で `sun_path` に切り詰めてコピーする (長いと黙って切れる) | [conn_sock.c](https://github.com/containers/conmon/blob/main/src/conn_sock.c) |
| podman | SEQPACKET | attach socket のパスが 109 バイトになりコンテナを起動できなかった (3.0.0rc2)。今は Linux で `O_PATH` + `/proc/self/fd/<fd>` に `DialUnix("unixpacket")`、FreeBSD で短い symlink を作って dial する | [podman#9264](https://github.com/containers/podman/issues/9264)、[oci_conmon_attach_linux.go](https://github.com/containers/podman/blob/main/libpod/oci_conmon_attach_linux.go)、[oci_conmon_attach_freebsd.go](https://github.com/containers/podman/blob/main/libpod/oci_conmon_attach_freebsd.go) |
| go-trusted-platform | DGRAM | 試験で notify socket の `ListenUnixgram` が `sun_path` を超えて落ち、短いディレクトリへ逃がした | [#1983](https://github.com/jeremyhahn/go-trusted-platform/issues/1983) |

- crun と conmon の bind の綴りは `/proc/self/fd/<dirfd>/<名前>` で、dirfd を閉じた後に `getsockname` の綴りが別の所を指す。sockat が [DR-0012](../decisions/DR-0012-own-directory-and-thread-cwd.md) で R を挟む理由と同じ形 ([Fedora devel の議論](https://www.mail-archive.com/devel@lists.fedoraproject.org/msg202065.html) でも、fd を閉じた後も綴りが返り続けると指摘されている)

### systemd の NOTIFY_SOCKET

| 場所 | 振る舞い | 一次資料 |
|---|---|---|
| libsystemd の `sd_notify` | 呼ぶたびにソケットを作り、DGRAM は connect せず `sendmsg` の `msg_name` に宛先を渡す (STREAM / SEQPACKET は connect)。宛先は `sockaddr_un_set_path` で作り、長いと `-ENAMETOOLONG` で送れない (迂回なし) | [sd-daemon.c](https://github.com/systemd/systemd/blob/main/src/libsystemd/sd-daemon/sd-daemon.c)、[socket-util.c](https://github.com/systemd/systemd/blob/main/src/basic/socket-util.c) |
| man の自前実装の例 | C は `path_length >= sizeof(sun_path)` で `-E2BIG`。DGRAM を connect してから送る | [notify-selfcontained-example.c](https://github.com/systemd/systemd/blob/main/man/notify-selfcontained-example.c) |
| systemd の `connect_unix_path` | 長いパスを `O_PATH` で開いて `/proc/self/fd/<fd>` に connect する (v252 から)。STREAM 向けの汎用の道具で、`sd_notify` は使わない | [commit 2679aee440](https://github.com/systemd/systemd/commit/2679aee440) |
| PID1 / user manager の bind | `<runtime prefix>/systemd/notify` を素の `sockaddr_un` で bind する。長いと拒否。失敗の報告は見つからない (`/run/user/<uid>` は短い) | [manager.c](https://github.com/systemd/systemd/blob/main/src/core/manager.c) |

- NOTIFY_SOCKET の宛先は固定で、`sd_notify` は呼ぶたびに新しいソケットで 1 回送る。宛先を connect してから送っても費用は同じ (man の例はそうしている)

### 他の DGRAM / SEQPACKET の利用 (長いパスの報告は見つからない)

| 対象 | 型 | 長いパスの扱い | 一次資料 |
|---|---|---|---|
| wpa_supplicant の ctrl_interface | DGRAM | クライアントは `/tmp/wpa_ctrl_<pid>-<n>` 等を bind して connect、サーバは `recvfrom` の送り元へ `sendto` で返す。長いと拒否 | [wpa_ctrl.c](https://w1.fi/cgit/hostap/plain/src/common/wpa_ctrl.c)、[ctrl_iface_unix.c](https://w1.fi/cgit/hostap/plain/wpa_supplicant/ctrl_iface_unix.c) |
| chrony (chronyc ↔ chronyd) | DGRAM | chronyc がソケットを bind して返信を受ける。コメントに「bind した後に動かすと、chronyd に見える送り元のアドレスが実際のパスと合わず、返信が chronyc に届かない」 | [client.c](https://github.com/mlichvar/chrony/blob/master/client.c) |
| rsyslog imuxsock | DGRAM | `>= sun_path` で `ENAMETOOLONG`。bind は黙って切り詰めるので拒否する、とコメント | [imuxsock.c](https://github.com/rsyslog/rsyslog/blob/main/plugins/imuxsock/imuxsock.c) |
| QEMU `-netdev dgram` | DGRAM | 長いと拒否 | [net/dgram.c](https://gitlab.com/qemu-project/qemu/-/raw/master/net/dgram.c) |
| Postfix の `unix-dgram` | DGRAM | queue_directory からの相対パス | [master(5)](https://www.postfix.org/master.5.html) |
| Android の logd / lmkd / tombstoned | SEQPACKET | `/dev/socket/<名前>` の短いパス | [logd.rc](https://android.googlesource.com/platform/system/logging/+/refs/heads/main/logd/logd.rc) |
| syslog の `/dev/log`、journald の `/run/systemd/journal/socket` | DGRAM | 固定の短いパス | — |

- 返信先が bind した時の綴りになる問題は、chrony のコメントと、送り元のアドレスを書き戻す必要が出た [termux/proot#403](https://github.com/termux/proot/pull/403) に出てくる (下の実測の「返信」と同じ現象)
- 宛先を変えながら長いパスへ送る (1 つのソケットで送るたびに宛先が違う) 実例は見つけていない

### 標準ライブラリ側の議論

- Rust: SEQPACKET を std に入れる PR は「macOS で使えないのでまず crates.io で」と閉じられ ([rust#50348](https://github.com/rust-lang/rust/pull/50348))、ACP ([libs-team#898](https://github.com/rust-lang/libs-team/issues/898)、open) にも「`UnixStream` と API が同じで別の型にする理由が弱い」との意見。crate の uds は macOS と illumos を N/A とする。tokio-seqpacket と nix は長いパスを拒否する
- Python: asyncio の `create_unix_server` / `create_unix_connection` は SOCK_STREAM 以外を拒否し、SEQPACKET 対応の要望 ([cpython#82466](https://github.com/python/cpython/issues/82466)) は実装されずに閉じた
- Go: `"unixpacket"` が macOS で使えないことは文書に無く、試験 (`src/net/platform_test.go`) で darwin 等を外しているだけ

## 各言語の標準の扱い

| 言語 | DGRAM の bind / connect / 宛先つきの送信 | 長いパスの時 | SEQPACKET | 返す型 |
|---|---|---|---|---|
| Rust std | `UnixDatagram::bind` / `unbound` + `connect` / `send_to` | 3 つとも `InvalidInput` "path must be shorter than SUN_LEN" (実測 macOS、rustc 1.100.0)。判定は `library/std/src/os/unix/net/addr.rs` の `sockaddr_un` | 型が無い | `UnixDatagram` |
| Python | `socket.socket(AF_UNIX, SOCK_DGRAM)` の `bind` / `connect` / `sendto` | 3 つとも `OSError("AF_UNIX path too long")`、errno 無し (実測 macOS 3.15.2、Linux 3.13.18) | `socket.SOCK_SEQPACKET` は両 OS にある。macOS は `socket()` が `[Errno 43] Protocol not supported`、Linux は作れる (実測) | `socket.socket` (型の種類によらず同じクラス) |
| Go net | `ListenUnixgram` / `ListenPacket("unixgram")`、`DialUnix("unixgram", laddr, raddr)`、`(*UnixConn).WriteToUnix` | 4 つとも `EINVAL` を包んだ `*net.OpError` (実測 macOS・Linux、go1.27.3) | `"unixpacket"`。macOS は短いパスでも `socket: protocol not supported`、Linux は使える (実測) | DGRAM は `*net.UnixConn`。SEQPACKET は `*net.UnixListener` / `*net.UnixConn`。生の fd からも `net.FileConn` / `net.FilePacketConn` が DGRAM で `*net.UnixConn`、SEQPACKET で `*net.UnixConn` を返す (実測)。`FileListener` は Unix の sockaddr なら `*net.UnixListener` (`src/net/file_posix.go`) |

- Go の `ListenUnixgram` の `*UnixConn` は閉じてもソケットのファイルを消さない (実測)。消すのは `UnixListener` だけ (`src/net/unixsock_posix.go` の `unlinkOnce`)。DGRAM では 3 言語とも標準が消さない
- Go の `ListenUnixgram("unixgram", nil)` は `missing address` で、bind しない DGRAM の `*UnixConn` は `FilePacketConn` か `DialUnix` でしか作れない (実測)
- Python の asyncio は `create_datagram_endpoint(sock=...)` に bind 済みの AF_UNIX DGRAM を渡せる。`local_addr=` に長いパスを渡すと `AF_UNIX path too long` (実測)
- 送り元が bind していない datagram を受けた時の送り元アドレス: Linux はアドレス長 0 (Python `None`、Go `nil`)、macOS はアドレス長 16 で中身が 0 (Python `''`、Go `nil`) (実測)

## 実測

### 環境とコマンド

| 環境 | 中身 |
|---|---|
| macOS | macOS 26.5.2 (Darwin 25.5.0、arm64)、Apple clang |
| Linux | `docker run --rm --privileged gcc:14` (カーネル 7.2.12、OrbStack の VM)。`--privileged` 無し (docker の既定の seccomp) でも回した |
| 言語の標準 | Python 3.15.2 (macOS) / `python:3.13-slim` (Linux)、go1.27.3 (Linux へは `CGO_ENABLED=0 GOOS=linux` で作って `python:3.13-slim` で実行)、rustc 1.100.0 (macOS) |

- C の試験プログラム 1 本 (`cc -O0 -o dg dg.c -lpthread && ./dg "$(mktemp -d)"`) を両 OS で回した。`$TMPDIR` の下に 120 バイトのディレクトリを作り、その中のソケット (パス全体 macOS 205、Linux 144 バイト) を相手にする。D は作業ディレクトリの中、symlink-file の symlink は `/tmp` に作ってすぐ消す
- 経路は SPEC の手段をそのまま C で書いた (thread-cwd は Linux `unshare(CLONE_FS)` → `fchdir`、macOS `pthread_fchdir_np`)。`-direct` は R を通さずソケットのディレクトリに直接移る形

### bind (SOCK_DGRAM)

| 経路 | macOS | Linux | 返る綴り (`getsockname`) |
|---|---|---|---|
| thread-cwd | 通る | 通る (`--privileged`)。既定の seccomp では `unshare` が `EPERM` | `R1/<名前>` |
| proc | `/proc` が無く `ENOENT` | 通る | `/proc/self/fd/4/R2/<名前>` |
| symlink-file | 通る | `EADDRINUSE` (辿らない。stream と同じ) | `/tmp/sockat.<乱数>` |
| fork-cwd | 通る | 通る | `R4/<名前>` |

- 通った経路はどれも、元のパスにソケットのファイルができ、そこへ送った datagram が届いた (両 OS)
- bind の経路と結果は stream と同じ。listen が無いことだけが違う

### 宛先つきの送信 (bind していない送り元の `sendto`)

| 経路 | macOS | Linux |
|---|---|---|
| relative (プロセスの cwd を移して相対パス) | 届く | 届く |
| thread-cwd-direct (スレッドの cwd をソケットのディレクトリへ、ファイル名で) | 届く | 届く (既定の seccomp では `EPERM`) |
| thread-cwd (D と R を通す) | 届く | 届く (同上) |
| proc-direct | `ENOENT` (`/proc` が無い) | 届く |
| symlink-file | 届く | 届く (`sendto` は最後の要素の symlink を辿る) |
| widened | 届く | 該当なし (`ENOSYS` は試験側で未実装の印) |

- relative の競合: 相対パスを作った後で cwd が変わると、datagram は別のディレクトリの同じ名前のソケットに届いた (両 OS)。connect と違い、送った後で cwd を確かめても取り消せない

### connect してから `send` (SOCK_DGRAM)

| 経路 | macOS | Linux | connect した側の `getpeername` |
|---|---|---|---|
| relative | 届く | 届く | 受け手が bind した綴り (`rcv`) |
| thread-cwd-direct | 届く | 届く | 同上 |
| proc-direct | `ENOENT` | 届く | 同上 |
| symlink-file | 届く | 届く | 同上 |
| widened | 届く | 該当なし | 同上 |
| fork-cwd-direct | 届く | 届く | 同上 |

- どれも、connect に使った綴り (symlink、dir の fd、cwd) を消した・閉じた・戻した後の `send` が届いた。宛先は connect の時に固まる
- connect した綴りは相手に残らない (stream と同じ)

### connect した DGRAM の性質 (標準そのもの、経路によらない)

| 場面 | macOS | Linux |
|---|---|---|
| 受け手を閉じて同じパスに作り直した後、connect 済みの `send` | `ECONNRESET`、新しい受け手に届かない | `ECONNREFUSED`、新しい受け手に届かない |
| 同じ場面で、connect していないソケットの `sendto` | 新しい受け手に届く | 届く |
| connect 済みのソケットで connect し直す | 通り、届く | 通り、届く |
| connect 済みのソケットから別の宛先へ `sendto` | `EISCONN` | 届く |
| connect したソケットへ、connect 先以外が送る | 届く | `EPERM` |

### 受け手が受け取る送り元のアドレスと、そこへの返信

送り元を各経路で長いパスに bind し、受け手 (cwd は別の空のディレクトリ) が `recvfrom` で得たアドレスへ `sendto` で返信した。

| 送り元の bind | 受け手が得るアドレス | 返信 | 綴りを他人が作り直した時 |
|---|---|---|---|
| bind しない | Linux: 長さ 0。macOS: 長さ 16 で中身 0 | Linux `ENOTCONN`、macOS `ENOENT` | 該当なし |
| thread-cwd | `R<n>/<名前>` | `ENOENT` (両 OS) | 受け手の cwd に `R<n>/<名前>` のソケットを作ると、返信はそこに届いた (両 OS) |
| fork-cwd | `R<n>/<名前>` | `ENOENT` (両 OS) | thread-cwd と同じ |
| proc | `/proc/self/fd/5/R<n>/<名前>` | `ENOENT` (Linux) | 受け手のプロセスの fd 5 で解決される (作り直しは未実測。仕組みは [DR-0012](../decisions/DR-0012-own-directory-and-thread-cwd.md) の `/proc` の綴りと同じ) |
| symlink-file | `/tmp/sockat.<乱数>` | `ENOENT` (macOS) | 同じ名前で別のソケットを指す symlink を作ると、返信はそこに届いた (macOS) |

- 長いパスに bind した送り元には、受け手から返信が届かない。返信の綴りを他人が作れる場所 (受け手の cwd、共有の `/tmp`) なら、返信はその人のソケットに届く
- stream の `respelled` の危険は「綴りで unlink / stat する」だったが、DGRAM では「綴りへ送る」が加わる。symlink-file の綴りは、unlink では置き場の項目が消えるだけ ([SPEC](../SPEC-ja.md#symlink-file)) だが、送ると作り直された symlink を辿る

### SOCK_SEQPACKET

| 場面 | macOS | Linux |
|---|---|---|
| `socket(AF_UNIX, SOCK_SEQPACKET)` | `EPROTONOSUPPORT` | 作れる |
| bind: thread-cwd / proc / fork-cwd → listen | 該当なし | 通る |
| bind: symlink-file | 該当なし | `EADDRINUSE` (辿らない) |
| connect: relative / proc-direct / symlink-file / thread-cwd-direct | 該当なし | どの bind の経路の相手にも届く |
| メッセージの境界 | 該当なし | 保たれる (3 バイトと 4 バイトを送り、2 回の `recv` で 3 と 4) |
| 返る綴り | 該当なし | `getsockname` と相手の `getpeername` が `R<n>/<名前>` / `/proc/self/fd/4/R<n>/<名前>` (stream と同じ) |

- FreeBSD の unix(4) は SOCK_STREAM・SOCK_SEQPACKET・SOCK_DGRAM を持つと書く ([unix(4)](https://man.freebsd.org/cgi/man.cgi?query=unix&sektion=4))。NetBSD・OpenBSD・illumos は未確認

### FreeBSD (一次資料のみ、実測なし)

- `connectat(fd, s, name, namelen)` は PF_LOCAL のソケットだけで、相対の `sun_path` を `fd` のディレクトリから引く ([connectat(2)](https://man.freebsd.org/cgi/man.cgi?query=connectat&sektion=2))。`sendto` の `*at` 版は無い (同じ man page の SEE ALSO にも無い)
- FreeBSD にはスレッドごとの cwd も `/proc/self/fd` も無い (SPEC の connect の順が at-direct → at だけなのと同じ理由)。宛先つきの送信を送るたびに当てる経路は、symlink-file か fork の子の `sendto` しか無い (推測。実測なし)
- unix(4): datagram ソケットは書き込みが常にブロックしない、と書く

## 設計案の比較

### 前提 (実測から)

- DGRAM と SEQPACKET の bind は、stream の bind の経路をそのまま使える (listen が無いかだけ)
- DGRAM の connect は、stream の connect の経路をそのまま使える。宛先は connect の時に固まり、綴りは相手に残らない
- SEQPACKET は stream と同じに扱える。macOS では標準も作れない
- DGRAM 特有の論点は 2 つ
  - 宛先つきの送信 (`sendto`) をどう当てるか
  - 長いパスに bind した送り元に返信が届かない (どの経路でも)

### 宛先つきの送信の当て方

| 案 | 中身 | 失うもの (SPEC の語彙) | 標準と同じ型 | 届く所 | 悪い面 |
|---|---|---|---|---|---|
| A: connect して宛先を固定 | `connect_datagram(path)` 等で、connect 済みの標準の DGRAM を返す。経路は stream の connect の順そのまま | 無し (最終手段の fork-cwd-direct で `forked`) | 返す (`UnixDatagram` / `socket.socket` / `*net.UnixConn`) | stream の connect と同じ (どこから届かなくなるかの connect の列) | 1 つのソケットで宛先を変えられない (macOS は別宛先への `sendto` が `EISCONN`)。受け手が作り直されたら `ECONNREFUSED` / `ECONNRESET` で、利用者が connect し直す (短いパスの標準の connect と同じだが、送るたびに `sendto` していた利用者には違う) |
| B: 送るたびに経路を当てる | `send_to(sock, buf, path)` 等の関数で、標準のソケットに長いパスへ送る | relative を使うなら、cwd の競合で別のソケットに届きうる (今の語彙に無い。取り消せない)。relative を外せば無し。fork の子なら `forked` | ソケットは標準のまま。送る関数が sockat 独自 | relative を外すと: Linux は proc-direct / thread-cwd / symlink-file、macOS は widened / thread-cwd / symlink-file、FreeBSD は symlink-file か fork だけ (推測)、他は symlink-file | 送るたびに費用 (経路により dir を開く・スレッドを立てる・symlink を作って消す)。`sendmsg` (fd や資格情報を付ける送信) と非同期のランタイム (tokio の `send_to`、asyncio の transport) に、言語ごとの版を足す必要がある。1 回の送信が経路の途中の失敗で落ちた時の扱いを決め直す |
| C: A と B を別の関数で両方出す | 宛先が決まっている用途は A、宛先が変わる用途は B | A と B のそれぞれ | A は返す、B はソケットが標準 | A と B のそれぞれ | API が倍になる。B の悪い面がそのまま残る。A と B は責務が分かれる (宛先を固定するか) ので集約の問題は無いが、B の需要は未確認 |
| D: 宛先を一度引いた送り先の値を返す | sockat が長いパスを引いて dir の fd 等を持つ値を返し、`send_to(sock, buf, &dest)` で使う | B と同じ | ソケットは標準、宛先の値は sockat 独自 | B と同じ | 宛先の値が fd を持ち、閉じる責任が利用者に移る。言語ごとに独自の型が増える |

- A は「標準の型を返して置き換えるだけで使える」という SPEC の約束 ([公開する操作](../SPEC-ja.md#公開する操作)) にそのまま乗る。B と D は送る口が sockat 独自になる
- B で relative を使うなら、cwd の競合で別のソケットに datagram が届く (実測)。stream の relative は connect の後に cwd を確かめて捨てられるが、送った datagram は捨てられない。B では relative を外すのが前提になる

### 長いパスに bind した DGRAM の失うもの

| 案 | 中身 | 悪い面 |
|---|---|---|
| a: `respelled` のまま、説明に DGRAM の結果を足す | 「起きること」に「受け手が返信できない (`ENOENT`)、綴りを作り直されると返信が他人に届く」を足す | 分岐に使う名前が stream と同じなので、返信を当てにする利用者が `losses` で見分けられない (DGRAM の bind では `respelled` が常に返信不可を意味する、と読ませる) |
| b: DGRAM の bind だけに付く新しい名前を足す (例: `unrepliable`。名前は仮) | 標準以外の経路を通った DGRAM の bind に `respelled` と並べて付ける | 名前が増える。`respelled` が付く時は必ず付くので、情報が増えない (型で分かる) |
| c: 共有の置き場の symlink-file を DGRAM の bind では `recreatable-spelling` にする | 送ると作り直された symlink を辿るので (実測)、symlink-dir と同じ危険になる | stream の symlink-file の判断 ([DR-0016](../decisions/DR-0016-bind-through-file-symlink.md)) と型で割れる。macOS の `$TMPDIR` は持ち主だけが書けるので、そこが先に使われれば当たらない |

- a・b と c は別の論点 (返信が届かないこと全般と、共有の置き場の綴りの作り直し) で、両方決める必要がある
- 返信を届かせる経路 (bind の綴りを片付けずに残す) は作れるが (symlink-file の symlink を `discard()` まで残す等)、[DR-0012](../decisions/DR-0012-own-directory-and-thread-cwd.md) の「片付けた後は R がどこにも無い」に反し、綴りを他の利用者が使える時間が延びる。候補に挙げるだけにする

### 型ごとの API の形の候補

| 型 | 操作 | Rust | Python | Go |
|---|---|---|---|---|
| DGRAM | bind | `bind_datagram(path) -> UnixDatagram` | `bind(path, type=SOCK_DGRAM)` か `bind_datagram(path)` | `ListenUnixgram(path) (*net.UnixConn, error)` |
| DGRAM | connect (案 A) | `connect_datagram(path) -> UnixDatagram` | `connect(path, type=SOCK_DGRAM)` か `connect_datagram(path)` | `DialUnixgram(path) (*net.UnixConn, error)` |
| DGRAM | bind してから connect (返信を受けたい送り元) | 未定 (下の未確定) | 未定 | 標準は `DialUnix("unixgram", laddr, raddr)`。未定 |
| SEQPACKET | bind (listen 済み) | 返す型が未定 (下) | `bind(path, type=SOCK_SEQPACKET)` か `bind_seqpacket(path)` | `ListenUnixpacket(path) (*net.UnixListener, error)` |
| SEQPACKET | connect / connect_nonblocking | 同上 | `connect(path, type=...)` か `connect_seqpacket(path)` | `DialUnixpacket(path) (*net.UnixConn, error)` |
| どれも | `_ex` | 型ごとに `bind_datagram_ex` 等を足すか、`_ex` に型を渡すか | 同 | 同 |

- DGRAM の connect は相手の backlog を待たない (Linux も macOS も datagram の connect は相手と結ぶだけ。推測、未実測) ので、[DR-0003](../decisions/DR-0003-single-connect-when-standard-never-blocks.md) と同じ考えで connect を 1 つにできる。SEQPACKET の connect は stream と同じく backlog で待ちうる (推測、未実測) ので、`connect_nonblocking` も出す
- DGRAM の bind の後に listen は無い。fork-cwd の bind で親が listen する決まり ([DR-0010](../decisions/DR-0010-fork-bind-listen-by-parent.md)) は DGRAM では当たらない。DGRAM の peer 情報 (`SO_PEERCRED` 等) は connect した相手でしか意味を持たない (未実測)
- SEQPACKET は Apple の OS で標準も作れないので、経路を試さず標準と同じエラー (`EPROTONOSUPPORT`) を返す形が「標準と同じ」に合う
- Rust の SEQPACKET の返す型の候補

| 候補 | 良い面 | 悪い面 |
|---|---|---|
| `std::os::fd::OwnedFd` | std の型。どの crate にも `From<OwnedFd>` / `FromRawFd` で渡せる | ソケットとしての操作 (`accept`、`send`) を持たない。利用者が包む |
| sockat 独自の型 (`SeqpacketListener` / `SeqpacketStream` 等) | そのまま使える | 標準の型を返すという約束から外れる。std に入ったら置き換えが要る |
| 既存の crate の型 (uds、tokio-seqpacket 等) を feature の後ろで返す | 使い慣れた型 | 依存が増え、crate の版に縛られる |
| `std::os::unix::net::UnixListener` / `UnixStream` に SEQPACKET の fd を入れて返す | std の型 | 型が SOCK_STREAM を意味するので、std の約束の外 (実際に動くかは未実測)。[libs-team#898](https://github.com/rust-lang/libs-team/issues/898) の「API が同じ」の議論はこの形に近いが、std は認めていない |

## 推し

- 宛先つきの送信は案 A (connect して宛先を固定) を推す
  - stream の connect の経路と順 (relative の後の cwd の確認を含む) をそのまま使え、SPEC に足す経路が無い
  - 標準と同じ型を返し、失うものは stream の connect と同じ (無し、最終手段で `forked`)
  - connect 済みのソケットの `send` / `sendmsg` は標準のままなので、fd や資格情報を付ける送信も非同期のランタイムも、sockat が版を足さずに使える
  - 見つけた需要 (sd_notify の中継、NOTIFY_SOCKET) は宛先が固定で、`sd_notify` は呼ぶたびに新しいソケットで送るので、connect してから送っても費用が変わらない
  - B は relative を外す必要があり、FreeBSD 等で届く所が狭く、送るたびの費用と言語ごとの版の数が大きい。B の需要 (長いパスの宛先へ、1 つのソケットで宛先を変えながら送る) は今回の調査では見つけていない
- DGRAM と SEQPACKET の bind は stream の bind の経路をそのまま使う (実測で同じに動いた)
- 長いパスに bind した DGRAM に返信が届かないことは、少なくとも SPEC の「長いパスで標準と違う点」と `respelled` の説明に書く (案 a)。新しい名前 (案 b) と symlink-file の扱い (案 c) は kawaz に決めてもらう

## 未確定

- 案 A・B・C・D のどれにするか (推しは A)
- 長いパスに bind した DGRAM の失うもの: 案 a / b のどちらか。共有の置き場の symlink-file の DGRAM の bind に `recreatable-spelling` を付けるか (案 c)
- 返信を受けたい送り元 (bind してから connect) の API: bind と connect を 1 つの関数で受けるか (Go の `DialUnix(laddr, raddr)` の形)、標準のソケットを受け取って経路で connect する関数を足すか。後者は「既存のソケットを受け取る」口が増える
- API の形: 型ごとに関数を分けるか、型を引数で渡すか (言語ごとの慣習に任せるかも含む)。`_ex` の数
- Rust の SEQPACKET の返す型 (`OwnedFd` / 独自の型 / 既存の crate の型)
- 実測していないこと
  - FreeBSD・NetBSD・OpenBSD・illumos での DGRAM の経路と SEQPACKET (各言語の CI の VM で確かめる)
  - DGRAM の connect と SEQPACKET の connect が backlog で待つか
  - `/proc` の綴りへの返信が、受け手のプロセスの fd で別の所に届くこと (仕組みからの推測)
  - DGRAM の peer の資格情報 (`SO_PEERCRED`、`LOCAL_PEERCRED` は FreeBSD では stream と seqpacket だけと unix(4) に書かれる)
