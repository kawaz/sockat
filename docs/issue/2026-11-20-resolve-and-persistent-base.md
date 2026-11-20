---
title: パスを短い綴りに解決する resolve と、消さない置き場 B で経路を組み直す
status: open
category: design
created: 2026-11-20
origin: kawaz との議論
---

# resolve と消さない置き場 B で経路を組み直す

kawaz との議論 (2026-11-19〜20) で方向が出たものの記録。[DR-0012](../decisions/DR-0012-own-directory-and-thread-cwd.md) の芯 (綴りはすぐ片付け、片付けた後は R がどこにも無い) を覆すので、決まったら DR にする。SOCK_DGRAM / SOCK_SEQPACKET ([2026-11-18-datagram-and-seqpacket](2026-11-18-datagram-and-seqpacket.md)) もこの上に作る。

## 操作ごとに重視すること (kawaz 2026-11-20)

| 操作 | 使われ方の見込み | 重視すること |
|---|---|---|
| bind | 息が長く、大量には作らない | 速さ以外 (綴りの寿命、残るもの、安全) |
| connect | CLI や制御の問い合わせで、必要な時に都度行う | 手数・速さ・IO の回数・負荷。同じパスへの綴り (B / D / `s`) を作り直さず再利用できること |

- connect の再利用は、`resolve_for_connect` で 1 度作った綴りを何度も connect に使い、最後に `cleanup` する形で足りるかを先に見る (既定の `connect` に隠れた状態を持たせない)
- 経路ごとの費用 (syscall の数、時間、置き場への書き込み) をベンチマークで測り、届く範囲の表と経路の説明に数字で載せる

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
- fork はしない (kawaz 裁定 2026-11-20。fork の手法の説明と、それで届く場面は [pages/fork-cwd-ja.md](../../pages/fork-cwd-ja.md))。普段はスレッドも使わない

## 方向 (kawaz と合意)

- resolve が短い綴りを返す (整理案では用途ごとに `resolve_for_bind` / `resolve_for_connect`)。短いパス (標準に渡す長さ以下) はそのまま返す: 絶対パスは `Original`、相対パスは `CwdRelative`
- 綴りは `B/D/d/<ファイル名>` か `B/D/s`
- 既定の `bind` も、綴りが収まれば resolve の綴りを使う (kawaz)。thread-cwd は収まらない時の後ろ
- 今の `bind` / `connect` は、resolve で済まない場面 (thread-cwd が要る長さ、`getsockname` の綴りで消す上のライブラリへの備え) のために残し、内部で resolve を使う
- D は乱数の名前 (カウンタにしない。プロセスが終わった後に同じ PID・同じ fd 番号の別の sockat のプロセスが現れると、カウンタの D は同じ綴りで他人のソケットを指す)
- 消す (`remove`) と片付ける (`cleanup` は E。B と D は sockat が片付けない) は自動で行わない。どれも 1 回だけ働き、2 回目以降は何もしない (`remove` は resolve した綴りの物を 1 回だけ消す、の意味の冪等)。connect は内部で resolve した後に自分で `cleanup` してよい
- 利用者が「別の uid にも辿らせる」と指定した時は、procB を飛ばし、dirB・tmpB のうち B までの途中のディレクトリが全部 other に x (辿る権限) を持つ物だけを使う (子が 0711 でも親が 0700 なら別の uid は辿れない。実測)。`/tmp` (1777) の下の tmpB はいつも当たり、dirB は置き場が 0700 (`/run/user/<uid>`、macOS の `$TMPDIR`) なら外れ、`$TMPDIR` を辿れる場所に向けた環境なら当たる
- 相手の `/tmp` が隔離されている場合 (systemd の `PrivateTmp` 等) は選択肢にせず説明に書く (procB を先に試すので Linux ではまず起きない)
- DGRAM の API は std の `UnixDatagram` の形に合わせ、パスを取る関数と、それと組で使う `unbound` だけを写す (`sockat::datagram::bind(path)`、`unbound()`、`connect(&sock, path)`、`send_to(&sock, buf, path)`)。`pair` は写さない

### B と D (kawaz と合意 2026-11-20。掃除は OS の一時ディレクトリの掃除に任せる)

