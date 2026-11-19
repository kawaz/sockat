# DR-0016: bind が symlink を辿る OS では、ソケットのファイルを指す symlink を通して bind する (symlink-file)。経路の名前を「手段 + 何についてか」にそろえる

- Status: Active
- Date: 2026-11-19

## Context

- 今の bind は綴りに `R/<ファイル名>` を含むので、ファイル名の上限がある (Apple の OS / BSD 92、Linux / illumos 96) ([DR-0012](DR-0012-own-directory-and-thread-cwd.md))
- 短い置き場に、まだ無い元のパスを指す symlink を作り、その symlink に bind すると、bind が最後の要素の symlink を辿る OS では元のパスにソケットができる (kawaz の案)。綴りにファイル名が出ないので、ファイル名の上限が無くなる
- 実測 (2026-11-19、macOS 26 と Linux の docker。[findings](../findings/2026-11-19-bind-through-file-symlink.md))

| 場面 | macOS | Linux (docker) |
|---|---|---|
| まだ無い先を指す symlink に bind | 辿って元のパスにソケットを作る | 辿らず `EADDRINUSE`。元のパスには何もできない |
| カーネルが返すアドレス (`getsockname`) | symlink の綴り (元のパスではない) | 該当なし |
| 元のパスに既に物がある (通常ファイル、生きたソケット、古いソケットのファイル) | `EADDRINUSE`。元の物はそのまま | `EADDRINUSE` (先が無い時と同じエラー)。元の物はそのまま |
| ソケットの fd の `fstat` と元のパスの `lstat` の `(st_dev, st_ino)` | 一致しない (`st_dev` が -1) | 該当なし |

- FreeBSD・NetBSD・OpenBSD・illumos で辿るかは未確認
- 経路の名前の `symlink` は、connect (ソケットのファイルを指す symlink) と `bind_ex` の最終手段 (ソケットのディレクトリを指す symlink) の別の経路を同じ名前で呼んでいた。bind にファイルを指す symlink の経路を足すと、bind にも 2 つが並ぶ。1.0.0 の前なので名前を変えられる

## Decision

### bind の symlink-file

- bind の既定の順で、standard の次に symlink-file を試す。macOS の bind の順は standard → symlink-file → thread-cwd → fork-cwd。D をどこにも作れない時の `-sockdir` の流れは今のまま
- やり方: 安全な置き場 (connect の symlink-file と同じ候補と条件) に、元のパスのソケットのファイルの綴り (相対パスなら cwd を前に付ける) を指す symlink `<置き場>/sockat.XXXXXXXXXX` を作り、その綴りで bind して、すぐ消す。消すのは成功でも失敗でも
- 辿るかどうかは実行時に見分ける: bind が `EADDRINUSE` を返した時に元のパスを `lstat` し、無ければ (`ENOENT`) カーネルが辿らなかったとみなして、この経路を使えないとして次へ進む (`skipped` に入る)。あれば本当の `EADDRINUSE` として返す (経路の失敗の扱いどおり、次は試さない)
- 届く長さ: 綴りは `<置き場>/sockat.XXXXXXXXXX` で、ファイル名が出ないので、ファイル名の長さによらない (元のパス全体は PATH_MAX まで)
- 失うもの: `respelled` だけ。カーネルが返すアドレスは symlink の綴り。その綴りで unlink しても、最後の要素の symlink は辿られず置き場の中の項目が消えるだけ (共有の sticky な置き場では他人の項目は消せない) なので、ディレクトリを指す symlink-dir と違い、無関係なファイルを消させない。`recreatable-spelling` は付かない
- 元のパスの最後の要素に bind の前から symlink が置かれていた時に bind がそれを辿るのは標準の bind の性質で、sockat は確かめない (責務外。kawaz 2026-11-19)。SPEC の「長いパスで標準と違う点」には書かない

### 経路の名前

| 今まで | これから |
|---|---|
| `fork` | `fork-cwd` |
| `fork-sockdir` | `fork-cwd-sockdir` |
| `fork-direct` | `fork-cwd-direct` |
| connect の `symlink` (ソケットのファイルを指す) | `symlink-file` |
| `bind_ex` の最終手段の `symlink` (ソケットのディレクトリを指す) | `symlink-dir` |

- 名前は「手段 + 何についてか」。手段は thread-cwd・fork-cwd・proc・at・symlink-file・symlink-dir・relative・widened。接尾辞 `-sockdir` は R をソケットのディレクトリに置く形、`-direct` は R を通さずファイル名で渡す形
- 失うものの `forked` は経路の名前でないので変えない
- 経路の名前は日英で同じ ASCII

理由:

- macOS の bind でファイル名の上限が無くなり、スレッドも fork も要らない
- 綴りの最後が乱数の symlink の名前なので、その綴りで unlink しても置き場の中の項目しか消えない
- 辿らない OS (Linux で実測) では bind が `EADDRINUSE` を返して元のパスに何も作らないので、実行時に見分けて次へ進めば何も残さない
- 経路の名前を「手段 + 何についてか」にそろえると、ファイルを指す symlink とディレクトリを指す symlink を名前で見分けられる (kawaz 裁定 2026-11-19)

## Alternatives Considered

- 案 A: bind の後に元のパスを `lstat` して、ソケットが元のパスにできたかを確かめる
  - 不採用理由: 元のパスの最後の要素に bind の前から置かれていた symlink を辿るのは標準の bind の性質で、sockat の責務外 (kawaz 2026-11-19)
- 案 B: bind したソケットの fd の `fstat` と元のパスの `lstat` の `(st_dev, st_ino)` を照らし合わせて確かめる
  - 不採用理由: ソケットの fd の `fstat` はソケットのファイルの inode を返さない (macOS で `st_dev` が -1、inode も一致しない。[findings](../findings/2026-11-19-bind-through-file-symlink.md) で実測)

## Consequences

- SPEC の経路の名前の表 (bind)、試す順番、各経路の節 (symlink-file の節に bind の段を足し、symlink-dir の節を作る)、symlink の置き場と名前、どこから届かなくなるか (macOS の bind はファイル名の上限が無くなる。他の OS は辿るかが未確認なので数えない)、失うもの、試験の観点を直す
- 経路の名前を `fork-cwd`・`fork-cwd-sockdir`・`fork-cwd-direct`・`symlink-file`・`symlink-dir` に変える (SPEC の表・見出し・リンク・本文、[DR-0012](DR-0012-own-directory-and-thread-cwd.md)、[DR-0015](DR-0015-ex-with-last-resort-and-diagnostics.md))
- 試験: 辿る OS で通り `losses` が `respelled` だけ、辿らない OS で `skipped` に入り何も残らない、元のパスに物がある時は `EADDRINUSE` で次を試さない
- FreeBSD・NetBSD・OpenBSD・illumos で辿るかは、各言語の CI の VM で確かめる

## 関連

- [docs/SPEC-ja.md](../SPEC-ja.md) の「経路の名前」「試す順番」「symlink-file」「symlink-dir」「symlink の置き場と名前」「どこから届かなくなるか」「実装が確かめる試験の観点」
- [ファイルを指す symlink を通した bind の issue](../issue/archive/2026-11-19-bind-through-file-symlink.md)、[実測](../findings/2026-11-19-bind-through-file-symlink.md)
- 裁定: kawaz (2026-11-19。経路の名前の変更、bind に symlink-file を足す)
- [DR-0012](DR-0012-own-directory-and-thread-cwd.md)、[DR-0015](DR-0015-ex-with-last-resort-and-diagnostics.md)
