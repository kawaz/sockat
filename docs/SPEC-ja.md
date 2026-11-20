# sockat 仕様

> [English](./SPEC.md) | 日本語

言語によらない sockat の振る舞い (利用者と、各言語の README を書く人に向けた約束)。各言語の実装はこれに従う。

- 経路の作り方 (置き場 B の作り方、各経路の手順): [SPEC-routes-ja.md](SPEC-routes-ja.md)
- どの条件でどこまで届くか: [届く範囲の表](../pages/reach/README-ja.md)
- 判断と却下した案: [docs/decisions](decisions/INDEX.md) (今の設計の正本は [DR-0017](decisions/DR-0017-resolve-through-persistent-base.md))
- 言語固有の話 (型、ランタイム連携、メモリ安全の扱い): 各言語のリポ ([sockat-rs](https://github.com/kawaz/sockat-rs)、[sockat-py](https://github.com/kawaz/sockat-py)、[sockat-go](https://github.com/kawaz/sockat-go)) の README とマニュアル

## 用語

| 用語 | 意味 |
|---|---|
| 標準 | その言語の標準ライブラリの Unix domain socket の bind / connect |
| 標準に渡す長さ | その言語の標準が受け付けるパスの最長。これ以下は標準にそのまま渡す。多くは `sun_path` − 1、Java は `sun_path` − 2 ([DR-0004](decisions/DR-0004-standard-length-per-language.md)) |
| sockaddr に入る長さ | `sun_path` の長さ − 1 バイト (NUL の分を除く)。広げていない sockaddr に入る綴りの最長 |
| 元のパス | 利用者が渡したパス |
| ディレクトリ / ファイル名 | 元のパスの最後の要素の前と、最後の要素。ソケットのディレクトリは前者 |
| 綴り | カーネルに渡すパスの文字列。bind の綴りはカーネルが覚え、`getsockname` / `getpeername` で返す |
| 経路 | 元のパスと同じ所を指す別の綴りを作り、それで bind / connect するやり方。名前は「[経路の名前](#経路の名前)」 |
| 試す | 経路が使えるかを確かめ、使えればその綴りで bind / connect すること。使えなければ次の経路へ進む |
| 使えない / 失敗 | 使えない: 経路自体が使えない (綴りが収まらない、手段が無い、B・D・E を作れない)。失敗: 実際に bind / connect して OS がエラーを返した ([経路の失敗の扱い](SPEC-routes-ja.md#経路の失敗の扱い)) |
| 置き場 | B を作る場所。`/tmp`・`$XDG_RUNTIME_DIR`・`$TMPDIR`・ソケットのディレクトリのどれかか、利用者が `Options.base` で指定した所 ([実体の置き場](SPEC-routes-ja.md#実体の置き場)) |
| B | 置き場の中に作る実在のディレクトリ。利用者ごとで、プロセスをまたいで使い回す |
| D | B の中に (プロセス, B) ごとに 1 つ作るディレクトリ。名前は乱数 |
| E | symlink。ソケットのディレクトリを指す物 (link-dir と thread-cwd・at) と、ソケットのファイルを指す物 (link-file) がある |
| procB | B を `/proc/<pid>/fd/<B の fd>` で綴る形。同じ uid のプロセスだけが辿れ、プロセスが終われば辿れない |
| 実パスの綴り | B をその実パスで綴る形 |
| resolve | 長いパスを、B・D・E を通る短い綴りに言い換えて返すこと ([resolve](#resolve)) |
| 綴りの性質 | bind の綴りを後で使えるか。`Spelling` で返す ([綴りの性質 `Spelling`](#綴りの性質-spelling))。`Dangling` は片付け済みの E を含み、どこにも届かない綴り |
| connect 系 | `connect`・`connect_nonblocking` と、それぞれの `_ex` |
| `/proc` を使える | `/proc/self/fd/<fd>` と `/proc/<pid>/fd/<fd>` を引ける |

OS は次の括りで呼ぶ。

| 括り | 中身 |
|---|---|
| Linux / Android | Linux カーネルの OS |
| Apple の OS | macOS、iOS 等。macOS とだけ書いた所は macOS で実測したこと |
| FreeBSD、NetBSD、OpenBSD、illumos | それぞれの OS |
| その他の Unix | 上のどれでもない Unix 系の OS |

## 対象

- pathname 型の Unix domain socket の bind (と listen) / connect / `send_to`
- ソケットの型は stream・DGRAM・SEQPACKET (DGRAM と SEQPACKET の細部は「[未確定](#未確定)」)
- Unix 系の OS。Windows は対象外

## 公開する操作

- 型ごとのモジュールに std の形で置く (stream は crate 直下、`datagram::`、`seqpacket::`)
- 既定の操作は path だけを取る。後始末と診断が要る人のために、既定の操作ごとに `_ex(…, Options)` を 1 つずつ置く
- 綴りを自分で std に渡す人のために、resolve を用途ごとに 2 つ置く ([resolve](#resolve))
- 置き場の死んだ D を消す `sweep()` を置く ([`sweep`](#sweep))
- 経路を利用者が選ぶ・組み合わせる口と、プロセス全体の既定を変える関数は作らない
- 名前は各言語の慣習で決める。Python は `_ex` を子モジュール `sockat.ex` に置く (標準の `socket.connect_ex` と紛れるため)。Go の stream は `Listen` / `ListenEx` / `Dial` / `DialEx`

### 関数

Rust の名前で示す。

| 型 | 関数 | 返す物 |
|---|---|---|
| stream | `bind(path)` | listen 済みの標準の listener |
| stream | `connect(path)` | 標準の stream |
| stream | `connect_nonblocking(path)` | 非ブロッキングの標準の stream |
| stream | `bind_ex(path, Options)` | `Bound<UnixListener>` |
| stream | `connect_ex(path, Options)` | `Connected<UnixStream>` |
| stream | `connect_nonblocking_ex(path, Options)` | `Connected<UnixStream>` (stream は非ブロッキング) |
| DGRAM | `datagram::bind(path)` | 標準の `UnixDatagram` |
| DGRAM | `datagram::unbound()` | 標準の `UnixDatagram` |
| DGRAM | `datagram::connect(&sock, path)` | 無し |
| DGRAM | `datagram::send_to(&sock, buf, path)` | 送ったバイト数 |
| DGRAM | `datagram::bind_ex(path, Options)` | `Bound<UnixDatagram>` |
| DGRAM | `datagram::connect_ex(&sock, path, Options)` | `Report` |
| DGRAM | `datagram::send_to_ex(&sock, buf, path, Options)` | 送ったバイト数と `Report` |
| SEQPACKET | `seqpacket::bind(path)`・`connect(path)`・`connect_nonblocking(path)` と各 `_ex` | 未確定 |
| resolve | `resolve_for_bind(path, Options)` | `ForBind` |
| resolve | `resolve_for_connect(path, Options)` | `ForConnect` |
| 置き場 | `sweep()` | 無し |

- 失敗は、既定の操作は標準と同じエラーの型、`_ex` と resolve はエラーに診断を付けた型 ([診断](#診断))
- DGRAM は std の `UnixDatagram` の、パスを取る関数と、それと組で使う `unbound` だけを写す。`pair` は写さない

### `Options`

| 項目 | 中身 |
|---|---|
| `usable_cross_uid: bool` | 別の uid の相手も辿れる綴りを求める。B の選び方と、procB を使わないことに効く。満たせなければ thread-cwd / at に進む ([別の uid と PrivateTmp](SPEC-routes-ja.md#別の-uid-と-privatetmp))。満たせたかは結果の `Spelling` で分かる |
| `base: Option<Path>` | 利用者が B の実体の場所を指定する (アプリが自分の管理する場所を渡す。例 `/tmp/app-<uid>/sockat`)。その所に B を作り、確かめて外れたらエラーで、自動の置き場に落とさない。綴りの形は自動の時と同じ順で選ぶ |

### 返す物

| 型 | 中身 |
|---|---|
| `Bound<S>` | `socket` (標準の型)、`file: SocketFile` (`remove()`・`cleanup()`)、`spelling: Spelling`、診断 (`route`・`base`・`skipped`) |
| `Connected<S>` | `socket` (標準の型)、診断 (`route`・`skipped`) |
| `Report` | 診断 (`route`・`skipped`) |
| `ForBind` | `path` (綴り)、`spelling`、`remove()`、`cleanup()`、診断 |
| `ForConnect` | `path` (綴り)、`cleanup()`、診断。`remove()` は持たない (消し間違いを型で防ぐ) |

- `remove()` と `cleanup()` は「[片付け](#片付け)」
- connect の綴りの性質は返さない (connect の綴りは相手に残らない)
- 「標準にそのまま渡したか」の bool は持たない (`spelling == Original` か `route == "standard"` で分かる)
- 項目と型の名前は各言語の慣習で決める

### ブロックしない connect

- connect の前にソケットを非ブロッキングにして、そのまま返す。相手の backlog が満杯なら待たずに失敗する
- `EINPROGRESS` はエラーとして返し、ソケットを閉じる
- 片付けで待たない (既定の connect が link-file で作った E は unlink するだけ)
- 標準の connect が元から待たない言語 (Node.js、Go 等) は、標準と同じ形の connect を 1 つだけ出し、`_nonblocking` を分けない。`connect_ex` 系も同じ ([DR-0003](decisions/DR-0003-single-connect-when-standard-never-blocks.md))。Go の `Dial` / `DialEx` は標準の `net.DialUnix` と同じく待たない (backlog が満杯なら Linux は即 `EAGAIN`、macOS は `ECONNREFUSED`)

### 標準と同じにすること

- 戻り値の listener / stream / datagram は標準が返すのと同じ型。標準の代わりに置き換えるだけで使える
- 自前で作るソケットは、その言語の標準が作るソケットと同じ設定にする (close-on-exec、`SO_NOSIGPIPE`、listen の backlog 等)。backlog を指定する口は作らない
- 標準の listener を閉じた時にソケットのファイルが消えるかは、標準と同じ仕組みに任せる (長いパスでの違いは「[長いパスで標準と違う点](#長いパスで標準と違う点)」)。`bind_ex` の listener は短いパスでも閉じた時に消さず、消すのは `remove()` だけ

### 診断

`_ex` と resolve は、成功した時に次を返す。

| 項目 | 中身 |
|---|---|
| `route` | 通った経路の名前 |
| `base` | bind で使った B の綴り (`proc`・`sockdir`・`runtime`・`tmpdir`・`tmp`) |
| `skipped` | 試して使えなかった経路の並び (試した順)。各要素は `{ name: 経路の名前, reason: 使えなかった理由 }`。長いパスでは `standard` も入る |

- `route` より前に試した経路はすべて使えなかったもの (実際に bind / connect して失敗したら、そこでエラーを返して次を試さない。bind の link-file を実行時に見分ける時だけは次へ進む)。そのため「使えたか」の真偽値は持たない
- `route`・`base`・`skipped` の名前と `reason` は診断用で、中身を約束しない (経路は増えたり変わったりする)。分岐には `Spelling` を使う
- 経路の名前は日英で同じ ASCII
- `_ex` が失敗した時も、エラーに `skipped` を付ける。実際に bind / connect して失敗した経路があれば、その名前 (`route`) も付ける (全部が使えなかった `ENAMETOOLONG` では無い)
- 付け方は各言語の慣習に従う。OS のエラーの errno は取り出せる形を保つ (Rust は errno を持つエラー型に `skipped` を持たせる、Go は `Unwrap` で errno に届くエラー型、Python は例外の属性 等)

## resolve

長いパスを、元のパスと同じ所を指し続ける短い綴りに言い換えて返す。綴りが生きている間は、`getsockname` の綴りで消す上のライブラリ、DGRAM の返信、運用の道具が元のパスと同じに働く。綴りはただのパスなので、ソケットの型 (stream / DGRAM / SEQPACKET) と操作 (bind / connect / `send_to`) を問わず、利用者が std に渡して使える。

| | `resolve_for_bind` | `resolve_for_connect` |
|---|---|---|
| 綴り | `B/D/E/<ファイル名>` (link-dir) を先に、`B/D/E` (link-file) をその後に | `B/D/E` (link-file)。ファイル名の長さによらない |
| link-file を選ぶ理由 | Linux 等では bind が最後の要素の symlink を辿らず、link-file を使えない | connect は最後の要素の symlink をいつも辿る |
| 返す物 | `ForBind` (`spelling`、`remove()`、`cleanup()`) | `ForConnect` (`cleanup()`) |

- 標準に渡す長さ以下のパスはそのまま返す (絶対パスは `Original`、相対パスは `CwdRelative`)
- resolve は綴りを返すだけなので、thread-cwd・at でしか届かない長さでは `ENAMETOOLONG`。それも届かせたい人は `bind` / `connect` を使う
- B の綴り (procB か実パス) の選び方は既定の操作と同じ ([綴りの形](SPEC-routes-ja.md#綴りの形))
- resolve のたびに B の中を一覧しない (resolve の手数を増やさない)
- 同じパスへの connect を繰り返す時は、`resolve_for_connect` で 1 度作った綴りを何度も connect に使い、最後に `cleanup` する
- 既定の `bind` は内部で resolve を使い、resolve で済まない長さには thread-cwd・at で届かせる。既定の `connect` は D を作らない ([connect の順](#connect-の順))。既定の bind は綴りを残し、既定の connect は残さない

## 綴りの性質 `Spelling`

bind の綴りを後で使えるかを 1 つの値で返す (`Bound` と `ForBind` の `spelling`)。

```rust
#[non_exhaustive]
pub enum Spelling {
    Original,
    CwdRelative,
    Linked { removable: bool, until: Until, usable_cross_uid: bool, usable_with_private_tmp: bool },
    Dangling,
}
```

| 値 | 綴り | 経路 |
|---|---|---|
| `Original` | 元の絶対パス | standard |
| `CwdRelative` | 元の相対パス。cwd を変えると別の所を指す (標準が元から持つ危険だが、知らせる) | standard |
| `Linked` | B・D・E を通り、元のパスと同じ所を指す | link-dir、link-file |
| `Dangling` | 片付け済みの E を含む。どこにも届かない | thread-cwd、at |

`Linked` の属性:

| 属性 | 中身 | 値 |
|---|---|---|
| `removable` | 綴りで unlink すると実体が消えるか | link-dir は true (途中の E を辿る)。link-file は false (最後の symlink は辿られず E が消える。消すには `remove` が要る) |
| `until` | 綴りがいつまで辿れるか | `Process` (procB: プロセスが終われば辿れない)。`Cleanup` (実パスの綴り: E は `cleanup` まで、D はプロセスが終わった後の OS の掃除まで残る) |
| `usable_cross_uid` | 別の uid の相手が辿れるか | procB は false (同じ uid・同じ PID 名前空間だけ。root は辿れる)。実パスの綴りは、B までの途中が全部 other に x を持てば true (`/tmp` の B)、そうでなければ false (`/run/user/<uid>` と macOS の `$TMPDIR` は 0700) |
| `usable_with_private_tmp` | 自分と相手のどちらかが `/tmp` を隔離していても (systemd の `PrivateTmp` 等) 相手が辿れるか | 綴りが `/tmp`・`/var/tmp` を通らなければ true。mount 名前空間が丸ごと違う相手 (コンテナ等) までは保証しない |

- connect の綴りは相手に残らないので返さない

## 片付け

### `remove` と `cleanup`

| 口 | すること | 持つ物 |
|---|---|---|
| `remove()` | bind したソケットのファイルを 1 回だけ消し、`cleanup` もする | `Bound` の `SocketFile`、`ForBind` |
| `cleanup()` | resolve の E を 1 回だけ片付ける | `Bound` の `SocketFile`、`ForBind`、`ForConnect` |

- どちらも自動では行わない (Rust の Drop でも消さない)。2 回目以降は何もしない (`remove` は resolve した綴りの物を 1 回だけ消す、の意味の冪等)
- B と D は sockat が片付けない ([置き場に残る物](#置き場に残る物))
- 片付けた後の綴りは使わない。B が `/tmp` にある時は、B が消えた後に他人が同じ名前で作り直しうる (std の元のパスを消した後に、そのディレクトリに書ける人が作り直せるのと同じ)

### `remove`

- `remove` はファイルを消すだけで、listener を閉じない。閉じるのは利用者
- bind したソケットのファイルの realpath と `(st_dev, st_ino)` を覚え、そのパスの `(st_dev, st_ino)` が同じ時だけ消す
  - 覚えるのは bind が通った直後 (listener を返す前)。覚えられなければ listener を閉じ、ファイルは消さずにエラーを返す (消せない `remove()` を成功に見せない)
  - 相対パスの時は、パスを何も引く前と、bind と覚えるための realpath の両方の後でプロセスの cwd の `(st_dev, st_ino)` を比べ、違えば覚えられない時と同じに扱う (間の cwd の変更で、元の cwd の無関係なファイルを覚えて消さないため。変えて戻した場合は見えない)
  - 引数のパスは入口で一度だけ文字列にし、覚える・bind する・返すのすべてにその値を使う
- ファイルが既に無い時と、別のファイルに置き換わっていて消さない時も成功を返す。失敗を返すのは、確かめられない時 (`lstat` が `ENOENT` / `ENOTDIR` 以外で失敗) と、消そうとして失敗した時
- 置き換えを見分けるのは `(st_dev, st_ino)` だけで、約束するのは listener を開いている間の置き換えまで。閉じた後に消して作り直された物は、番号をすぐ使い回すファイルシステム (ext4、BSD の UFS / FFS) で見分けられない。各言語の説明で、`remove` は listener を閉じる前に呼ぶよう勧める ([findings](findings/2026-11-19-inode-reuse-after-close.md))
- 確かめてから消すまでと、bind してから覚えるまでの間に、ソケットのディレクトリに書ける者がファイルをすり替えるのは防げない (inode を指定して消す手段が POSIX に無い)

| 言語 | 形 |
|---|---|
| Rust | `SocketFile` の `remove` |
| Python | 戻り値に引数なしの関数を含める |
| Go | 戻り値に `func() error` を含める。短いパスでも消すのはこれだけにする (`SetUnlinkOnClose(false)`) |

### 置き場に残る物

| | B | D | E |
|---|---|---|---|
| 作る単位 | 利用者ごと。プロセスをまたいで使い回す。1 つのプロセスが使う B は 1 つ (`usable_cross_uid` の時だけ、もう 1 つ使いうる) | (プロセス, B) ごとに 1 つ。作るのは、綴りを残す bind (thread-cwd・at を含む) と `resolve_for_connect` だけ | resolve ごと。thread-cwd・at と既定の connect の link-file は呼び出しごと |
| 生きている間 | 消さない | プロセスが flock (共有ロック) を掛けた fd を持ち続ける | resolve の E は消さない |
| 片付け | sockat はしない (`Options.base` の B はアプリが管理) | sockat はしない。死んだプロセスの D は OS の一時ディレクトリの掃除で消える。`sweep()` を呼んだ時だけ、ロックの外れた D を消す | resolve の E は `cleanup`。呼び出しごとの E は呼び出しの中で unlink |

- 既定の `bind` は `SocketFile` を返さないので、その E はプロセスが終わるまで残り、D と一緒に OS の一時ディレクトリの掃除で消える。exec をまたぐプロセスの掃除の仕組みは作らない。片付けを気にする利用者は `_ex` か resolve を使う
- 既定の `connect` はプロセスの中に状態を残さない (D を作らず、B の直下の E を connect の後すぐ unlink する)

OS の一時ディレクトリの掃除 ([research](research/2026-11-20-tmp-cleaners-and-persistent-base.md)):

| 置き場 | 死んだ D | 生きている D |
|---|---|---|
| Linux の `/tmp` | systemd-tmpfiles が 10 日の age で配下ごと消す | flock の掛かったディレクトリは配下ごと飛ばされる (systemd v242 以上)。v242 より古い環境 (RHEL 8 の v239 等) では 10 日で消されうる |
| `$XDG_RUNTIME_DIR` | age の掃除が無く、最終ログアウトと再起動まで残る | 同左 |
| macOS の `/tmp` | symlink の入ったディレクトリは消えないので、再起動まで残る | 消えない |
| macOS の `$TMPDIR` | dirhelper が 3 日で消しうる (種類ごとの扱いは未確認) | 同左 |
| FreeBSD・NetBSD・OpenBSD・illumos | 既定は消えないか、再起動で消える。日次の掃除は symlink を消さない | 同左 |

- 生きている D が消された時は、綴りが辿れなくなるだけで危険はない
- exec をまたぐと D の flock の fd が閉じ、引き継いだ listener が生きていても D・E は `sweep()` や OS の掃除で消されうる (綴りが辿れなくなるだけ)。procB の綴りは exec の時点で辿れなくなる

### `sweep`

- 呼んだ時だけ、B の中の持ち主の死んだ D (ロックの外れた D) を消す。生きている他のプロセスの D は消さない
- 自動では呼ばない (resolve のたびに B の中を一覧しない)

## 短いパス

標準に渡す長さ以下のパスは、標準にそのまま渡す。何も足さず、環境変数も読まない。それを超えたら経路に回す ([DR-0004](decisions/DR-0004-standard-length-per-language.md))。

- 先頭以外に NUL を含むパスは、長さによらず標準に渡さず引数の誤りにする ([DR-0006](decisions/DR-0006-nul-is-invalid-at-any-length.md))
- Linux / Android で先頭が NUL のパス (abstract namespace) は対象外で、長さによらず標準にそのまま渡す。言語固有の abstract の書き方 (Go の `@` 等) も同じ
- abstract namespace の無い OS では、先頭が NUL のパスも長さによらず引数の誤り
- 標準にブロックしない connect が無い言語では、ブロックしない connect に限り、標準と同じアドレスで自前のソケットを connect する
- 経路の綴りを標準が受け付けない時 (標準に渡す長さが sockaddr に入る長さより短い言語) も、標準と同じアドレスで自前のソケットを使う

| OS | sockaddr に入る長さ |
|---|---|
| Linux / Android / illumos | 107 バイト |
| Apple の OS / FreeBSD / NetBSD / OpenBSD | 103 バイト |

## 長いパスの経路と試す順番

標準に渡す長さを超えるパスは、次の順に経路を試し、最初に使えた経路で bind / connect する。各経路の作り方は [SPEC-routes-ja.md](SPEC-routes-ja.md#経路)、どこまで届くかは [届く範囲の表](../pages/reach/README-ja.md)。

- 最後がファイル名でないパス (`dir/`、`dir/.`、`dir/..`、`..`) は、何も作らずに引数の誤り
- ソケットのディレクトリを先に引く。無ければ `ENOENT`、ディレクトリでなければ `ENOTDIR` (長さの判定や B・D・E を作るより前)
- どの経路も、呼び出し元のプロセスの cwd も呼び出し元のスレッドの cwd も変えない
- fork はしない (bind・connect とも)。fork でしか届かなかった場面と fork の手法は [fork-cwd](../pages/fork-cwd-ja.md)

### 経路の名前

名前は「手段 + 何についてか」。接尾辞 `-direct` は E を通さずファイル名で渡す形。

| 名前 | 中身 | 操作 |
|---|---|---|
| `standard` | 標準にそのまま渡す | bind、connect |
| `link-dir` | ソケットのディレクトリを指す E を通す `B/D/E/<ファイル名>` | bind |
| `link-file` | ソケットのファイルを指す E を通す `B/D/E` (既定の connect は `B/E`) | bind、connect |
| `thread-cwd` | 使い捨てのスレッドの cwd を D に移し、すぐ消す E を通す `E/<ファイル名>` | bind |
| `at` | thread-cwd と同じ綴りを、スレッドを使わず `bindat` に D の fd で渡す | bind |
| `proc-direct` | `/proc/self/fd/<ソケットのディレクトリの fd>/<ファイル名>` | connect |
| `relative` | cwd からの相対パス | connect |
| `widened` | 広げた sockaddr | connect |
| `at-direct` | `connectat` にソケットのディレクトリの fd とファイル名を渡す | connect |
| `thread-cwd-direct` | 使い捨てのスレッドの cwd をソケットのディレクトリに移し、ファイル名で渡す | connect |

### bind の順

| 順 | 経路 | B の綴り | 綴り | 使う時 | `Spelling` |
|---|---|---|---|---|---|
| 1 | `standard` | | 元のパス | 標準に渡す長さ以下 | `Original` / `CwdRelative` |
| 2 | `link-dir` | procB | `B/D/E/<ファイル名>` | `/proc` を使えて収まる (`usable_cross_uid` の時は使わない) | `Linked` |
| 3 | `link-dir` | 実パス | 同 | 収まる | `Linked` |
| 4 | `link-file` | 実パス | `B/D/E` | bind が最後の要素の symlink を辿る OS | `Linked` |
| 5 | `thread-cwd` (FreeBSD は `at`) | | `E/<ファイル名>` | Linux / Android・Apple の OS (`at` は FreeBSD) | `Dangling` |
| 6 | `ENAMETOOLONG` | | | | |

- 綴りを残すので、生きている間は `getsockname` の綴りで消す上のライブラリと DGRAM の返信が元のパスと同じに働く。thread-cwd・at は resolve の綴りが収まらない時の後ろ
- link-file は、bind が symlink を辿らないと実測した OS (Linux / Android、FreeBSD、OpenBSD、illumos) では試さない。辿るのは macOS と NetBSD (実測 2026-11-19、[findings](findings/2026-11-19-bind-through-file-symlink.md))。他の OS では試して、辿るかを実行時に見分ける
- bind は proc-direct・relative・widened・at-direct を使わない。綴りが後で無関係なファイルに当たる (proc-direct、relative、at-direct) か、アドレスが途中で切れて読む側を壊す (widened)
- `usable_cross_uid` を満たす B が無いか、その綴りが収まらなければ、満たさない綴りに落とさず 5 に進む

### connect の順

書き込みもスレッドも要らない経路を先に、スレッドを立てる経路と置き場に書く経路をその後にする。

| 順 | 経路 | 中身 |
|---|---|---|
| 1 | `standard` | 元のパス |
| 2 | `proc-direct` / `relative` / `widened` / `at-direct` | 書き込みもスレッドも要らない (OS ごと、下の表) |
| 3 | `thread-cwd-direct` | D も E も要らない |
| 4 | `link-file` | B の直下に乱数の名前の E を作って `B/E` で connect し、すぐ E を unlink する。ファイル名の長さによらず届く |
| 5 | `ENAMETOOLONG` | |

| OS | 2 の経路 |
|---|---|
| Linux / Android (`/proc` を使える) | proc-direct |
| Linux / Android (`/proc` を使えない) | relative |
| Apple の OS | relative → widened |
| FreeBSD | at-direct |
| NetBSD / OpenBSD / illumos / その他の Unix | relative |

- connect の綴りは相手に残らない (connect した側のソケットは bind されない) ので、E を残さない。CLI の 1 回だけの connect は普通 2 で終わり、置き場に書けない sandbox でも届く
- relative と widened は、置き場を通す経路より遠くまで届く場面がある
- 3 を使える OS は Linux / Android・Apple の OS ([thread-cwd-direct](SPEC-routes-ja.md#thread-cwd-direct))

## 長いパスで標準と違う点

| 点 | 内容 |
|---|---|
| カーネルが返すアドレス | bind した側の `getsockname` と、そこへ connect した側の `getpeername` は元のパスでなく bind の綴りを返す。後で使えるかは `Spelling` で分かる。標準の型でアドレスを返す口を差し替えられる言語 (Python) は元のパスを返す。illumos では connect した側の `getpeername` が、bind した綴りでなく connect に渡した綴りを返す (sockat-rs の CI で実測 2026-11-19) |
| 運用の道具での見え方 | `ss -x`・`lsof`・`/proc/net/unix` 等に出るアドレスが bind の綴りになる。link-dir と thread-cwd・at はファイル名が綴りの最後に残る。link-file の綴りにはファイル名が出ない |
| listener を閉じた時 | 閉じる時にアドレスの綴りで消す標準 (Go の `UnixListener.Close` 等) は、`removable` が true の綴りなら元のパスのファイルを消す。link-file の綴りでは E が消えてファイルは残り、`Dangling` では何も消えない |
| ディレクトリを先に引く | thread-cwd・at の E はソケットのディレクトリの realpath を指し、proc-direct・at-direct・thread-cwd-direct はディレクトリを引いてからファイル名で渡す。その間の rename や symlink の張り替えは反映されない |
| 他のスレッドの chdir | relative は、間に cwd が変わったままなら一般のエラー。変えて戻した場合は見えない |
| 状態がアプリの置き場の外に増える | B・D・E が `/tmp`・`$XDG_RUNTIME_DIR`・`$TMPDIR` に残る。既定の `bind` の E と死んだプロセスの D は OS の掃除まで残る ([置き場に残る物](#置き場に残る物)) |
| 生きている D が消されうる環境 | systemd v242 より古い Linux と、B が macOS の `$TMPDIR` にある時 ([置き場に残る物](#置き場に残る物))。綴りが辿れなくなるだけ |
| `PrivateTmp` の相手 | 相手の `/tmp` が隔離されていると、`/tmp` を通る綴りを相手は辿れない。Linux では procB を先に使うので、まず起きない。辿れるかは `usable_with_private_tmp` で分かる |

- 先頭以外の NUL は短いパスでも引数の誤り。標準が NUL で黙って切り詰める言語 (Go 等) では、README の「標準と違う点」に書く

## 使ってはいけない書き方

sockat を使う時に、無関係なファイルを消したり、ファイルを消し損ねたりする書き方。利用者への注意はこの節が正本で、他の節と各言語の文書はここを指す。各言語の README / マニュアルは、同じ見出しで、その言語での具体的な形 (例: Go の `os.Remove(l.Addr().String())`) と避け方の推奨コード (試験として動かす) を置く。

| 書き方 | なぜいけないか | 代わりに |
|---|---|---|
| `Spelling` を見ずに、カーネルが返す綴り (`getsockname`、listener のアドレス等) でソケットのファイルを unlink / stat する | link-file の綴りでは E が消えるだけでファイルは残る。`Dangling` の綴りはどこにも届かない | 元のパスを持っておいて使う。`remove()` |
| `cleanup` の後やプロセスが終わった後に、古い綴りを使う | 片付けた後の `/tmp` の B は、他人が同じ名前で作り直しうる。procB の綴りはプロセスが終われば辿れない | 綴りは `until` の間だけ使う |
| 相対パスで bind し、cwd を変えた後にその相対パスで消す | 別の場所のファイルに当たる (`CwdRelative`) | bind の前に絶対パスにする。`remove()` |
| listener を閉じればソケットのファイルが消えると当てにする | 長いパスでは綴りしだいで消えない (「[長いパスで標準と違う点](#長いパスで標準と違う点)」)。`bind_ex` の listener は閉じても消さない | `remove()` か、元のパスで消す |
| `remove()` で listener も閉じると当てにする | `remove()` はファイルを消すだけ | listener は自分で閉じる |
| listener を閉じた後に `remove()` を呼ぶ | 閉じた後に作り直された別のファイルを見分けられないことがある ([`remove`](#remove)) | listener を閉じる前に呼ぶ |
| `procB` の綴りや `usable_cross_uid` が false の綴りを別の uid の相手に辿らせる | 辿れない | `Options.usable_cross_uid` を指定し、結果の `Spelling` を確かめる |
| `_ex` の `route`・`base`・`skipped`・`reason` の文字列で分岐する | 診断用で、中身を約束しない | `Spelling` で分岐する |

## エラー

| 状況 | エラー |
|---|---|
| ディレクトリが無い / connect 先が無い | `ENOENT` |
| ディレクトリの位置にディレクトリでない物がある | `ENOTDIR` |
| bind 先に既にファイルがある | `EADDRINUSE` |
| 誰も listen していないソケットファイル | `ECONNREFUSED` |
| backlog が満杯 | Linux はブロックしない connect で `EAGAIN` (ブロックする connect は待つ)、macOS は `ECONNREFUSED` |
| どの経路も使えない (綴りが収まらない、手段が無い) | `ENAMETOOLONG` |
| resolve で、thread-cwd・at でしか届かない長さ | `ENAMETOOLONG` |
| `Options.base` の確認に外れた。B までの途中のディレクトリが無い | エラー (自動の置き場に落とさない) |
| 標準に渡す長さを超えるパスで、名前で終わらない | 引数の誤り |
| 先頭以外に NUL を含むパス (長さによらない) | 引数の誤り |
| relative の途中で cwd が変わった | 一般のエラー |

- ディレクトリを先に引くので、`ENOENT` と `ENOTDIR` はどの OS でも長さの判定より前に決まる
- OS のエラーは、その言語の作法で errno を取り出せる形で返す
- 「引数の誤り」「一般のエラー」をどの型で表すかは各実装が決める

## 各実装に求めること

- この仕様の経路と順番に従う ([SPEC-routes-ja.md](SPEC-routes-ja.md))。その言語で作れない経路は飛ばし (使えない経路として次へ進み、`_ex` の `skipped` に理由付きで入れる)、README に OS × 経路の表で明示する
- 言語によらない適合試験 ([docs/design/conformance.md](design/conformance.md)) の試験用 CLI を用意する
- 自前で作ったソケットを標準の型に取り込む言語では、widened で connect したソケットを取り込んでも、取り込みやアドレスの取得で落ちないか確かめる。落ちるなら widened を作れない経路として飛ばす
- 経路は公開 API に出さない。試験はパッケージの中から各経路を直接呼んで強制する
- 環境を読む部分 (置き場の候補、`/proc` の場所、Apple の OS で広げた sockaddr を受け付けるか、スレッドの cwd を使えるか) は試験から差し替えられるようにする
- README とマニュアルにこの仕様へのリンクを置く。仕様と食い違う振る舞いを入れる時は、先にこの仕様を直す
- 利用者向けの説明に書くこと: 状態がアプリの置き場の外に増えること、片付けた後の綴りは使わないこと、`PrivateTmp` の相手、systemd v242 より古い環境と macOS の `$TMPDIR` で生きている D が消されうること (各項目は「[長いパスで標準と違う点](#長いパスで標準と違う点)」と「[使ってはいけない書き方](#使ってはいけない書き方)」)

## 実装が確かめる試験の観点

| 観点 | 確かめること |
|---|---|
| 短いパスの境界 | 標準に渡す長さちょうどは標準にそのまま渡り、1 バイト長いと経路に回る (標準自身で境界を確かめる) |
| 綴りが当たる所 | 綴りを unlink / stat しても無関係なファイル (cwd の同名ファイル、fd の番号を使い回させた別のディレクトリの同名ファイル) に当たらない |
| B の確認 | B までの途中の確認で外れた置き場を使わない。`Options.base` が外れたらエラー |
| 並行 | 並行する多数の bind / connect で B・D の作成が競合しない |
| `sweep` | 生きている他のプロセスの D を消さない |
| `cleanup` | `cleanup` の後に E が残らない |
| 既定の connect | connect の後に B の直下に何も残らず、待ちも入らない |
| `remove` | ファイルが消え、listener は閉じない。listener を開いている間に別のファイルに置き換えられていたら消さない |
| thread-cwd・at | 強制して、プロセスの cwd も呼び出し元のスレッドの cwd も変わらず、呼び出しの後に E が残らない。ソケットが元のパスにでき送受信できる |
| link-file の bind | bind が symlink を辿らない OS で `skipped` に入り、何も残らない。元のパスに物がある時はそのエラー (`EADDRINUSE`) を返し、次を試さない |
| connect の経路 | proc-direct・relative・widened・at-direct・thread-cwd-direct・link-file を 1 つずつ強制して、ソケットに届く |
| 失敗をやり直さない | `ENOENT` / `EADDRINUSE` / `ECONNREFUSED` を返し、後の経路に何も作らない |
| relative と cwd | relative の途中で cwd が変わったら一般のエラー |
| macOS | connect 系で 253 バイトのパスが widened で通る。bind は widened を使わない |
| ブロックしない connect | backlog が満杯で待たずに失敗する |
| 名前で終わらないパス、先頭以外の NUL | 何も作らずに引数の誤り。NUL は短いパスでも。先頭が NUL (abstract) は標準に渡る |
| カーネルが返すアドレス | 長いパスでも取得で落ちない。差し替えられる言語では、listener・accept したソケット・connect したソケットの各口が元のパスを返し、その言語の代表的な上のライブラリ (Python の asyncio の `start_unix_server(sock=...)` 等) が引数を足さずに短いパスと同じに動く |

- 経路は OS で違うので、少なくとも macOS と Linux で回す。他の Unix は CI の VM で回す
- cwd やシグナルの扱いのようにプロセス全体に効く設定を変える試験は、子プロセスの中で行う

## 未確定

- 届く長さ: procB の綴りは `/proc/<pid>/fd/<fd>/` + D + `/E/` でおよそ 35 バイト食い、Linux で届くファイル名はおよそ 70。thread-cwd との間は thread-cwd に回す
- B・D・E の名前の長さ (届く範囲に効く。届く範囲の表は B を 17 バイトで見積もっている)
- FreeBSD の connect で link-file を使えるか (未確認)
- `send_to` は resolve の綴りに送るので relative (送った後に取り消せない) を使わない。resolve で済まない長さの `send_to` をどうするか (thread-cwd で送る、`ENAMETOOLONG` にする)
- 長いパスに bind した DGRAM の送り手への返信は、綴りが生きている間は届く (procB は同じ uid、`/tmp` の B の実パスは別の uid も)。届かない場面 (`cleanup` の後、procB で別の uid) を `Spelling` でどう表すか
- Rust の SEQPACKET の返す型
- `ForBind` の `remove()` の同一性: resolve の時点では bind していないので、ソケットのファイルの `(st_dev, st_ino)` を覚えられない。形は未決 (案: bind した後に呼んで `SocketFile` を受け取る口)
- Android と macOS 以外の Apple の OS は全体が未確認
- NetBSD・OpenBSD・illumos は peer の資格情報が未確認
- ブロックしない connect が `EINPROGRESS` を返さないことは Linux と macOS でだけ確認済み
