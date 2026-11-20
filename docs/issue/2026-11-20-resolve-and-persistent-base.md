---
title: パスを短い綴りに解決する resolve と、消さない置き場 B で経路を組み直す
status: open
category: design
created: 2026-11-20
origin: kawaz との議論
---

# resolve と消さない置き場 B で経路を組み直す

kawaz との議論 (2026-11-19〜20) で方向が出たものの記録。[DR-0012](../decisions/DR-0012-own-directory-and-thread-cwd.md) の芯 (綴りはすぐ片付け、片付けた後は R がどこにも無い) を覆すので、決まったら DR にする。SOCK_DGRAM / SOCK_SEQPACKET ([2026-11-18-datagram-and-seqpacket](2026-11-18-datagram-and-seqpacket.md)) もこの上に作る。

## SPEC の記号との対応

この issue の記号は [SPEC](../SPEC-ja.md) の同じ字と別物がある。

| この issue | 中身 | SPEC との違い |
|---|---|---|
| B | 置き場の中に作る実在のディレクトリ。消さない | SPEC に無い |
| D | B の中に resolve ごとに作るディレクトリ | SPEC の D は bind / connect のたびに作って呼び出しの最後に消す。この issue の D は resolve ごとに作るが消さない (`cleanup` まで残る) |
| `d` | D の中の、ソケットのディレクトリを指す symlink | SPEC の R に当たるが、消さず、名前は固定 |
| `s` | D の中の、ソケットのファイルを指す symlink | SPEC の proc-held の `s` と同じ形だが、消さない |

## 目的

- 長いパスを、元のパスと同じ所を指し続ける短い綴りに言い換える。綴りが生きている間は、`getsockname` の綴りで消す上のライブラリ、DGRAM の返信、運用の道具が元のパスと同じに働く
- 綴りはただのパスなので、ソケットの型 (stream / DGRAM / SEQPACKET) と操作 (bind / connect / `send_to`) を問わず、利用者が std に渡して使える
- 普段はスレッドも fork も使わない

## 方向 (kawaz と合意)

- resolve が短い綴りを返す (整理案では用途ごとに `resolve_for_bind` / `resolve_for_connect`)。短いパス (標準に渡す長さ以下) はそのまま返す: 絶対パスは `Original`、相対パスは `CwdRelative`
- 綴りは `B/D/d/<ファイル名>` か `B/D/s`
- 既定の `bind` も、綴りが収まれば resolve の綴りを使う (kawaz)。thread-cwd・fork は収まらない時の後ろ
- 今の `bind` / `connect` は、resolve で済まない場面 (thread-cwd・fork が要る長さ、`getsockname` の綴りで消す上のライブラリへの備え) のために残し、内部で resolve を使う
- D は乱数の名前 (カウンタにしない。プロセスが終わった後に同じ PID・同じ fd 番号の別の sockat のプロセスが現れると、カウンタの D は同じ綴りで他人のソケットを指す)
- 消す (`remove`) と片付ける (`cleanup` は D、`cleanup_base` は B) は自動で行わない。どれも 1 回だけ働き、2 回目以降は何もしない (`remove` は resolve した綴りの物を 1 回だけ消す、の意味の冪等)。connect は内部で resolve した後に自分で `cleanup` してよい
- 利用者が「別の uid にも辿らせる」と指定した時は、procB を飛ばし、dirB・tmpB のうち B までの途中のディレクトリが全部 other に x (辿る権限) を持つ物だけを使う (子が 0711 でも親が 0700 なら別の uid は辿れない。実測)。`/tmp` (1777) の下の tmpB はいつも当たり、dirB は置き場が 0700 (`/run/user/<uid>`、macOS の `$TMPDIR`) なら外れ、`$TMPDIR` を辿れる場所に向けた環境なら当たる
- 相手の `/tmp` が隔離されている場合 (systemd の `PrivateTmp` 等) は選択肢にせず説明に書く (procB を先に試すので Linux ではまず起きない)
- DGRAM の API は std の `UnixDatagram` の形に合わせ、パスを取る関数と、それと組で使う `unbound` だけを写す (`sockat::datagram::bind(path)`、`unbound()`、`connect(&sock, path)`、`send_to(&sock, buf, path)`)。`pair` は写さない

### B と D

| | B | D |
|---|---|---|
| 作る単位 | プロセスごと (fd を持ち続ける) | resolve ごと |
| 置く所 | 置き場 (「実体の置き場と綴りの形」) | B の中 |
| 名前 | 未決 (PID を入れる案。「案がまだ無い」の掃除) | 乱数 |
| mode | 0711 (他人は中を一覧できず、名前を知っていれば辿れる) | 0711 (名前は乱数。中は `d` か `s`) |
| 消す口 | `cleanup_base` | `cleanup` (B ごと消す `cleanup_base` でも消える) |
| 残る間 | `cleanup_base` か、次の sockat の掃除まで | `cleanup` か `cleanup_base` か、次の sockat の掃除まで |