| | B | D | E |
|---|---|---|---|
| 作る単位 | 利用者ごと。プロセスをまたいで使い回す | プロセスごと (1 つ) | resolve ごと |
| 置く所 | 置き場 (下の順) か、利用者が `Options.base` で指定した所 | B の中 | D の中 |
| 名前 | `sockat-<uid>` (`$XDG_RUNTIME_DIR` の下は `sockat`)。使う前に、実ディレクトリ・持ち主が自分・他人が書けない、を確かめ、外れたら乱数の名前 (指定された所なら外れたらエラー) | 乱数 (プロセスが終わった後に同じ PID・同じ fd 番号の別のプロセスが現れても綴りが同じにならないため) | プロセスの中で一意なら短くてよい (D がプロセスごとに一意) |
| 中身 | D | E | ソケットのディレクトリを指す symlink (link-dir、綴り `B/D/E/<ファイル名>`) か、ソケットのファイルを指す symlink (link-file、綴り `B/D/E`) |
| 生きている間 | 消さない | プロセスが flock (共有ロック) を掛けた fd を持ち続ける。systemd-tmpfiles (v242 以上) はロックの掛かったディレクトリを配下ごと掃除しない | 消さない |
| 片付け | sockat はしない (利用者が指定した B はアプリが管理) | sockat はしない。死んだプロセスの D は OS の一時ディレクトリの掃除で消える (Linux の `/tmp` は 10 日。macOS の `/tmp` は symlink の入ったディレクトリを消さないので再起動まで残る)。明示の `sweep()` を呼んだ時だけ、ロックの外れた D を消す | `cleanup` |

- resolve のたびに B の中を一覧しない (resolve の手数を増やさない)
- 他の節の `d`・`s` (と綴り `B/D/d/<ファイル名>`・`B/D/s`) は E のこと (`B/D/E/<ファイル名>`・`B/D/E`)
- 既定の bind と connect の違い: bind の綴りはカーネルがソケットの寿命の間覚えるので、綴りが辿れ続けることが正しく動く条件 (`getsockname` の綴りで消す、DGRAM の返信)。connect の綴りは相手に残らず、残すのは速さのためのキャッシュでしかない。だから bind は既定でも残し、connect は既定では残さず、再利用したい人が resolve を選ぶ
- 調査は [research](../research/2026-11-20-tmp-cleaners-and-persistent-base.md)。systemd v242 より古い環境 (RHEL 8 の v239 等) では生きている D も 10 日で消されうる (綴りが辿れなくなるだけで危険はない。説明に書く)

### 実体の置き場と綴りの形

B の実体をどこに作るかと、B をどう綴るかは別の軸。

実体の置き場 (利用者が指定しなければ、作れた最初の所。OS の掃除で死んだ D が消え、生きている D が守られる所を先に):

| 順 | 置き場 | 理由 |
|---|---|---|
| 1 | `/tmp` | Linux は死んだ D を 10 日で消し、生きている D は flock で守られる。macOS は生きている D を消さない |
| 2 | `$XDG_RUNTIME_DIR` | age の掃除が無く、死んだ D はログアウトまで残る |
| 3 | `$TMPDIR` | macOS の `$TMPDIR` は dirhelper が 3 日で消しうる (生きている D も) |
| 4 | ソケットのディレクトリ (名前は `.sockat.XXXXXXXXXX`。1〜3 のどこにも作れない時) | |

綴りの形 (sockat が自分で判断する。上から順に、収まる物):

| 綴り | 形 | 実体 | 診断の `base` | 他のプロセスが辿れるか |
|---|---|---|---|---|
| procB | `/proc/<pid>/fd/<B の fd>/D/…` | 実体の置き場の順で決まる所 | `proc` (ソケットのディレクトリに作った時は `sockdir`) | 同じ uid・同じ PID 名前空間だけ (root は辿れる)。プロセスが終われば辿れない |
| dirB | 実体の実パス `…/B/D/…` | `$XDG_RUNTIME_DIR` と `$TMPDIR` のうち実パスの短い方 | `runtime` / `tmpdir` | 置き場までの途中が全部 other に x を持てば別の uid も、そうでなければ同じ uid だけ (`/run/user/<uid>` と macOS の `$TMPDIR` は 0700) |
| tmpB | `/tmp` の実パス `…/B/D/…` | `/tmp` | `tmp` | 別の uid も (B が 0711、D は乱数) |

- procB は `/proc` を使えて綴りが収まる時だけ。実体がどこでも綴りは同じ形
- B をソケットのディレクトリに作った時は、実パスの綴りは元のパスより長くなるので、使えるのは procB の綴りだけ。`/proc` の無い OS では resolve の綴りを使えず、thread-cwd / at へ
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
| dirB | E は `cleanup` まで、D はプロセスが終わった後の OS の掃除まで残る |
| tmpB | 同上。B が消えた後は、他人が同じ名前で作り直しうる (std の元のパスを消した後に、そのディレクトリに書ける人が作り直せるのと同じ。片付けた後の綴りは使わない、と説明に書く) |

