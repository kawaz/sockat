---
title: "経路ごとの費用を測り、届く範囲の表と技術説明に載せる"
status: open
category: task
created: 2026-11-24
origin: "自リポ TODO"
---

# 経路ごとの費用を測り、届く範囲の表と技術説明に載せる

## 概要

- 経路ごとの費用 (syscall の数、時間、置き場への書き込み) をベンチマークで測り、届く範囲の表と経路の説明に数字で載せる ([DR-0017](../decisions/DR-0017-resolve-through-persistent-base.md) の Consequences、[resolve と置き場 B の issue](archive/2026-11-20-resolve-and-persistent-base.md) の「操作ごとに重視すること」)
- connect で重視するのは手数・速さ・IO の回数・負荷 (kawaz 2026-11-20、DR-0017 の Context)。connect の順は、書き込みもスレッドも要らない経路を先にしている

## 測る物

経路は SPEC の [bind の順](../SPEC-ja.md#bind-の順) と [connect の順](../SPEC-ja.md#connect-の順) の物。

| 操作 | 経路 |
|---|---|
| bind | standard<br>link-dir (procB)<br>link-dir (実パス)<br>link-file<br>thread-cwd<br>at |
| connect | standard<br>proc-direct<br>relative<br>widened<br>at-direct<br>thread-cwd-direct<br>link-file |

経路ごとに測ること:

- syscall の数
- 時間
- 置き場への書き込みの有無 (B・D・E を作るか)

## 測り方の候補

- Linux: `strace -c` で syscall の数を数える
- macOS: `dtruss` か同等の道具で syscall の数を数える
- 時間: 経路ごとの所要時間を測る
- 経路を 1 つずつ強制するのは、各言語の試験と同じくパッケージの中から各経路を直接呼ぶ形 ([SPEC の「各実装に求めること」](../SPEC-ja.md#各実装に求めること))

## 載せる場所

- 届く範囲の表 (`pages/reach/model.json` から作る)
- 技術説明 (`pages/technical`) の経路の説明

## 受け入れ条件

- [ ] 測る言語・OS・測り方を決める
- [ ] bind の経路ごとに、syscall の数・時間・置き場への書き込みの有無を測る
- [ ] connect の経路ごとに、syscall の数・時間・置き場への書き込みの有無を測る
- [ ] 測った環境・手順・出力を `docs/findings/` に残す
- [ ] 届く範囲の表に数字を載せる (`pages/reach/model.json` を直し、`python3 -I pages/reach/gen.py` で作り直す)
- [ ] 技術説明 (`pages/technical`、日英) の経路の説明に数字を載せる

## 関連

- [DR-0017](../decisions/DR-0017-resolve-through-persistent-base.md)、[resolve と置き場 B の issue](archive/2026-11-20-resolve-and-persistent-base.md)
- [届く範囲の表](../../pages/reach/README-ja.md)、[技術説明](../../pages/technical-ja.md)
