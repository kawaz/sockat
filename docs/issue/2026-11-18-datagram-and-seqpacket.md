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
- 今の対象は SOCK_STREAM だけ。作る (kawaz 承認 2026-11-18)。今の SPEC の変更 (sockat-rs 0.4.0 等) を出し終えてから着手する

| 型 | 考えること |
|---|---|
| SOCK_DGRAM | 宛先を毎回 `sendto` で渡すので、bind だけでなく送るたびに長いパスの問題がある。経路の当て方 (connect して宛先を固定する等) を考える |
| SOCK_SEQPACKET | stream とほぼ同じ形 (Rust の std には型が無い) |

## 受け入れ条件

- [ ] 型ごとの経路の当て方と API の形を SPEC に書く (SOCK_DGRAM の宛先つきの送信は、送るたびに経路を当てるか、connect して宛先を固定してもらうかを比べて決める)
- [ ] Rust / Python / Go で実装する (Rust は std に SOCK_SEQPACKET の型が無いので返す型も決める)
- [ ] 需要を調べる (systemd の NOTIFY_SOCKET、syslog の /dev/log 等で長いパスに当たる報告)