## 整理案 (統括、2026-11-20。RS-Q1〜Q4 は kawaz 裁定済み)

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

- connect は、D と R を通す `thread-cwd`・`at`・`proc`、D を通す `proc-held`、置き場に symlink を作る `symlink-file` が要らなくなる (`thread-cwd-direct` と `link-file` が代わる)
- FreeBSD の connect で `link-file` を使えるか (今の SPEC は symlink-file を FreeBSD で使わない) は未確認

### 綴りの性質 (RS-Q1)

bind の綴りの性質を返す。connect の綴りは相手に残らないので返さない。fork しないので `forked` は無い。

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
    Dangling,     // 片付け済みの R を含む綴り。どこにも届かない (thread-cwd・at)
}
```

採らなかった S2: `forked`・`cwd-relative`・`dangling`・`unremovable-by-spelling`・`temporary`・`owner-only` の名前の並び。種類と属性が混ざり、組み合わせの意味を利用者が考えることになる。

### 最終手段と fork (RS-Q2、kawaz 裁定 2026-11-20)

- fork の実装を全部なくす (`fork-cwd`・`fork-cwd-sockdir`・`fork-cwd-direct`)。fork の副作用 (fd の複製、`SIGCHLD`、`waitpid(-1)`、`pthread_atfork`、connect では相手に見える pid) はプロセス全体に及び、してほしくない利用者の方が多い
- 最終手段も無くなる: bind の symlink-dir は tmpB として既定の順に入り、connect の fork-cwd-direct は作らない。引数から最終手段が消え、`forked` も無くなる
- 3 言語で届く所がそろう (Python・Go はもともと fork の経路を作らない)
- fork をやめて届かなくなる場面と、fork の手法の説明は [pages/fork-cwd-ja.md](../../pages/fork-cwd-ja.md)。sockat で届かない場面の全体は [届く範囲の表](../../pages/reach/README-ja.md) (選んで絞り込むページは [pages/reach/index.html](../../pages/reach/index.html?lang=ja))

### 引数

- `_ex` の引数を `Options` にする: `usable_cross_uid: bool` (別の uid の相手も辿れる綴りを求める。B の選び方にだけ効き、満たせたかは結果の `Spelling` で分かる)
- `base: Option<Path>`: 利用者が B の実体の場所を指定する (アプリが自分の管理する場所を渡す。例 `/tmp/app-<uid>/sockat`)。sockat は中にプロセスごとの D を作るだけで、B の掃除はアプリに任せる。実ディレクトリ・持ち主が自分・他人が書けない、を確かめ、外れたらエラー (自動の置き場に落とさない)。綴りの形は自動の時と同じ順で選ぶ
- 既定の操作は今のとおり path だけ (プロセス全体の既定を変える関数は、隠れた状態になるので作らない)

### 関数 (RS-Q3、kawaz 裁定 2026-11-20: F1)

F1 にする。resolve を用途で 2 つに分けるのも採る (戻り値に `remove()` があるかが用途で変わるので、型で区別して消し間違いを防ぐ)。

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
sockat::sweep() -> io::Result<()>   // 呼んだ時だけ、持ち主の死んだ D (ロックの外れた D) を消す
```

```rust
pub struct Bound<S> {
    pub socket: S,
    pub file: SocketFile,   // remove(): bind したファイルを 1 回だけ消し、cleanup もする / cleanup(): D を 1 回だけ片付ける
    pub spelling: Spelling,
    pub route: &'static str, pub base: Option<&'static str>, pub skipped: Vec<Skipped>, // 診断用
}
pub struct Connected<S> { pub socket: S, pub route: &'static str, pub skipped: Vec<Skipped> }
pub struct Report { pub route: &'static str, pub skipped: Vec<Skipped> }
```

