# DR-0008: 安全でない置き場は、自分専用のディレクトリを fd で掴んで symlink の経路に使う

- Status: Active
- Date: 2026-11-18

## Context

- Linux で seccomp の filter が掛かり (スレッド cwd の経路が使えない)、`TMPDIR` も `/tmp` も安全な置き場でない (例: sticky でない 0777 の `/tmp`) と、ファイル名が `/proc` の綴りに収まらない時、bind は fork で届くが connect は `ENAMETOOLONG` になる (hyoui の実測)
- 安全でない置き場に名前で辿る symlink を置くと、他人がそれを差し替えられる

## Decision

`/proc` を使える Linux / Android では、symlink の経路で安全でない置き場の候補を飛ばさず、fd で掴む形で使う。

| 置き場の候補 | 形 |
|---|---|
| 安全 | 置き場に直接 symlink (今まで通り) |
| 安全でない (`/proc` を使える Linux / Android) | fd で掴む形 |
| 安全でない (それ以外) | 何も作らず次の候補へ |

- 試す順: `TMPDIR` が安全なら symlink → 安全でなければ fd で掴む形 → `/tmp` が安全なら symlink → 安全でなければ fd で掴む形 → スレッド cwd → fork (bind と `connect_any` 系だけ)。`TMPDIR` が `/tmp` と同じなら 1 回だけ
- fd で掴む形: 何かを作る前に `/proc` を使えるか確かめる → 0700 のディレクトリ (`sockat.` + 乱数 10 文字) を作る → `O_PATH | O_DIRECTORY | O_NOFOLLOW` で開き `fstat` で「ディレクトリ・持ち主が実効 uid・group と other に権限が無い」を確かめ、`chmod("/proc/self/fd/<fd>", 0700)` する (umask が持ち主のビットを削る環境でも開けて残骸が溜まらないため。統括の裁定 2026-11-18、sockat-go と sockat-rs の指摘) → fd の中に `symlinkat` でソケットのファイルを指す `s` を作る → `/proc/self/fd/<fd>/s` を渡す
- connect 系だけが使う。bind の綴り (`/proc/self/fd/<fd>/s/<ファイル名>`) は /proc の経路より長く、収まるなら /proc の経路が先に通るので、bind には効かない (統括の裁定 2026-11-18、worker の指摘)
- 片付け: `unlinkat(fd, "s")`。ディレクトリは名前の `(st_dev, st_ino)` が fd と一致する時だけ `rmdir`。fd を閉じる
- 使えないとみなして次の候補へ: `/proc` を使えない、ディレクトリを作れない、`fstat` の確認が通らない、`symlinkat` が失敗した

理由:

- 名前でなく fd で辿るので、sticky でない置き場で他人がディレクトリを rename して差し替えても影響を受けない
- 作ってから開くまでのすり替えは `fstat` の確認で弾く
- connect の綴りはファイル名の長さによらず収まる
- 渡された `TMPDIR` で済むならそれが一番良いので、`TMPDIR` を `/tmp` より先に使い切る

悪い面:

- `/proc` が要る。`/proc` の無い Linux と他の Unix では使えない
- 途中でプロセスが死ぬとディレクトリが残る (名前の `sockat.` で残骸と分かる)
- Apple の OS はスレッド cwd の経路で届くので足さない

## Alternatives Considered

- 案 A: 何もしない
  - 不採用理由: bind は届くのに connect は届かないソケットができる
- 案 B: 安全でない置き場に名前で辿るディレクトリや symlink を置く
  - 不採用理由: sticky でない置き場ですり替えられる

## Consequences

- 試験: 安全でない置き場で、ソケットが元のパスにでき届く、終わった後に置き場に何も残らない、作ってから開くまでに差し替えたディレクトリ (持ち主か mode が違う) を使わない、`TMPDIR` を `/tmp` より先に使う、`/proc` を使えない時は安全でない置き場を飛ばす

## 関連

- [docs/SPEC-ja.md](../SPEC-ja.md) の「symlink の置き場と名前」「fd で掴む形 (安全でない置き場)」「どこから届かなくなるか」
- 裁定: kawaz (2026-11-18)。発端は hyoui の実測
- [DR-0005](DR-0005-thread-cwd-route.md)
- [DR-0011](DR-0011-bind-spelling-with-random-part.md) (bind の /proc の経路が同じ作りのディレクトリを使う)
