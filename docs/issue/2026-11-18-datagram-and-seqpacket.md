---
title: "SOCK_DGRAM と SOCK_SEQPACKET も長いパスで使えるようにする"
status: open
category: task
created: 2026-11-18
origin: "自リポ TODO"
---

# SOCK_DGRAM と SOCK_SEQPACKET も長いパスで使えるようにする

## 概要

- SOCK_DGRAM と SOCK_SEQPACKET も同じ `sun_path` の上限に当たる
- 作る (kawaz 承認 2026-11-18)。resolve と消さない置き場 ([DR-0017](../decisions/DR-0017-resolve-through-persistent-base.md)) の上に作った
- 調査: [docs/research/2026-11-19-datagram-and-seqpacket.md](../research/2026-11-19-datagram-and-seqpacket.md)

| 型 | 考えること |
|---|---|
| SOCK_DGRAM | 宛先を毎回 `sendto` で渡すので、bind だけでなく送るたびに長いパスの問題がある。経路の当て方 (connect して宛先を固定する等) を考える |
| SOCK_SEQPACKET | stream とほぼ同じ形 (Rust の標準ライブラリには型が無い) |

## 受け入れ条件

- [x] DGRAM の bind・unbound・connect と各 `_ex` の経路と API の形を SPEC に書く ([SPEC の「関数」](../SPEC-ja.md#関数)。connect は stream の connect と同じ順)
- [x] DGRAM の bind・unbound・connect と各 `_ex` を Rust / Python / Go で実装する (Rust は `datagram::`、Python は `sockat.datagram` と `sockat.ex.datagram`、Go は SPEC の Go の形の `ListenUnixgram`・`DialUnixgram` と各 `Ex`)
- [x] 需要を調べる ([docs/research/2026-11-19-datagram-and-seqpacket.md](../research/2026-11-19-datagram-and-seqpacket.md))
- [x] SEQPACKET の API の形を決める: 専用の関数を置かず、resolve の綴りを使う (kawaz 2026-11-22。下の「SEQPACKET を resolve で使う形」。SPEC の「公開する操作」と DR-0017 に書いた)
- [ ] `datagram::send_to` / `send_to_ex` を作るか (SPEC の関数の表に載っているが、どの言語にも無い。各言語のリファレンスは、SPEC で未確定なので無いと書いている)。持ち主の裁定待ち ([QUESTIONS](../QUESTIONS.md) の DG-Q1)
- [x] 長いパスに bind した DGRAM の送り手への返信が届くかは、今ある `Spelling` (`until`・`usable_cross_uid`・`Dangling`) で表す。返信のための項目は足さない (統括 2026-11-24。[SPEC の「公開する操作」](../SPEC-ja.md#公開する操作))

## SEQPACKET を resolve で使う形 (2026-11-22、各言語のマニュアルのページを書く中で確かめた)

SEQPACKET の直接のラッパーになる API (`seqpacket::`) は、無くてよい (kawaz 2026-11-22)。マニュアルで「resolve で作ったパスを使えばよい」と案内すれば、利用者は困らない。下は、各言語が resolve で SEQPACKET を動かして確かめたことの記録 (後で専用の関数を考える時が来たら、材料になる)。

### 使い方の形 (sockat-rs。他の言語もこの形にそろえる)

| 場面 | 手順 |
|---|---|
| 待ち受ける | ソケットを先に作る → `resolve_for_bind` → 綴りに bind・listen → 失敗したら `cleanup()` してからそのエラーを返す → 成功したら `socket_file()` で `SocketFile` を受け取る |
| つなぐ | ソケットを先に作る → `resolve_for_connect` の綴りに connect → 結果によらず、すぐ `cleanup()` (その後も双方向に通る)。同じ相手に何度もつなぐなら、綴りを持ち続けて最後に `cleanup()` |
| 終わる時 | `SocketFile` の `remove()` の後に listener を閉じる |

### 専用の関数を決める時の材料 (sockat-rs)

- Rust は std に SEQPACKET の型が無いので、「標準の型を返す」形を取れない (サンプルは socket2 の `Socket`。accept の相手のアドレスも socket2 の型)
- macOS は `AF_UNIX` の `SOCK_SEQPACKET` を作れない (`EPROTONOSUPPORT`)。専用の関数を作るなら、macOS で返すエラーを決める
- resolve を使う形は、片付けの順番を利用者が毎回書くことになる。`resolve_for_bind` の後で失敗する所 (アドレスの組み立て、bind、listen) で早く返すと E が残る。既定の bind はこれを中で済ませている
- `socket_file()` は bind の後・listener を閉じる前に呼ぶ。bind の後で `socket_file()` 自体が失敗すると、ソケットのファイルと E が両方残る
- SEQPACKET で `getsockname` が bind の綴りを返すことは、確かめていない
- 動かして確かめたのは Linux だけ (docker 3 種)。BSD と illumos は確かめていない

### sockat-py が Linux の docker で動かして分かったこと (2026-11-22)

- resolve の綴りは link-dir か link-file だけなので、`resolve_for_bind` は既定の bind より届く範囲が狭い。Linux ではファイル名がおよそ 80 バイトを超えると `ENAMETOOLONG` (境目は pid の桁で動く)。同じパスを stream の `sockat.ex.bind` は thread-cwd で bind できた。SEQPACKET 専用の関数を作るなら、thread-cwd の経路が要る
- 自分で作った標準のソケットなので、アドレスを元のパスで返す subclass は効かない (`getsockname` は bind の綴りを返す)
- つないだ側の `getpeername` は、自分が connect に使った綴りでなく、相手が bind した綴りを返す (accept 側の `getsockname` も同じ)
- `cleanup` の後に、その綴りで connect し直すと `ENOENT` (つなぎ直す間は綴りを持ち続ける)
- stream の `sockat.connect` で SEQPACKET の listener につなぐと `EPROTOTYPE`
- macOS は `socket.socket(AF_UNIX, SOCK_SEQPACKET)` が `EPROTONOSUPPORT`

### sockat-go が動かして分かったこと (2026-11-22)

- 形は stream の resolve の使い方と同じで、`unixpacket` に固有の扱いは無い (`ResolveForBind` の綴りで `net.ListenUnix("unixpacket")` → 失敗したら `Cleanup` → `SetUnlinkOnClose(false)` → `SocketFile()` → 終わる時は `Remove` の後に `Close`。connect は `ResolveForConnect` の綴りで `DialUnix` → すぐ `Cleanup`)
- `unixpacket` の listener の `Close` も、stream と同じく綴りで unlink する。長いパスで `Close` だけだと、ファイルは消えるが E が 1 つ置き場に残る
- Linux・NetBSD・OpenBSD・illumos の CI で通った。macOS は `socket: protocol not supported`
- FreeBSD の CI で止まったのは、sockat の問題ではなかった (sockat-go が切り分けた。2026-11-22)。FreeBSD は `write(2)` で送った物に SEQPACKET の記録の境目を付けない (FreeBSD 15.1 の socket(2): 境目は `send(2)` / `sendmsg(2)` の `MSG_EOR` で付ける。`write(2)` では付けられない)。Linux・NetBSD・OpenBSD・illumos は送るたびに 1 記録になる。試験は 2 回書いて 2 回読んでいたので、FreeBSD では 1 記録にまとまり、両側が 2 回目の読みで待ち合った。標準だけの短いパスでも同じになり、resolve の綴りは正しく bind したソケットに届いていた。FreeBSD で記録ごとに送るなら `MSG_EOR` を付ける (Go の標準の `Write` には付ける口が無く、`SyscallConn` 経由の `sendmsg` が要る)。言語によらない OS の事実
