---
title: 言語によらない適合試験 (同じ入力で同じ losses・route・errno になるか)
status: resolved
category: task
created: 2026-11-19
origin: 外部の指摘
close_reason: implemented
---

# 言語によらない適合試験

経路は 17 個あり、3 言語 (今後は 5 言語) がそれぞれ試験を書いている。2026-11-19 だけでも skipped の中身や失敗時の route で言語ごとの食い違いを何度も直した。人の突き合わせに頼らず、同じ入力で同じ結果になることを機械で確かめる。

形 (試験用 CLI の入出力、場面の表、比べ方) の正本は [docs/design/conformance.md](../../design/conformance.md)。

## 受け入れ条件

- [x] 各言語の試験用 CLI (3 言語)、ハブの `just conformance`、経路を強制しない場面 20 (最終手段の場面、言語が作らない経路で組を分けて比べる形を含む) で 3 言語に差が無い
- [x] スクリプトに、Linux のコンテナで流す形と、経路を強制する条件の作り方を足す (ライブラリに強制の口を作らない。kawaz 裁定 2026-11-20、[conformance.md](../../design/conformance.md) の「経路を強制する場面」)
- [x] 経路を強制する場面を場面の表に足し、全言語で差が無い (`just conformance --on linux` で 23 場面が一致。Bun は `/proc` が見えないと起動しないので、13 場面は対象外)

## 閉じた理由

Linux のコンテナで経路を強制する形と強制の場面 23 を足し、手元 25 場面・Linux 23 場面で 5 つの実行環境 (rs・py・go・ts-node・ts-bun) に差が無いことを確かめた (2026-11-24)。
