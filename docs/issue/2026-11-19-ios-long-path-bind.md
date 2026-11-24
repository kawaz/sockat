---
title: iOS 等 macOS 以外の Apple の OS で長いパスを bind する経路を決める
status: open
category: idea
created: 2026-11-19
origin: 自リポ TODO
---

# iOS 等 macOS 以外の Apple の OS で長いパスを bind する経路を決める

kawaz が iOS で何かする機会ができた時に、実機で確かめて決める (kawaz 2026-11-19)。今は SPEC で「Android と macOS 以外の Apple の OS は全体が未確認」のまま。

## 分かっていること (推測を含む、どれも未確認)

| 経路 | iOS で |
|---|---|
| thread-cwd (`pthread_fchdir_np`) | 非公開 API。App Store の審査で弾かれる危険がある (外部の指摘) |
| link-dir の procB | `/proc` が無い |
| fork-cwd | サンドボックスで禁止。sockat は fork の経路を作らない ([DR-0017](../decisions/DR-0017-resolve-through-persistent-base.md) の「fork をしない」) |
| link-dir の実パス (`B/D/E/<ファイル名>`) | 手段が要らず、綴りは絶対パス。サンドボックスで他のアプリから見えず作り直されない。bind の順で thread-cwd より先に試す |
| widened (広げた sockaddr) | 253 バイトまで届くが、返るアドレスが途中で切れて読む側 (CPython、Go の `net.FileConn` 等) を壊す。DR-0017 で bind には使わない (案 S) と決め、最終手段も置かないので、iOS でも bind の経路にならない |

## 確かめること

- アプリが書ける置き場の候補と、その綴りの長さ (コンテナの一時ディレクトリ `/var/mobile/Containers/Data/Application/<UUID>/tmp/` は 81 バイト前後で、ファイル名が 11 バイトほどしか残らない見込み。`/tmp` に書けるか)
- 置き場の symlink で bind / connect が届き、片付けで何も残らないこと
- シミュレータは macOS の上で動きサンドボックスが違うので、実機で確かめる

## 関連

- [DR-0017](../decisions/DR-0017-resolve-through-persistent-base.md) (広げた sockaddr の bind を不採用にした理由、綴りの性質 `Spelling`、最終手段を置かない判断)
