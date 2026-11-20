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
- 利用者が「別の uid にも辿らせる」と指定した時は、1 を飛ばし、2・3 のうち B までの途中のディレクトリが全部 other に x (辿る権限) を持つ物だけを使う (子が 0711 でも親が 0700 なら別の uid は辿れない。実測)。`/tmp` (1777) の下の tmpB はいつも当たり、dirB は置き場が 0700 (`/run/user/<uid>`、macOS の `$TMPDIR`) なら外れ、`$TMPDIR` を辿れる場所に向けた環境なら当たる
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
| 0700 の親の中の 0711 のディレクトリに別の uid が cd | できない。親も 0711 にするとできる |
| bind が最後の要素の symlink を辿るか (`B/D/s` で bind できるか) | 辿るのは macOS と NetBSD だけ (Linux・FreeBSD・OpenBSD・illumos は辿らない。[findings](../findings/2026-11-19-bind-through-file-symlink.md)) |

## 綴りごとの性質

| 綴り | 綴りで消せるか | 片付け |
|---|---|---|
| `B/D/d/<ファイル名>` | 消せる (途中の `d` を辿る) | `cleanup` |
| `B/D/s` | 消せない (最後の symlink は辿られず `s` が消える)。`remove` が要る | `cleanup` |

| B の綴り | 他のプロセスが辿れるか | プロセスが終わった後 |
|---|---|---|
| procB | 同じ uid・同じ PID 名前空間だけ (root は辿れる) | 辿れない |
| dirB | 置き場までの途中が全部 other に x を持てば別の uid も、そうでなければ同じ uid だけ (`/run/user/<uid>` と macOS の `$TMPDIR` は 0700) | `cleanup` まで残る |
| tmpB | 別の uid も (B が 0711、D は乱数) | `cleanup` まで残る。`cleanup` の後は他人が同じ名前で作り直しうる |

## 整理案 (統括、2026-11-20。kawaz の判断待ち)

既定の `bind` も、収まれば resolve の綴りを使う (kawaz)。thread-cwd・fork は収まらない時の後ろ。今の route・losses の名前とのつながりは気にしない (kawaz)。

### 経路 (route、診断用)

bind (6 つ):

| 順 | route | 綴り | 使う時 |
|---|---|---|---|
| 1 | `standard` | 元のパス | 標準に渡す長さ以下 |
| 2 | `link-dir` | `B/D/d/<ファイル名>` (`d` → ソケットのディレクトリ) | 収まる時 |
| 3 | `link-file` | `B/D/s` (`s` → ソケットのファイル) | bind が symlink を辿る OS (macOS・NetBSD) で、`link-dir` が収まらない時 |
| 4 | `thread-cwd` | `R/<ファイル名>` (R は片付け済み) | Linux・Apple の OS |
| 4 | `at` | 同 | FreeBSD |
| 5 | `fork-cwd` | 同 | fork のある言語 |

- B は持ち主だけの置き場 (procB → dirB) を先に、共有の置き場 (tmpB) を後に試し、同じ B の中では `link-dir` → `link-file` の順
- B を `$XDG_RUNTIME_DIR`・`$TMPDIR`・`/tmp` のどこにも作れない時は、ソケットのディレクトリに `.sockat.XXXXXXXXXX` で作る (`-sockdir` の経路は無くなる)
- どの B を使ったかは診断用の `base` (`proc`・`runtime`・`tmpdir`・`tmp`・`sockdir`) で返す

connect (8 つ):

| 順 | route | 中身 |
|---|---|---|
| 1 | `standard` | 元のパス |
| 2 | `proc-direct` / `relative` / `widened` / `at-direct` | 書き込みもスレッドも要らない (OS ごとに今と同じ) |
| 3 | `thread-cwd-direct` | 使い捨てのスレッドがソケットのディレクトリへ `fchdir` してファイル名で connect (D も R も要らない。connect の綴りは相手に残らないため) |
| 4 | `link-file` | `B/D/s`。ファイル名の長さによらず届く。connect の後に片付ける |
| 5 | `fork-cwd-direct` | fork のある言語だけ (案 L を採らなければ) |