- resolve を用途で 2 つに分ける理由: bind は `link-file` を Linux 等で使えず `link-dir` を先に選ぶ、connect は `link-file` を選ぶ (ファイル名の長さによらない)。connect 用の resolve には `remove` を持たせず、消し間違いを型で防ぐ
- 「標準にそのまま渡したか」の bool は持たない (`spelling == Original` か `route == "standard"` で分かる)
- resolve は path を返すだけなので、thread-cwd でしか届かない長さでは `ENAMETOOLONG`。それも届かせたい人は `bind` / `connect` を使う
- 既定の `bind` も綴りを残す (RS-Q4、kawaz 裁定 2026-11-20: a)。`SocketFile` を返さないので、その E はプロセスが終わるまで残り、D と一緒に OS の一時ディレクトリの掃除で消える。exec をまたぐプロセスの掃除の仕組みは作らない。片付けを気にする利用者は `_ex` か resolve を使う

## 利用者の回答 (2026-11-20)

llm-gateway の統括 (sockat-rs 0.4.1 を使用):

- 使うのは `bind`・`connect_nonblocking`・`connect` (同期、ECONNREFUSED で残骸を見分ける) だけ。`_ex`・最終手段・`getsockname` は使わない。STREAM だけで DGRAM / SEQPACKET の需要は無い
- 実運用のパスは 60〜66 バイトで長いパスの経路を通らない。長くなるのは試験 (TMPDIR が 113 バイト) と、利用者が長い置き場を設定した時
- fork をやめても困らない。connect の順が今どおりなら振る舞いは変わらない
- 気になる点: 監督者や unit は落ちて起こし直されるので長いパスでは B が残る (次の sockat の掃除で足りる)。試験は並行して多数の bind / connect を長いパスで行うので、B の作成と片付けが並行で競合しないか、試験の後に残骸が残らないか。状態がアプリの置き場の外 ($XDG_RUNTIME_DIR / $TMPDIR / /tmp) に増える (MANUAL に書く)。connect の後の片付けで待ちが入ると tokio の上で困る (`connect_nonblocking` は待たずに返ること)
- 確かめてほしい点: macOS には $XDG_RUNTIME_DIR が無く、$TMPDIR が長い (113 バイト) 環境で B の綴りが収まるか

hyoui の統括 (sockat-rs 0.4.1 を使用):

- 使うのは `bind`・`connect`・`connect_nonblocking` だけ。STREAM だけ。Unix socket の `local_addr()` / `peer_addr()` は読まず、unlink・stat は元のパスで行う。別の uid とは通信せず、PrivateTmp の指定も無い。OS は Linux と macOS
- 実運用のパスは 55〜82 バイト (ファイル名 41 / 15)。長くなるのは状態の root を深い所に向けた時、`--socket` の指定、試験 (104〜305 バイト)
- fork をやめても困らない。fork-cwd に当たるのは Linux の seccomp の下で `--socket` にファイル名 80〜96 バイトを指定した時だけ (実測)。fork の子が親の fd を複製する副作用が無くなるのは良い点
- connect する側 (CLI) は短命で数が多く、sandbox の中で書ける置き場が無いことがある。connect は書き込みもスレッドも要らない経路を先に、を保ってほしい
- 確かめてほしい点 1: 既定の `bind` が消さない D を作ると、std の型しか返らないので利用者に片付けの手がかりが無い。長命の daemon や、1 プロセスで長いパスの bind を数十回行う試験で D が溜まる。「既定の `bind` は呼び出しの中で片付ける今の形、消さない綴りは `_ex` / resolve を選んだ人だけ」と比べてほしい
- 確かめてほしい点 2: exec をまたぐプロセス (`hyoui upgrade` は pid を変えずに execve し、listener の fd と path を引き継ぐ)。B の fd は CLOEXEC で閉じるので、旧い B / D は片付けられずに残る。B の名前に PID を入れる掃除の案では「その PID は生きている」ので消されない。procB の綴りは fd が閉じた時点で辿れなくなる
- 1 マシンで数十の daemon が動くので、掃除は生きている他のプロセスの B を消さない判定が要る

## 未決

### 案がまだ無い

- 届く長さ: procB の綴りは `/proc/<pid>/fd/<fd>/` + D + `/d/` でおよそ 35 バイト食い、Linux で届くファイル名はおよそ 70。今の thread-cwd (96) の間は今の経路に回す
- `send_to` は resolve の綴りに送るので relative の経路 (送った後に取り消せない) を使わない。resolve で済まない長さの `send_to` をどうするか (thread-cwd で送る、`ENAMETOOLONG` にする)
- 長いパスに bind した DGRAM の送り手への返信は、綴りが生きている間は届く (procB は同じ uid、tmpB は別の uid も)。届かない場面 (`cleanup` の後、procB で別の uid) を綴りの性質 (S1) でどう表すか