### 実体の置き場と綴りの形

B の実体をどこに作るかと、B をどう綴るかは別の軸。

実体の置き場 (作れた最初の所):

| 順 | 置き場 |
|---|---|
| 1 | `$XDG_RUNTIME_DIR` |
| 2 | `$TMPDIR` |
| 3 | `/tmp` |
| 4 | ソケットのディレクトリ (名前は `.sockat.XXXXXXXXXX`。1〜3 のどこにも作れない時) |

綴りの形 (sockat が自分で判断する。上から順に、収まる物):

| 綴り | 形 | 実体 | 診断の `base` | 他のプロセスが辿れるか |
|---|---|---|---|---|
| procB | `/proc/<pid>/fd/<B の fd>/D/…` | 実体の置き場の順で決まる所 | `proc` (ソケットのディレクトリに作った時は `sockdir`) | 同じ uid・同じ PID 名前空間だけ (root は辿れる)。プロセスが終われば辿れない |
| dirB | 実体の実パス `…/B/D/…` | `$XDG_RUNTIME_DIR` と `$TMPDIR` のうち実パスの短い方 | `runtime` / `tmpdir` | 置き場までの途中が全部 other に x を持てば別の uid も、そうでなければ同じ uid だけ (`/run/user/<uid>` と macOS の `$TMPDIR` は 0700) |
| tmpB | `/tmp` の実パス `…/B/D/…` | `/tmp` | `tmp` | 別の uid も (B が 0711、D は乱数) |

- procB は `/proc` を使えて綴りが収まる時だけ。実体がどこでも綴りは同じ形
- B をソケットのディレクトリに作った時は、実パスの綴りは元のパスより長くなるので、使えるのは procB の綴りだけ。`/proc` の無い OS では resolve の綴りを使えず、今の経路 (thread-cwd・fork 等) へ
- どの綴りも収まらなければ今の経路へ

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

| B の綴り | プロセスが終わった後 |
|---|---|
| procB | 辿れない |
| dirB | `cleanup` (D) か `cleanup_base` (B) まで残る |
| tmpB | `cleanup` (D) か `cleanup_base` (B) まで残る。`cleanup_base` で B を消した後は、他人が同じ名前で作り直しうる (std の元のパスを消した後に、そのディレクトリに書ける人が作り直せるのと同じ。片付けた後の綴りは使わない、と説明に書く) |

## 整理案 (統括、2026-11-20。kawaz の判断待ち)

今の route・losses の名前とのつながりは気にしない (kawaz)。

### 経路 (route、診断用)

bind の試す順 (B の綴りごとに展開した 1 列):

| 順 | route | B の綴り | 綴り | 使う時 |
|---|---|---|---|---|
| 1 | `standard` | | 元のパス | 標準に渡す長さ以下 |
| 2 | `link-dir` | procB | `B/D/d/<ファイル名>` (`d` → ソケットのディレクトリ) | `/proc` を使えて収まる |
| 3 | `link-dir` | dirB | 同 | 収まる |
| 4 | `link-file` | dirB | `B/D/s` (`s` → ソケットのファイル) | bind が symlink を辿る OS (macOS・NetBSD) |
| 5 | `link-dir` | tmpB | `B/D/d/<ファイル名>` | 収まる |
| 6 | `link-file` | tmpB | `B/D/s` | bind が symlink を辿る OS (macOS・NetBSD) |
| 7 | `thread-cwd` (FreeBSD は `at`) | | `R/<ファイル名>` (R は片付け済み) | Linux・Apple の OS (`at` は FreeBSD) |
| 8 | `fork-cwd` | | 同 | fork の経路を作れる言語 |

- procB の `link-file` は無い (`/proc` のある Linux は bind が symlink を辿らない)
- B を `$XDG_RUNTIME_DIR`・`$TMPDIR`・`/tmp` のどこにも作れない時は、ソケットのディレクトリに作り、procB の綴りだけを使う (「実体の置き場と綴りの形」)。`-sockdir` の経路は無くなる
- どの B を使ったかは診断用の `base` で返す (「実体の置き場と綴りの形」の表)

connect:

| 順 | route | 中身 |
|---|---|---|
| 1 | `standard` | 元のパス |
| 2 | `proc-direct` / `relative` / `widened` / `at-direct` | 書き込みもスレッドも要らない (OS ごとに今と同じ) |
| 3 | `thread-cwd-direct` | 使い捨てのスレッドがソケットのディレクトリへ `fchdir` してファイル名で connect (D も R も要らない。connect の綴りは相手に残らないため) |
| 4 | `link-file` | `B/D/s`。ファイル名の長さによらず届く。connect の後に片付ける |
| 5 | `fork-cwd-direct` | fork の経路を作れる言語だけ (案 L を採らなければ) |

