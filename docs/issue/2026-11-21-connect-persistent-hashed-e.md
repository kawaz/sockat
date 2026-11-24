---
title: 接続先のハッシュの名前の E をプロセスをまたいで使い回す案
status: open
category: idea
created: 2026-11-21
origin: 自リポ TODO
---

# 接続先のハッシュの名前の E をプロセスをまたいで使い回す案

検討中。方針は決まっていない。

- 名前の作り方 (指す先のバイト列の SHA-256 の 16 進小文字の先頭 12 文字) と置き換え方 (指す先が違えば乱数の名前で作って rename で置き換える) は、CLI の既定の `resolve` が採った ([DR-0018](../decisions/DR-0018-cli-resolve-with-reused-hashed-link.md))。実装は sockat-rs の `cli/`
- ライブラリの connect と `resolve_for_connect` には入れていない
- 残っているのは、ライブラリに入れるか

## 案

- B の直下に、接続先 (ソケットのファイル、またはディレクトリ) の realpath のハッシュを名前にした E を置き、プロセスをまたいで使い回す。無ければ作り、あれば指す先を確かめて使い、消さない
- 名前が接続先で決まるので、同じ接続先を何プロセス繰り返しても作るのは最初の 1 回だけ (例: `hyoui list` を 10 回実行)。E は接続先の数で頭打ちになる
- ライブラリの今の E は、名前がプロセスの中のカウンタか乱数で、同じ接続先でもプロセスをまたいで使い回さない ([SPEC-routes の D と E](../SPEC-routes-ja.md#d-と-e))
  - resolve (`resolve_for_bind`・`resolve_for_connect`) と `_ex` の bind の E は呼び出しごとに作り、`cleanup` まで残る
  - 既定の bind の link-dir の E は (D, ソケットのディレクトリ) ごとに 1 つを使い回す。D は (プロセス, B) ごとなので、プロセスごとに増える
  - thread-cwd・at の E と既定の connect の link-file の E は呼び出しごとに作り、呼び出しの中で消す

## connect に使う場合

- 掃除の心配が無い (kawaz 2026-11-21 の指摘): connect の綴りは相手に残らないので、E が OS の掃除で消えても次の connect が作り直す
- 今の既定の connect は書き込みの要らない経路を先に試すので、効くのは最後の手段 (link-file) まで落ちる環境と `resolve_for_connect`
- 既定の connect が置き場に書くのは次の時だけ (ディレクトリが 100 バイト等に長くても、他は書かない)
  - NetBSD・OpenBSD・illumos で、cwd からの相対パスが収まらない
  - Linux で `/proc` を使えず、cwd からの相対パスが収まらず、スレッドの cwd を使えないかファイル名が 107 バイトを超える
  - Linux で `/proc` があっても、ファイル名が約 90 バイトを超え、スレッドの cwd を使えない
  - macOS で、パス全体が 253 バイトを超え、ファイル名が 103 バイトを超える
- 見立て (kawaz 2026-11-21): まれな場合の最適化なので、今は入れない。該当する環境の利用者が出たら再検討する

## bind に使う場合

- 未検討。D をやめると溜まる問題と exec をまたぐ問題が消えうるが、ロックの無い E が OS の掃除 (Linux の systemd-tmpfiles の 10 日等) で消されないかが分かっていない

## 統括の案 (connect の細部、採否は未定)

- 名前: 指す先のバイト列の SHA-256 の 16 進小文字の先頭 12 文字 (衝突は readlink で見分ける)
- 指す先が違う E: 乱数の名前で作って rename で上書き
- connect の順: 「既にある E を使う」を thread-cwd-direct の前に、「E を作る」を最後に (要らない時は書かない原則を保ち、2 回目からはスレッドも立てない)
- E が途中で消えた `ENOENT` は 1 回だけ作り直してやり直す
- `resolve_for_connect` の綴りも同じ E にし、`cleanup()` は何もしない

## 関連

- [DR-0017](../decisions/DR-0017-resolve-through-persistent-base.md)、[SPEC の connect の順](../SPEC-ja.md#connect-の順)