- connect は D・R を通す `thread-cwd`・`at`・`proc`・`proc-held`・`symlink-file` が要らなくなる
- FreeBSD の connect で `link-file` を使えるか (今の SPEC は symlink-file を FreeBSD で使わない) は未確認

### 失うもの (bind だけ。connect の綴りは相手に残らない)

名前の並びをやめ、綴りの性質を 1 つの値で返す案 (S1) と、名前の並びの案 (S2)。推しは S1。利用者が知りたいのは「この綴りを後で使えるか」の 1 点で、性質は互いに排他な種類 + 種類ごとの属性になるため。

S1:

```rust
#[non_exhaustive]
pub enum Spelling {
    Original,     // 元の絶対パス
    CwdRelative,  // 元の相対パス (cwd を変えると別の所を指す)
    Linked {
        removable: bool,             // 綴りで unlink すると実体が消えるか (link-dir: true、link-file: false)
        until: Until,                // Process (procB) / Cleanup (dirB・tmpB)
        followable_by_other_uids: bool,    // 別の uid の相手が辿れるか
        followable_from_private_tmp: bool, // /tmp を隔離した相手 (systemd の PrivateTmp 等) が辿れるか (綴りが /tmp・/var/tmp を通らなければ true。mount 名前空間が丸ごと違う相手 (コンテナ等) までは保証しない)
        recreatable_after_cleanup: bool, // cleanup の後に他人が作り直せるか (tmpB)
    },
    Dangling,     // 片付け済みの R を含む綴り。どこにも届かない (thread-cwd・at・fork-cwd)
}
```

S2: `forked`・`cwd-relative`・`dangling`・`unremovable-by-spelling`・`temporary`・`owner-only`・`recreatable-after-cleanup` の名前の並び。種類と属性が混ざり、組み合わせの意味を利用者が考えることになる。

fork したかは別の `forked: bool` にする。

### 最終手段

- bind: 無くなる (共有の置き場の綴りは tmpB として既定の順に入り、生きている間は 0711 の自分の B で作り直されない)
- connect: `fork-cwd-direct` だけ。thread-cwd-direct と link-file の後に来るので、出番はスレッドも B も使えない環境だけ
- 案 L: 最終手段を無くし、`fork-cwd-direct` を作らない (Python・Go はもともと無い)。引数から最終手段が消える

### 引数

- `_ex` の引数を `Options` にする: `followable_by_other_uids: bool` (別の uid にも辿らせる。B の選び方にだけ効き、満たせたかは結果の `Spelling` で分かる)、案 L を採らなければ `last_resort: bool` (connect だけ)
- 既定の操作は今のとおり path だけ

### 関数

推しは F1。

| 案 | 形 |
|---|---|
| F1 | 型ごとのモジュールに std の形で置く (stream は crate 直下、`datagram::`、`seqpacket::`)。操作ごとに `_ex(…, Options)`。resolve は用途ごとに 2 つ |
| F2 | 型を引数で渡す (`bind(path, Type)`)。std の形から外れる |
| F3 | builder (`Options::new().followable_by_other_uids(true).bind(path)`)。`_ex` の数は減るが、型ごとの操作が builder に集まる |

F1 の一覧 (Rust):

