---
title: パスを短い綴りに解決する resolve と、消さない置き場 B で経路を組み直す
status: open
category: design
created: 2026-11-20
origin: kawaz との議論
---

# resolve と消さない置き場 B で経路を組み直す

kawaz との議論 (2026-11-19〜20) で方向が出たものの記録。[DR-0012](../decisions/DR-0012-own-directory-and-thread-cwd.md) の芯 (綴りはすぐ片付け、片付けた後は R がどこにも無い) を覆すので、決まったら DR にする。SOCK_DGRAM / SOCK_SEQPACKET ([2026-11-18-datagram-and-seqpacket](2026-11-18-datagram-and-seqpacket.md)) もこの上に作る。

## 目的

- 長いパスを、元のパスと同じ所を指し続ける短い綴りに言い換える。綴りが生きている間は、`getsockname` の綴りで消す上のライブラリ、DGRAM の返信、運用の道具が元のパスと同じに働く
- 綴りはただのパスなので、ソケットの型 (stream / DGRAM / SEQPACKET) と操作 (bind / connect / `send_to`) を問わず、利用者が std に渡して使える
- 普段はスレッドも fork も使わない

## 方向 (kawaz と合意)

- `resolve(path)` が短い綴りを返す。短いパス (標準に渡す長さ以下の絶対パス) はそのまま返す
- 置き場 B は実在のディレクトリで、消さない (片付けは `cleanup`)。B の中に D (乱数の名前、0711)、D の中に `d` (ソケットのディレクトリを指す symlink) か `s` (ソケットのファイルを指す symlink) を作り、綴りは `B/D/d/<ファイル名>` か `B/D/s`
- B の実体の置き場: `$XDG_RUNTIME_DIR` → `$TMPDIR` → `/tmp`
- B の綴りの順 (sockat が自分で判断する):
  1. procB `/proc/<pid>/fd/<B の fd>/...`: `/proc` を使えて綴りが収まる時
  2. dirB: `$XDG_RUNTIME_DIR` と `$TMPDIR` のうち短い方の実パスの綴り。収まる時
  3. tmpB: `/tmp` の実パスの綴り。収まる時
  4. どれも収まらなければ今の経路 (thread-cwd・fork 等)
- 利用者が「別の uid にも辿らせる」と指定した時は 1・2 を飛ばして 3 から (別の uid が辿れるのは `/tmp` の下の 0711 の B だけ)
- 相手の `/tmp` が隔離されている場合 (systemd の `PrivateTmp` 等) は選択肢にせず説明に書く (procB を先に試すので Linux ではまず起きない)
- D は乱数 (カウンタにしない。プロセスが終わった後に同じ PID・同じ fd 番号の別の sockat のプロセスが現れると、カウンタの D は同じ綴りで他人のソケットを指す)
- 消す (`remove`) と片付ける (`cleanup`) は自動で行わない。どちらも 1 回だけ働き、2 回目以降は何もしない (`remove` は resolve した綴りの物を 1 回だけ消す、の意味の冪等)。connect は内部で resolve した後に自分で `cleanup` してよい
- 今の `bind` / `connect` は、resolve で済まない場面 (thread-cwd・fork が要る長さ、`getsockname` の綴りで消す上のライブラリへの備え) のために残し、内部で resolve を使う
- DGRAM の API は std の `UnixDatagram` の形に合わせ、パスを取る関数と、それと組で使う `unbound` だけを写す (`sockat::datagram::bind(path)`、`unbound()`、`connect(&sock, path)`、`send_to(&sock, buf, path)`)。`pair` は写さない

## 実測 (2026-11-19〜20、docker の Linux と macOS)

| 確かめたこと | 結果 |
|---|---|
| 開いて fd を持ったディレクトリを rmdir し、`/proc/<pid>/fd/<fd>/D` を mkdir | `ENOENT` (消したディレクトリの中には作れない) |
| 中に `d` のあるディレクトリを rmdir / unlink | `ENOTEMPTY` / `EISDIR`。rename はでき、rename 後も B に作れる |
| `/proc/<pid>/fd/<fd>/D/d/s.sock` (`d` → ソケットのディレクトリ) に bind | 通る。`getsockname` はその綴り、実体は元のパス |
| その綴りに別のプロセスが connect | 同じ uid: 届く。別の uid: `EACCES` |
| その綴りで unlink | 元のパスの実体が消える |
| macOS の `$TMPDIR` (`/var/folders/.../T/`) の権限 | `drwx------` (別の uid は辿れない) |
| bind が最後の要素の symlink を辿るか (`B/D/s` で bind できるか) | 辿るのは macOS と NetBSD だけ (Linux・FreeBSD・OpenBSD・illumos は辿らない。[findings](../findings/2026-11-19-bind-through-file-symlink.md)) |

## 綴りごとの性質

| 綴り | 綴りで消せるか | 片付け |
|---|---|---|
| `B/D/d/<ファイル名>` | 消せる (途中の `d` を辿る) | `cleanup` |
| `B/D/s` | 消せない (最後の symlink は辿られず `s` が消える)。`remove` が要る | `cleanup` |

| B の綴り | 他のプロセスが辿れるか | プロセスが終わった後 |
|---|---|---|
| procB | 同じ uid・同じ PID 名前空間だけ (root は辿れる) | 辿れない |
| dirB | 同じ uid だけ (置き場が 0700) | `cleanup` まで残る |
| tmpB | 別の uid も (B が 0711、D は乱数) | `cleanup` まで残る。`cleanup` の後は他人が同じ名前で作り直しうる |

## 未決

- 既定の `bind` / `connect` の中でも resolve の綴りを使うか (使うと綴りの寿命と `cleanup` が既定の操作に漏れ出す)
- resolve の綴りの失うもの: 生きている間は `respelled` でない。「プロセスの寿命と `cleanup` まで有効」を表す名前が要るか
- 返り値の形と名前 (`{path, remove, cleanup, 標準にそのまま渡したか}`、仮の `direct`)。B 自体を片付ける口 (仮の `cleanup_base`)
- 届く長さ: procB の綴りは `/proc/<pid>/fd/<fd>/` + D + `/d/` でおよそ 35 バイト食い、Linux で届くファイル名はおよそ 70。今の thread-cwd (96) の間は今の経路に回す
- 片付け損ねた B の掃除 (B の名前に PID を入れ、次の sockat が持ち主のいない B を消すか。PID の使い回しで生きている他人の B を消さない確かめ方)
- 「別の uid にも辿らせる」の指定の形
- `send_to` は resolve の綴りに送るので relative の経路 (送った後に取り消せない) を使わない。resolve で済まない長さの `send_to` をどうするか (thread-cwd で送る、`ENAMETOOLONG` にする)
- 長いパスに bind した DGRAM の送り手への返信は、綴りが生きている間は届く (procB は同じ uid、tmpB は別の uid も)。届かない場面 (`cleanup` の後、procB で別の uid) を失うものの名前で表すか
