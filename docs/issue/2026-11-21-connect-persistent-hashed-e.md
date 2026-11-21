---
title: 接続先のハッシュの名前の E をプロセスをまたいで使い回す案
status: open
category: idea
created: 2026-11-21
origin: 自リポ TODO
---

# 接続先のハッシュの名前の E をプロセスをまたいで使い回す案

検討中。方針は決まっていない。

## 案

- B の直下に、接続先 (ソケットのファイル、またはディレクトリ) の realpath のハッシュを名前にした E を置き、プロセスをまたいで使い回す。無ければ作り、あれば指す先を確かめて使い、消さない
- 名前が接続先で決まるので、同じ接続先を何プロセス繰り返しても作るのは最初の 1 回だけ (例: `hyoui list` を 10 回実行)。E は接続先の数で頭打ちになる
- 今の E は名前をカウンタや乱数で一意にしているので、プロセスごと・呼び出しごとに増える

## connect に使う場合

- 掃除の心配が無い (kawaz 2026-11-21 の指摘): connect の綴りは相手に残らないので、E が OS の掃除で消えても次の connect が作り直す
- 今の既定の connect は書き込みの要らない経路を先に試すので、効くのは最後の手段 (link-file) まで落ちる環境と `resolve_for_connect`

## bind に使う場合

- 未検討。D をやめると溜まる問題 (AS-Q1) と exec をまたぐ問題が消えうるが、ロックの無い E が OS の掃除 (Linux の systemd-tmpfiles の 10 日等) で消されないかが分かっていない

## 統括の案 (connect の細部、採否は未定)

- 名前: 指す先のバイト列の SHA-256 の 16 進小文字の先頭 12 文字 (衝突は readlink で見分ける)
- 指す先が違う E: 乱数の名前で作って rename で上書き
- connect の順: 「既にある E を使う」を thread-cwd-direct の前に、「E を作る」を最後に (要らない時は書かない原則を保ち、2 回目からはスレッドも立てない)
- E が途中で消えた `ENOENT` は 1 回だけ作り直してやり直す
- `resolve_for_connect` の綴りも同じ E にし、`cleanup()` は何もしない

## 関連

- [DR-0017](../decisions/DR-0017-resolve-through-persistent-base.md)、[SPEC の connect の順](../SPEC-ja.md#connect-の順)、[AS-Q1](../QUESTIONS.md)
