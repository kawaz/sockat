---
title: "SOCK_DGRAM と SOCK_SEQPACKET も長いパスで使えるようにする"
status: open
category: idea
created: 2026-11-18
origin: "自リポ TODO"
---

# SOCK_DGRAM と SOCK_SEQPACKET も長いパスで使えるようにする

## 概要

- SOCK_DGRAM と SOCK_SEQPACKET も同じ `sun_path` の上限に当たる
- 今の対象は SOCK_STREAM だけ。将来の拡張の候補

| 型 | 考えること |
|---|---|
| SOCK_DGRAM | 宛先を毎回 `sendto` で渡すので、bind だけでなく送るたびに長いパスの問題がある。経路の当て方 (connect して宛先を固定する等) を考える |
| SOCK_SEQPACKET | stream とほぼ同じ形 (Rust の std には型が無い) |

## 受け入れ条件

- [ ] 対象に入れるか、型ごとに経路の当て方を SPEC に書くかを決める
