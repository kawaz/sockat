---
title: "届く範囲の表が、sockat-ts の D のロックの制約を持っていない"
status: open
category: task
created: 2026-11-22
origin: "自リポ TODO"
---

# 届く範囲の表が、sockat-ts の D のロックの制約を持っていない

## 概要

- 届く範囲の表 ([pages/reach](../../pages/reach/README-ja.md)) は、既定の bind の illumos の行を「全部の言語で 1–76 バイトまで届く」としている
- sockat-ts の README と [言語ごとの注意](../../pages/langs-ja.md) は、「illumos は D をロックする手段が無く、長いパスの bind と resolve は `ENAMETOOLONG`」「Linux で `flock(1)` が無いと同じ」としている
- `pages/reach/model.json` の `ts-node`・`ts-bun` の `lacks` は経路の名前 (widened・thread-cwd・at・thread-cwd-direct・at-direct) だけで、D をロックできない環境を表す条件が無い
- sockat-ts のセッションの答え (2026-11-22、実装から): sockat-ts の README が正しい。`src/config.ts` の `lockMethodOn` が illumos で「ロックの手段が無い」を返し、D を使う経路 (bind の link-dir・link-file、resolve の 2 つ) が使えない。既定の connect は D を作らないので届く。illumos の実機では動かしていない
- 表の側 (model.json と gen.py) を直す

## 受け入れ条件

- [ ] sockat-ts の illumos と、`flock(1)` の無い Linux での長いパスの bind / resolve の結果を確かめる
- [ ] 表か sockat-ts の文書の、違っている方を直す
