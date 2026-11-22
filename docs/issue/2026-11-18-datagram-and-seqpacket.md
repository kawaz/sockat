---
title: "SOCK_DGRAM と SOCK_SEQPACKET も長いパスで使えるようにする"
status: blocked
category: task
created: 2026-11-18
origin: "自リポ TODO"
blocked_by: resolve-and-persistent-base
---

# SOCK_DGRAM と SOCK_SEQPACKET も長いパスで使えるようにする

## 概要

- SOCK_DGRAM と SOCK_SEQPACKET も同じ `sun_path` の上限に当たる
- 今の対象は SOCK_STREAM だけ。作る (kawaz 承認 2026-11-18)
- 経路を組み直す resolve の案 ([2026-11-20-resolve-and-persistent-base](2026-11-20-resolve-and-persistent-base.md)) の上に作るので、その案が決まってから着手する
- 調査: [docs/research/2026-11-19-datagram-and-seqpacket.md](../research/2026-11-19-datagram-and-seqpacket.md)

| 型 | 考えること |
|---|---|
| SOCK_DGRAM | 宛先を毎回 `sendto` で渡すので、bind だけでなく送るたびに長いパスの問題がある。経路の当て方 (connect して宛先を固定する等) を考える |
| SOCK_SEQPACKET | stream とほぼ同じ形 (Rust の std には型が無い) |

## 受け入れ条件

- [ ] 型ごとの経路の当て方と API の形を SPEC に書く (SOCK_DGRAM の宛先つきの送信は、送るたびに経路を当てるか、connect して宛先を固定してもらうかを比べて決める)
- [ ] Rust / Python / Go で実装する (Rust は std に SOCK_SEQPACKET の型が無いので返す型も決める)
- [ ] 需要を調べる (systemd の NOTIFY_SOCKET、syslog の /dev/log 等で長いパスに当たる報告)

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
