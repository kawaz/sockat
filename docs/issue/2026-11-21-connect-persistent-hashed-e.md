---
title: 既定の connect の link-file を、接続先のハッシュの名前の使い回す E にする
status: open
category: task
created: 2026-11-21
origin: 自リポ TODO
---

# 既定の connect の link-file を、接続先のハッシュの名前の使い回す E にする

## 決まったこと (kawaz 2026-11-21)

- 既定の connect の link-file は、B の直下に「接続先のソケットのファイルの realpath のハッシュ」を名前にした E を置き、プロセスをまたいで使い回す。無ければ作り、あれば指す先を確かめて使い、消さない
- 理由: 名前が接続先で決まるので、同じ接続先への connect を何プロセス繰り返しても作るのは最初の 1 回だけ (例: `hyoui list` を 10 回実行)。E は接続先の数で頭打ちになり、片付けが要らない
- 掃除の心配は無い: connect の綴りは相手に残らないので、E が OS の掃除で消えても次の connect が作り直す
- bind は今の D / E のまま (bind は頻繁に実行しないので)

## 決めること (統括)

- ハッシュの関数と名前の長さ (例: SHA-256 を base62 で 10 文字)。3 言語でそろえる
- 指す先が違う E (衝突、張り替え) の扱い: 別名で作って rename で上書きする
- E を確かめてから connect するまでに E が消えた時の `ENOENT` の見分け (E を確かめて 1 回だけ作り直す)
- connect の順: 作った後は書き込みもスレッドも要らないので、thread-cwd-direct より前に出すか (初回だけ置き場に書く)
- `resolve_for_connect` の綴りもこの E にするか (`cleanup()` は何もしない口になる)
- SPEC の約束「既定の connect は B に何も残さない」と適合試験の確かめを「接続先ごとに E を 1 つ残す」に直す

## 残り

- [ ] 上の「決めること」を決めて DR-0017 と SPEC / SPEC-routes (日英) に入れる
- [ ] 適合試験の表を直す
- [ ] 3 言語に実装して公開する

## 関連

- [DR-0017](../decisions/DR-0017-resolve-through-persistent-base.md) の「connect の試す順」、[SPEC の connect の順](../SPEC-ja.md#connect-の順)
- [AS-Q1](../QUESTIONS.md) (bind の死んだ D の自動の片付け) とは別の話