- connect は、D と R を通す `thread-cwd`・`at`・`proc`、D を通す `proc-held`、置き場に symlink を作る `symlink-file` が要らなくなる (`thread-cwd-direct` と `link-file` が代わる)
- FreeBSD の connect で `link-file` を使えるか (今の SPEC は symlink-file を FreeBSD で使わない) は未確認

### 綴りの性質 (RS-Q1)

bind の綴りの性質を返す。connect の綴りは相手に残らないので返さない。fork したかは綴りの性質と別の `forked: bool` で返す (connect にも付く)。

綴りの性質を 1 つの値で返す (S1、kawaz 裁定 2026-11-20)。利用者が知りたいのは「この綴りを後で使えるか」の 1 点で、性質は互いに排他な種類 + 種類ごとの属性になるため。

S1:

```rust
#[non_exhaustive]
pub enum Spelling {
    Original,     // 元の絶対パス
    CwdRelative,  // 元の相対パス (cwd を変えると別の所を指す)
    Linked {
        removable: bool,             // 綴りで unlink すると実体が消えるか (link-dir: true、link-file: false)
        until: Until,                // Process (procB) / Cleanup (dirB・tmpB)
        usable_cross_uid: bool,        // 別の uid の相手が辿れるか
        usable_with_private_tmp: bool, // 自分と相手のどちらかが /tmp を隔離していても (systemd の PrivateTmp 等) 相手が辿れるか (綴りが /tmp・/var/tmp を通らなければ true。mount 名前空間が丸ごと違う相手 (コンテナ等) までは保証しない)
    },
    Dangling,     // 片付け済みの R を含む綴り。どこにも届かない (thread-cwd・at・fork-cwd)
}
```

採らなかった S2: `forked`・`cwd-relative`・`dangling`・`unremovable-by-spelling`・`temporary`・`owner-only` の名前の並び。種類と属性が混ざり、組み合わせの意味を利用者が考えることになる。

### 最終手段 (RS-Q2)

- bind: 無くなる (共有の置き場の綴りは tmpB として既定の順に入り、生きている間は 0711 の自分の B で作り直されない)
- connect: `fork-cwd-direct` だけ。thread-cwd-direct と link-file の後に来るので、出番はスレッドも B も使えない環境だけ
- 案 L: 最終手段を無くし、`fork-cwd-direct` を作らない (Python・Go はもともと無い)。引数から最終手段が消える

### 引数

- `_ex` の引数を `Options` にする: `usable_cross_uid: bool` (別の uid の相手も辿れる綴りを求める。B の選び方にだけ効き、満たせたかは結果の `Spelling` で分かる)、案 L を採らなければ `last_resort: bool` (connect だけ)
- 既定の操作は今のとおり path だけ

### 関数 (RS-Q3)

推しは F1。

| 案 | 形 |
|---|---|
| F1 | 型ごとのモジュールに std の形で置く (stream は crate 直下、`datagram::`、`seqpacket::`)。操作ごとに `_ex(…, Options)`。resolve は用途ごとに 2 つ |
| F2 | 型を引数で渡す (`bind(path, Type)`)。std の形から外れる |
| F3 | builder (`Options::new().usable_cross_uid(true).bind(path)`)。`_ex` の数は減るが、型ごとの操作が builder に集まる |

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
- 既定の `bind` は `SocketFile` を返さないので、その D は `cleanup_base` か次の sockat の掃除まで残る (片付け損ねた B・D の掃除が必須になる)

## 未決

### 整理案で案を出した (判断待ち。[docs/QUESTIONS.md](../QUESTIONS.md))

- RS-Q2: 最終手段を残すか、無くす (案 L) か (「最終手段」)
- RS-Q3: 関数の形 F1〜F3 (「関数」)。返り値の形と名前、B を片付ける口 `cleanup_base` もこの中。「別の uid にも辿らせる」の指定の形は整理案の「引数」(`Options.usable_cross_uid`)

### 案がまだ無い

- 綴りの寿命と片付けが既定の操作に漏れ出すこと (既定の `bind` が resolve の綴りを使うので、片付け損ねた B・D の掃除が必須になる)
- 片付け損ねた B・D の掃除 (B の名前に PID を入れ、次の sockat が持ち主のいない B を消すか。PID の使い回しで生きている他人の B を消さない確かめ方)
- 届く長さ: procB の綴りは `/proc/<pid>/fd/<fd>/` + D + `/d/` でおよそ 35 バイト食い、Linux で届くファイル名はおよそ 70。今の thread-cwd (96) の間は今の経路に回す
- `send_to` は resolve の綴りに送るので relative の経路 (送った後に取り消せない) を使わない。resolve で済まない長さの `send_to` をどうするか (thread-cwd で送る、`ENAMETOOLONG` にする)
- 長いパスに bind した DGRAM の送り手への返信は、綴りが生きている間は届く (procB は同じ uid、tmpB は別の uid も)。届かない場面 (`cleanup` の後、procB で別の uid) を綴りの性質 (S1) でどう表すか
