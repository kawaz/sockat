---
title: ファイルを指す symlink を通した bind でファイル名の上限を無くす
status: resolved
category: task
created: 2026-11-19
origin: 自リポ TODO
close_reason: documented
close_ref: docs/decisions/DR-0016-bind-through-file-symlink.md
---

# ファイルを指す symlink を通した bind でファイル名の上限を無くす

kawaz の案 (2026-11-19)。bind が最後の要素の symlink を辿る OS では、短い置き場に元のパス (`<長いディレクトリ>/<ファイル名>`) を指す symlink `<置き場>/sockat.XXXXXXXXXX` を作り、そこに bind すれば、綴りにファイル名が出ないのでファイル名の上限が無くなる (元のパス全体は PATH_MAX まで)。

## 分かっていること (2026-11-19 の実測)

| | macOS 26 | Linux (docker) |
|---|---|---|
| まだ無い先を指す symlink に bind | 辿って先にソケットを作る | 辿らず `EADDRINUSE` |
| ソケットのファイルを指す symlink を通して connect | 通る | 通る |
| ソケットの fd の `fstat` とソケットのファイルの `lstat` の `(st_dev, st_ino)` | 一致しない | 一致しない |

## 良い点 (見込み)

- ファイル名の上限が無くなる (今の bind はファイル名 92 バイトまで)
- スレッドも fork も要らない
- 綴りの最後が乱数の symlink の名前なので、その綴りで unlink しても消えるのは置き場の中の項目だけ (ディレクトリを指す symlink の形と違い、作り直された symlink が別のディレクトリの同じ名前のファイルを消させることが無い)

## 責務の外

- 元のパスの最後の要素に bind の前から symlink が置かれていた時に、bind がそれを辿って別の場所にソケットを作るのは標準の bind の性質。sockat は確かめない (kawaz 2026-11-19)

## 確かめること

- macOS: 綴り・カーネルが返すアドレス、元のパスに既に物がある時のエラー (`EADDRINUSE` と「辿らない OS」の見分け方)、symlink の先が symlink の時、置き場が持ち主だけの `$TMPDIR` の時と共有の `/tmp` の時、片付けで何も残らないこと
- FreeBSD・NetBSD・OpenBSD・illumos で辿るか (手元に無い。各言語の CI の VM で)
- 結果で、辿る OS の bind の既定の経路に足すか、どの位置か、失うものは何か (`respelled` だけか) を決める