```rust
// stream
sockat::bind(path) -> io::Result<UnixListener>
sockat::connect(path) -> io::Result<UnixStream>
sockat::connect_nonblocking(path) -> io::Result<UnixStream>
sockat::bind_ex(path, Options) -> Result<Bound<UnixListener>, ExError>
sockat::connect_ex(path, Options) -> Result<Connected<UnixStream>, ExError>
sockat::connect_nonblocking_ex(path, Options) -> Result<Connected<UnixStream>, ExError>

// datagram (std の UnixDatagram の、path を取る関数と unbound)
sockat::datagram::bind(path) -> io::Result<UnixDatagram>
sockat::datagram::unbound() -> io::Result<UnixDatagram>
sockat::datagram::connect(&UnixDatagram, path) -> io::Result<()>
sockat::datagram::send_to(&UnixDatagram, buf, path) -> io::Result<usize>
sockat::datagram::bind_ex(path, Options) -> Result<Bound<UnixDatagram>, ExError>
sockat::datagram::connect_ex(&UnixDatagram, path, Options) -> Result<Report, ExError>
sockat::datagram::send_to_ex(&UnixDatagram, buf, path, Options) -> Result<(usize, Report), ExError>

// seqpacket (返す型は未決)
sockat::seqpacket::bind(path) / connect(path) / connect_nonblocking(path) と各 _ex

// resolve (std に自分で渡す人向け)
sockat::resolve_for_bind(path, Options) -> Result<ForBind, ExError>     // path / spelling / remove() / cleanup() / 診断
sockat::resolve_for_connect(path, Options) -> Result<ForConnect, ExError> // path / cleanup() / 診断 (remove は持たない)

// 置き場 B を片付ける
sockat::cleanup_base() -> io::Result<()>
```

```rust
pub struct Bound<S> {
    pub socket: S,
    pub file: SocketFile,   // remove(): bind したファイルを 1 回だけ消し、cleanup もする / cleanup(): D を 1 回だけ片付ける
    pub spelling: Spelling,
    pub forked: bool,
    pub route: &'static str, pub base: Option<&'static str>, pub skipped: Vec<Skipped>, // 診断用
}
pub struct Connected<S> { pub socket: S, pub forked: bool, pub route: &'static str, pub skipped: Vec<Skipped> }
pub struct Report { pub forked: bool, pub route: &'static str, pub skipped: Vec<Skipped> }
```

- resolve を用途で 2 つに分ける理由: bind は `link-file` を Linux 等で使えず `link-dir` を先に選ぶ、connect は `link-file` を選ぶ (ファイル名の長さによらない)。connect 用の resolve には `remove` を持たせず、消し間違いを型で防ぐ
- 「標準にそのまま渡したか」の bool は持たない (`spelling == Original` か `route == "standard"` で分かる)
- resolve は path を返すだけなので、thread-cwd・fork でしか届かない長さでは `ENAMETOOLONG`。それも届かせたい人は `bind` / `connect` を使う
- 既定の `bind` は `SocketFile` を返さないので、その B は `cleanup_base` か次の sockat の掃除まで残る (片付け損ねた B の掃除が必須になる)

## 未決

- 既定の `bind` / `connect` の中でも resolve の綴りを使うか (使うと綴りの寿命と `cleanup` が既定の操作に漏れ出す)
- resolve の綴りの失うもの: 生きている間は `respelled` でない。「プロセスの寿命と `cleanup` まで有効」を表す名前が要るか
- 返り値の形と名前 (`{path, remove, cleanup, 標準にそのまま渡したか}`、仮の `direct`)。B 自体を片付ける口 (仮の `cleanup_base`)
- 届く長さ: procB の綴りは `/proc/<pid>/fd/<fd>/` + D + `/d/` でおよそ 35 バイト食い、Linux で届くファイル名はおよそ 70。今の thread-cwd (96) の間は今の経路に回す
- 片付け損ねた B の掃除 (B の名前に PID を入れ、次の sockat が持ち主のいない B を消すか。PID の使い回しで生きている他人の B を消さない確かめ方)
- 「別の uid にも辿らせる」の指定の形
- `send_to` は resolve の綴りに送るので relative の経路 (送った後に取り消せない) を使わない。resolve で済まない長さの `send_to` をどうするか (thread-cwd で送る、`ENAMETOOLONG` にする)
- 長いパスに bind した DGRAM の送り手への返信は、綴りが生きている間は届く (procB は同じ uid、tmpB は別の uid も)。届かない場面 (`cleanup` の後、procB で別の uid) を失うものの名前で表すか
