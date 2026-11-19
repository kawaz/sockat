# 閉じたソケットのファイルの inode 番号の使い回し (discard の同一性)

2026-11-19。`bind_ex` の `discard()` は、覚えた `(st_dev, st_ino)` と今のパスの `lstat` が同じ時だけ消す (SPEC)。sockat-rs と sockat-py の「置き換えたソケットのファイルを discard が消さない」試験が GitHub の ubuntu で落ちたので、inode 番号がいつ使い回されるかを実測した。

## 目的

ソケットのファイルを消して同じパスに別の物を作った時、`(st_dev, st_ino)` が元と同じになる場面を、listener を開いているか閉じたかで分けて確かめる。

## 環境

- Linux: `docker run --rm --privileged python:3.13-slim`。カーネル 7.2.12 (OrbStack の VM)。ext4 は 64MB のイメージを `mkfs.ext4` して loop mount。btrfs は named volume、tmpfs は `--tmpfs`、overlay はコンテナの `/tmp`
- macOS 26 (Darwin 25.5.0) の `/tmp` (APFS)
- Python 3 標準ライブラリだけ (`python3 -I`)。パスは短いパス (経路を通らない、標準の bind)
- 1 回 = bind → `lstat` → (閉じる) → unlink → 同じパスに別のソケットを bind → `lstat` → 比べる。各 20 回

## 結果の表

| 場面 | ext4 | btrfs | tmpfs | overlay | APFS |
|---|---|---|---|---|---|
| listener を開いたまま unlink して作り直す | 別の番号 (0/20) | 別 (0/20) | 別 (0/20) | 別 (0/20) | 別 (0/20) |
| listener を閉じてから unlink して作り直す | **同じ番号 (20/20)** | 別 (0/20) | 別 (0/20) | 別 (0/20) | 別 (0/20) |
| 閉じる前に `O_PATH \| O_NOFOLLOW` でソケットのファイルを開いて持ち、閉じてから作り直す | 別 (0/20) | 未測 | 未測 | 未測 | 該当なし (`O_PATH` が無い) |
| ext4 で使い回された時の birth time / ctime (`stat -c '%w %z'`) | 元と違う (20/20、差はおよそ 0.6ms) | | | | |

- sockat-rs のセッションも ext4 で同じことを確かめた (3 回とも `(1792,13)`)。試験も ext4 の `/tmp` で落ちる
- sockat-py の CI (GitHub Actions の VM、run 44468917295) では、FreeBSD と NetBSD で、閉じてから消して作り直した物を `discard()` が消した (py の `discard()` が消すのは `(st_dev, st_ino)` が一致した時だけなので、FreeBSD の UFS と NetBSD の FFS でも番号が使い回されたと読める。番号そのものはログに無く、消された結果からの推定)
- OpenBSD・illumos と FreeBSD の ZFS は未測

## 分かったこと

- bind したソケットは、カーネルがソケットのファイルの inode を参照し続ける (Linux の `unix_sock` の `path`)。listener が開いている間は、ファイルを unlink しても inode は解放されず、番号も使い回されない
- listener を閉じると inode が解放され、ext4 は次に作る物にすぐ同じ番号を渡す。この時 `(st_dev, st_ino)` では置き換えを見分けられず、`discard()` は置き換え先を消す
- Linux では `O_PATH` の fd でソケットのファイルを掴めば、listener を閉じた後も番号は使い回されない
- birth time と ctime は今回のカーネルでは置き換えを見分けたが、時刻の粒度が tick 単位のカーネルで同じ tick に作り直した時に見分けられるかは未確認

## 未確認

- OpenBSD・illumos での使い回しと、FreeBSD・NetBSD での番号の直接の観測
- 古いカーネル (時刻の粒度が粗い) での birth time / ctime の衝突
