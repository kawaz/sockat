# sockat 仕様

> [English](./SPEC.md) | 日本語

言語によらない sockat の振る舞い。各言語の実装はこれに従う。判断と却下した案は [docs/decisions](decisions/INDEX.md)、Rust 固有の話 (型、`unsafe` の置き場、tokio) は [sockat-rs の MANUAL](https://github.com/kawaz/sockat-rs/blob/main/docs/MANUAL-ja.md) にある。

## 用語

| 用語 | 意味 |
|---|---|
| 標準 | その言語の標準ライブラリの Unix domain socket の bind / connect |
| 標準に渡す長さ | その言語の標準が受け付けるパスの最長。これ以下は標準にそのまま渡す。多くは `sun_path` − 1、Java は `sun_path` − 2 ([DR-0004](decisions/DR-0004-standard-length-per-language.md)) |
| sockaddr に入る長さ | `sun_path` の長さ − 1 バイト (NUL の分を除く)。広げていない sockaddr に入る綴りの最長 |
| ディレクトリ / ファイル名 | パスの最後の要素の前と、最後の要素 |
| 綴り | カーネルに渡すパスの文字列。同じ場所を指す別の綴りを作るのが経路 |
| D | sockat が bind / connect のたびに作る自分専用のディレクトリ ([D と R](#d-と-r)) |
| R | ソケットのディレクトリを指す乱数の名前の symlink。D の中 ([D 無しの形](#d-無しの形)ではソケットのディレクトリの中) に作る |

## 対象

- pathname 型の Unix domain socket の bind (と listen) / connect
- Unix 系の OS。Windows は対象外

## 公開する操作

| 操作 | Rust | Python | Go | fork | ブロック | 戻り値 |
|---|---|---|---|---|---|---|
| bind | `bind` | `bind` | `Listen` | 試す | (待たない) | listen 済みの標準の listener |
| 後始末つきの bind | `bind_ex` | `bind_ex` | `ListenEx` | 試す | (待たない) | 標準の listener と `discard()` |
| 何かを失ってでも届く bind | `bind_any` | `bind_any` | `ListenAny` | 試す | (待たない) | 標準の listener と、`losses`・`route`・`skipped` |
| connect | `connect` | `connect` | `Dial` | 試さない | する | 標準の stream |
| ブロックしない connect | `connect_nonblocking` | `connect_nonblocking` | なし | 試さない | しない | 非ブロッキングの標準の stream |
| 何かを失ってでも届く connect | `connect_any` | なし | なし | 試す | する | 標準の stream と、`losses`・`route`・`skipped` |
| 同 (ブロックしない) | `connect_any_nonblocking` | なし | なし | 試す | しない | 同上 (stream は非ブロッキング) |

- 名前は仮。他の言語はその言語の命名の慣習に合わせる。振る舞いは上の表に従う
- 戻り値の listener / stream は標準が返すのと同じ型。標準の代わりに置き換えるだけで使える
- `_ex` は bind の側だけ。bind したソケットのファイルの realpath と `(st_dev, st_ino)` を覚え、`discard()` でそのパスの `(st_dev, st_ino)` が同じ時だけファイルを消す。`discard()` は listener を閉じない (閉じるのは利用者) ([DR-0014](decisions/DR-0014-discard-removes-only.md))
  - 覚えるのは bind が通った直後 (経路の中で、listener を返す前)。覚えられなければ listener を閉じ、ファイルは消さずにエラーを返す (消せない `discard()` を成功に見せない)
  - 引数のパスは入口で一度だけ文字列にし、覚える・bind する・返すのすべてにその値を使う (呼ぶたびに違う値を返しうるパスの型で、覚えた物と bind した物を食い違わせない)
  - `discard()` は、ファイルが既に無い時と別のファイルに置き換わっていて消さない時も成功を返す。失敗を返すのは、確かめられない時 (`lstat` が `ENOENT` / `ENOTDIR` 以外で失敗) と消そうとして失敗した時 (消せたか分からないのを成功に見せない)
  - 確かめてから消すまでと、bind してから覚えるまでの間に、ソケットのディレクトリに書ける者がファイルをすり替えるのは防げない (inode を指定して消す手段が POSIX に無い)
- any 系 (`bind_any`、`connect_any` 系) は、既定の経路が全部使えない時に、何かを失ってでも届かせる ([DR-0013](decisions/DR-0013-any-means-reach-at-any-cost.md))。`bind_any` は最後に置き場の [symlink](#symlink)、`connect_any` 系は最後に [fork-direct](#fork-direct) を試す。pid は返さない
- any 系は成功した時に次の 3 つを返す ([DR-0013](decisions/DR-0013-any-means-reach-at-any-cost.md))
  - `losses`: 通った経路で失ったものの名前の並び (「[失うもの](#失うもの)」の名前。何も失っていなければ空)。分岐に使う。名前は約束で、変えずに足すだけ (知らない名前は「何かを失った」とだけ読むと説明に書く)。名前の間に大小や包含の関係は無い
  - `route`: 通った経路の名前
  - `skipped`: 試して使えなかった経路の並び (試した順)。各要素は `{ name, reason }` (経路の名前と使えなかった理由)。`route` より前に試した経路はすべて使えなかったものなので、「使えたか」は持たない
  - `route`・`skipped` の名前と `reason` は診断用で、中身を約束しない (経路は増えたり変わったりする)
  - 項目と型の名前は各言語の慣習で決める。失うものの名前は各言語の慣習 (enum 等) で表してよいが、文字列にした時は SPEC の名前と同じにする
- any 系が失敗した時も、エラーに `skipped` を付ける。実際に bind / connect して失敗した経路があれば、その名前 (`route`) も付ける (全部が使えなかった `ENAMETOOLONG` では無い) ([DR-0013](decisions/DR-0013-any-means-reach-at-any-cost.md))
  - 付け方は各言語の慣習に従う。OS のエラーの errno は取り出せる形を保つ ([エラー](#エラー))
- any 系は既定の API に出さず、使う人が選んで有効にする仕組みの後ろに置く (Rust は feature `any`)。`connect_any` 系は fork の経路を作れない言語では既定の connect と変わらないので出さず、README の表に「fork の経路なし」と書く ([DR-0002](decisions/DR-0002-no-connect-any-without-fork.md))。`bind_any` は fork の有無によらず出す
- 標準の connect が元から待たない言語 (Node.js 等) は、標準と同じ形の connect を 1 つだけ出す ([DR-0003](decisions/DR-0003-single-connect-when-standard-never-blocks.md))
- `connect` / `connect_nonblocking` は [fork-direct](#fork-direct) に来た所で `ENAMETOOLONG` を返す
- ブロックしない connect は、connect の前にソケットを非ブロッキングにしてそのまま返す。相手の backlog が満杯なら待たずに失敗する。`EINPROGRESS` はエラーとして返し、ソケットを閉じる
- 自前で作るソケットは、その言語の標準が作るソケットと同じ設定にする (close-on-exec、`SO_NOSIGPIPE`、listen の backlog 等)。backlog を指定する口は作らない
- listener を閉じた時のソケットファイルは、短いパスでは標準と同じ (Go の標準は消す)。長いパスでは、標準が消す言語でも消さない (カーネルが覚えている綴りは元のパスでない)。消す言語では README の「標準と違う点」に書く。消すのは `_ex` の `discard()`

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
| macOS / iOS 等 Apple の OS / FreeBSD / NetBSD / OpenBSD | 103 バイト |

## 長いパスの経路と試す順番

標準に渡す長さを超えるパスは、次の順に試し、最初に使えた経路で bind / connect する ([DR-0012](decisions/DR-0012-own-directory-and-thread-cwd.md))。

- 最後がファイル名でないパス (`dir/`、`dir/.`、`dir/..`、`..`) は、何も作らずに引数の誤り
- 最初にソケットのディレクトリを `stat` で引き、realpath を取る。無ければ `ENOENT`、ディレクトリでなければ `ENOTDIR`、realpath を引けなければそのエラー (どれも長さの判定や D を作るより前)。ソケットのディレクトリの fd が要る経路 ([proc-direct](#proc-direct)、[at-direct](#at-direct)、[fork-direct](#fork-direct)、名前が `-sockdir` で終わる経路) だけがそれを開き、開けなければその経路は使えない (他の OS の `O_RDONLY` は読み取り権限の無いディレクトリを開けない)
- どの経路も、呼び出し元のプロセスの cwd も呼び出し元のスレッドの cwd も変えない
- ディレクトリの開き方 (置き場、ソケットのディレクトリ): Apple の OS は `O_SEARCH` (カーネルが `EISDIR` / `EINVAL` を返したら `O_RDONLY`)、Linux は `O_PATH | O_DIRECTORY`、他は `O_RDONLY | O_DIRECTORY`

### 経路の名前

経路は次の名前で呼ぶ。表は試す順。名前が bind と connect の両方に出るものは同じ経路で、違いは各経路の節に書く。失うものの名前は「[失うもの](#失うもの)」。

bind:

| 名前 | 中身 | OS | 失うもの |
|---|---|---|---|
| [standard](#standard) | 標準にそのまま渡す | 全部 | 相対パスなら `cwd-relative` |
| [thread-cwd](#thread-cwd) | 使い捨てのスレッドの cwd を D に移し、`R/<ファイル名>` | Linux / Android / Apple の OS | `respelled` |
| [at](#at) | `bindat(Dfd, R/<ファイル名>)` | FreeBSD | `respelled` |
| [proc](#proc) | `/proc/self/fd/<Dfd>/R/<ファイル名>` | `/proc` を使える Linux / Android | `respelled` |
| [fork](#fork) | fork した子が `fchdir(Dfd)` して `R/<ファイル名>` | 全部 | `respelled`<br>`forked` |
| [thread-cwd-sockdir](#thread-cwd-sockdir) | thread-cwd を D 無しの形で (R はソケットのディレクトリの中、`.sockat.XXXXXXXXXX/<ファイル名>`) | Linux / Android / Apple の OS | `respelled` |
| [at-sockdir](#at-sockdir) | at を D 無しの形で | FreeBSD | `respelled` |
| [proc-sockdir](#proc-sockdir) | proc を D 無しの形で | `/proc` を使える Linux / Android | `respelled` |
| [fork-sockdir](#fork-sockdir) | fork を D 無しの形で | 全部 | `respelled`<br>`forked` |
| [symlink](#symlink) | 置き場にソケットのディレクトリを指す symlink を作り、`<置き場>/sockat.XXXXXXXXXX/<ファイル名>` (`bind_any` だけ) | 全部 | 持ち主だけが書ける置き場: `respelled`<br>共有の置き場: `respelled` と `recreatable-spelling` |

- `-sockdir` の 4 つは、D をどこにも作れない時だけ同じ順で試す ([D 無しの形](#d-無しの形))
- symlink は `bind_any` だけが、既定の bind が `ENAMETOOLONG` になる所で試す

connect:

| 名前 | 中身 | OS | 失うもの |
|---|---|---|---|
| [standard](#standard) | 標準にそのまま渡す | 全部 | 無し |
| [thread-cwd](#thread-cwd) | 使い捨てのスレッドの cwd を D に移し、`R/<ファイル名>` | Linux / Android / Apple の OS | 無し |
| [at](#at) | `connectat(Dfd, R/<ファイル名>)` | FreeBSD | 無し |
| [proc](#proc) | `/proc/self/fd/<Dfd>/R/<ファイル名>` | `/proc` を使える Linux / Android | 無し |
| [proc-direct](#proc-direct) | R を通さない `/proc/self/fd/<fd>/<ファイル名>` (予備) | `/proc` を使える Linux / Android | 無し |
| [proc-held](#proc-held) | D の中にソケットのファイルを指す `s` を置き、`/proc/self/fd/<Dfd>/s` (予備) | `/proc` を使える Linux / Android | 無し |
| [relative](#relative) | cwd からの相対パス (予備) | `/proc` を使えない Linux / Android<br>Apple の OS<br>NetBSD / OpenBSD / illumos / その他の Unix | 無し |
| [widened](#widened) | 広げた sockaddr (予備) | Apple の OS | 無し |
| [symlink](#symlink) | 置き場の symlink (予備) | FreeBSD 以外 | 無し |
| [at-direct](#at-direct) | `connectat(<ソケットのディレクトリの fd>, <ファイル名>)` (予備) | FreeBSD | 無し |
| [fork-direct](#fork-direct) | fork した子がファイル名で connect (`connect_any` 系だけ) | 全部 | `forked` |

- 予備の経路を OS ごとにどの順で試すかは「[予備の経路 (connect 系)](#予備の経路-connect-系)」

### 失うもの

経路を通ったことで、標準と比べて何を失うか。any 系の `losses` はこの名前の並びで返す (何も失っていなければ空)。

| 名前 | 失うもの | 付く時 |
|---|---|---|
| `respelled` | カーネルが返すアドレスが元のパスでない (「[長いパスで標準と違う点](#長いパスで標準と違う点)」)。標準が listener を閉じる時に消す言語 (Go の標準等) でも消えず、元のパスのファイルは自分で消す (`_ex` の `discard()` 等)。綴りの中の乱数の名前 (R) は消してあるので普段は何にも当たらないが、綴りは他の利用者に見えうる (Linux の `/proc/net/unix`) ので、プロセスの cwd が他人も書ける場所 (`/tmp` 等) だと、相手が見て作り直した後にその綴りで unlink すると、相手の選んだディレクトリの同じ名前のファイルを消しうる。元のパスで消せば当たらない | bind が標準以外の経路を通った |
| `cwd-relative` | カーネルが覚えた綴りが cwd からの相対パス (渡したパスがそのまま標準に渡った)。cwd を変えた後にその綴りで unlink / stat すると別の場所に当たる。sockat が経路で失わせたものでなく標準が元から持つ危険だが、知らせる。元のパスを絶対パスにして消せば当たらない | 相対パスで bind が [standard](#standard) を通った |
| `forked` | fork の副作用 (「[fork の副作用](#fork-の副作用)」) | [fork](#fork)・[fork-sockdir](#fork-sockdir)・[fork-direct](#fork-direct) を通った |
| `recreatable-spelling` | カーネルが返す綴りが共有の置き場 (`/tmp` 等) を通る。名前は乱数なので事前には当てられないが、bind の後は他の利用者に見えうる (Linux の `/proc/net/unix`)。他の利用者がそれを作り直した後にその綴りで unlink すると、相手の選んだディレクトリの同じ名前のファイルを消しうる。元のパス (`discard()` 等) で消せば当たらない。名前の長さは防御でない (名前は bind の後に見える) | `bind_any` が共有の置き場の [symlink](#symlink) を通った |

- 名前は約束で、変えずに足すだけ。知らない名前は「何かを失った」とだけ読む
- 名前の間に大小や包含の関係は無い (`forked` と `recreatable-spelling` は互いを含まない)
- connect の綴りは相手に残らない (「[試す順番](#試す順番)」) ので、connect で付くのは `forked` だけ
- 持ち主だけが書ける置き場の symlink は `respelled` だけ

### 試す順番

| 順 | bind | `connect` / `connect_nonblocking` | `connect_any` 系 |
|---|---|---|---|
| 1 | [standard](#standard) (標準に渡す長さ以下) | 同じ | 同じ |
| 2 | [thread-cwd](#thread-cwd) (FreeBSD は [at](#at)) | 同左 | 同左 |
| 3 | [proc](#proc) | 同左 | 同左 |
| 4 | [fork](#fork) | 予備の経路 | 予備の経路 |
| 5 | `ENAMETOOLONG` | `ENAMETOOLONG` | [fork-direct](#fork-direct) |

- bind の fork は、thread-cwd・proc がスレッド cwd / `/proc` を使えない、または proc の綴りに収まらない時に試す。D をどこにも作れない時は、2〜4 を D 無しの形で試す ([thread-cwd-sockdir](#thread-cwd-sockdir) (FreeBSD は [at-sockdir](#at-sockdir)) → [proc-sockdir](#proc-sockdir) → [fork-sockdir](#fork-sockdir))。綴りが sockaddr に入らない時は試さず `ENAMETOOLONG`
- bind は [proc-direct](#proc-direct)・[relative](#relative)・[widened](#widened)・置き場の [symlink](#symlink) を使わない (綴りが後で無関係なファイルに当たるか、アドレスが途中で切れて読む側を壊すか、D を通す経路で足りる)。`bind_any` だけは、何かを失ってでも届かせるため、最後に [symlink](#symlink) を試す ([DR-0013](decisions/DR-0013-any-means-reach-at-any-cost.md))
- connect の綴りは相手に残らない (connect した側のソケットは bind されない) ので、予備の経路は綴りにランダムな部品を挟まない
- thread-cwd と proc は副作用が無い (peer の pid は呼び出し元のまま、fd の複製も無く、他のスレッドの cwd は変わらない)。そのため `connect` / `connect_nonblocking` も試す

### 経路

数字はバイト。

#### standard

- やり方: 標準にそのまま渡す (「[短いパス](#短いパス)」)
- 使える条件: パスが標準に渡す長さ以下
- 使えない時: パスが標準に渡す長さを超える
- 届く長さ: パス全体が標準に渡す長さ以下
- 失うもの: bind は相対パスなら `cwd-relative`、他は無し。connect は無し
- 失うもの以外は bind と connect で同じ

#### thread-cwd

- やり方: D と R を作り ([D と R](#d-と-r))、[使い捨てのスレッド](#使い捨てのスレッド)の cwd を D に移して `R/<ファイル名>` で bind / connect する。Linux / Android は `unshare(CLONE_FS)` → `fchdir(Dfd)`、Apple の OS は `pthread_fchdir_np(Dfd)`
- 使える条件: Linux / Android / Apple の OS
- 使えない時:
  - Linux / Android: seccomp の filter が掛かっているか確かめられない (`prctl(PR_GET_SECCOMP)` が 0 以外か失敗)、`unshare` が断られた
  - Apple の OS: `pthread_fchdir_np` が無い・失敗した
  - スレッドを作れない・固定できない
  - D をどこにも作れない ([D の置き場](#d-の置き場))、綴りが sockaddr に入らない
- 届くファイル名: sockaddr に入る長さ − 11 (Linux / Android 96、Apple の OS 92)
- 失うもの: bind は `respelled`、connect は無し
- 失うもの以外は bind と connect で同じ

#### at

- やり方: D と R を作り ([D と R](#d-と-r))、スレッドを使わず、bind は `bindat(Dfd, ...)`、connect は `connectat(Dfd, ...)` に `R/<ファイル名>` を渡す
- 使える条件: FreeBSD
- 使えない時: D をどこにも作れない ([D の置き場](#d-の置き場))、綴りが sockaddr に入らない
- 届くファイル名: 92
- 失うもの: bind は `respelled`、connect は無し

#### proc

- やり方: D と R を作り ([D と R](#d-と-r))、スレッドを使わず `/proc/self/fd/<Dfd>/R/<ファイル名>` で bind / connect する
- 使える条件: `/proc` を使える Linux / Android
- 使えない時: `/proc/self/fd/<Dfd>` を引けない、綴りが sockaddr に入らない、D をどこにも作れない ([D の置き場](#d-の置き場))
- 届くファイル名: およそ 79 (fd の桁で変わる)
- 失うもの: bind は `respelled`、connect は無し
- 綴りの長さは D の fd の番号で変わり、開くまで分からない。D を作る前は見積もりで確かめ、開いた後に確かめ直す (収まらなければ D を片付けて次へ)
- `/proc` を使えるかの確認に、ソケットのディレクトリの fd は要らない (`/` か D の fd で確かめる)
- 綴りも R を通すので、後で fd の番号が使い回されても無関係なファイルに当たらない
- 失うもの以外は bind と connect で同じ

#### fork

- やり方: D と R を作り ([D と R](#d-と-r))、fork した子が `fchdir(Dfd)` して `R/<ファイル名>` で bind する ([fork の子](#fork-の子))
- 使える条件: bind だけ。前の経路が使えない時に試す (「[試す順番](#試す順番)」)
- 使えない時: D をどこにも作れない ([D の置き場](#d-の置き場))。綴りが sockaddr に入らない時は次へ進まず `ENAMETOOLONG`
- 届くファイル名: sockaddr に入る長さ − 11 (Linux / illumos 96、Apple の OS / BSD 92)
- 失うもの: `respelled` と `forked`
- connect は D を通す fork を使わない (`connect_any` 系は [fork-direct](#fork-direct))

#### thread-cwd-sockdir

- やり方: [thread-cwd](#thread-cwd) と同じ手段で、D の代わりにソケットのディレクトリに移り、`.sockat.XXXXXXXXXX/<ファイル名>` で bind する ([D 無しの形](#d-無しの形))
- 使える条件: bind だけ。D をどこにも作れない。OS は thread-cwd と同じ
- 使えない時: thread-cwd の「使えない時」のうち D によらないもの、綴りが sockaddr に入らない
- 届くファイル名: sockaddr に入る長さ − 19 (Linux / Android 88、Apple の OS 84)
- 失うもの: `respelled`

#### at-sockdir

- やり方: [at](#at) と同じく、`bindat(<ソケットのディレクトリの fd>, ...)` に `.sockat.XXXXXXXXXX/<ファイル名>` を渡す ([D 無しの形](#d-無しの形))
- 使える条件: bind だけ。FreeBSD。D をどこにも作れない
- 使えない時: 綴りが sockaddr に入らない
- 届くファイル名: 84
- 失うもの: `respelled`

#### proc-sockdir

- やり方: [proc](#proc) と同じく、`/proc/self/fd/<ソケットのディレクトリの fd>/.sockat.XXXXXXXXXX/<ファイル名>` で bind する ([D 無しの形](#d-無しの形))
- 使える条件: bind だけ。`/proc` を使える Linux / Android。D をどこにも作れない
- 使えない時: `/proc/self/fd/<fd>` を引けない、綴りが sockaddr に入らない
- 届くファイル名: およそ 72 (fd の桁で変わる)
- 失うもの: `respelled`

#### fork-sockdir

- やり方: fork した子が `fchdir(<ソケットのディレクトリの fd>)` して `.sockat.XXXXXXXXXX/<ファイル名>` で bind する ([D 無しの形](#d-無しの形)、[fork の子](#fork-の子))
- 使える条件: bind だけ。D をどこにも作れず、前の経路が使えない時に試す ([D 無しの形](#d-無しの形))
- 使えない時: 綴りが sockaddr に入らない時は `ENAMETOOLONG`
- 届くファイル名: sockaddr に入る長さ − 19 (Linux / illumos 88、Apple の OS / BSD 84)
- 失うもの: `respelled` と `forked`

#### proc-direct

- やり方: ソケットのディレクトリを開き、`/proc/self/fd/<fd>/<ファイル名>` で connect する
- 使える条件: connect 系の予備。`/proc` を使える Linux / Android
- 使えない時: ソケットのディレクトリを開けない、`/proc/self/fd/<fd>` を stat で引けない、綴りが sockaddr に入らない
- 届くファイル名: およそ 90 (fd の桁で変わる)
- 失うもの: 無し
- bind は使わない (「[試す順番](#試す順番)」)

#### proc-held

- やり方: D を作り ([D と R](#d-と-r) の手順 1・2・5)、その中に `symlinkat` でソケットのファイルを指す `s` を作り、`/proc/self/fd/<Dfd>/s` で connect する。`s` は自分が作れた時だけ消す
- 使える条件: connect 系の予備。`/proc` を使える Linux / Android
- 使えない時: D か `s` を作れない
- 届くファイル名: 綴りにファイル名が出ないので、ファイル名によらない
- 失うもの: 無し

#### relative

- やり方: cwd からの相対パスで connect する。文字列を書き直すだけで `chdir` しない ([相対パスの作り方](#相対パスの作り方))
- 使える条件: connect 系の予備。元のパスが絶対パス
- 使えない時: 相対パスが sockaddr に入る長さを超える、作った綴りのディレクトリが元と `(st_dev, st_ino)` で一致しない、cwd が既に変わっている
- 届く長さ: 相対パスが sockaddr に入る長さ以内 (Linux / Android / illumos 107、Apple の OS / BSD 103)
- 失うもの: 無し
- bind は使わない (「[試す順番](#試す順番)」)

#### widened

- やり方: `sun_len` とアドレス長を `2 + パスの長さ` にした sockaddr で、元のパス、無理なら相対パスを渡して connect する
- 使える条件: connect 系の予備。Apple の OS。パスが 253 バイト以内
- 使えない時: カーネルが `EINVAL` / `ENAMETOOLONG` を返した
- 届く長さ: 元のパスか相対パスが 253 以内
- 失うもの: 無し
- bind は使わない (「[試す順番](#試す順番)」)

#### symlink

- bind のやり方: `bind_any` だけ。置き場にソケットのディレクトリの realpath を指す symlink を作り、`<置き場>/sockat.XXXXXXXXXX/<ファイル名>` で bind して、すぐ消す ([symlink の置き場と名前](#symlink-の置き場と名前))
- bind の使える条件: 既定の bind の経路が全部使えない (`ENAMETOOLONG` になる所)
- bind の使えない時: どの候補も、綴りが sockaddr に入らない・置き場の条件に合わない・symlink を作れない。この時は `ENAMETOOLONG`
- bind で届くファイル名: sockaddr に入る長さ − (置き場の綴りの長さ + 19)
- bind で失うもの: 持ち主だけが書ける置き場なら `respelled` (綴りを作り直せるのは自分だけ)、共有の置き場なら `respelled` と `recreatable-spelling` (他の利用者が綴りを作り直せ、上のライブラリや利用者が綴りで unlink すると、相手の選んだディレクトリの同じ名前のファイルを消させうる)
- connect のやり方: 安全な置き場にソケットのファイルを指す symlink を作り、`<置き場>/sockat.XXXXXXXXXX` で connect して、すぐ消す ([symlink の置き場と名前](#symlink-の置き場と名前))
- connect の使える条件: connect 系の予備。FreeBSD 以外
- connect の使えない時: どの候補も、綴りが sockaddr に入らない・置き場が安全でない・symlink を作れない
- connect で届くファイル名: 綴りにファイル名が出ないので、ファイル名によらない (綴り `<置き場>/sockat.XXXXXXXXXX` が sockaddr に入る長さ以内)
- connect で失うもの: 無し (connect の綴りは相手に残らない)

#### at-direct

- やり方: ソケットのディレクトリを開き、`connectat(fd, <ファイル名>)` で connect する。D を通さない
- 使える条件: connect 系の予備。FreeBSD
- 使えない時: ソケットのディレクトリを開けない、ファイル名が 103 バイトを超える
- 届くファイル名: 103
- 失うもの: 無し

#### fork-direct

- やり方: fork した子が `fchdir(<ソケットのディレクトリの fd>)` してファイル名で connect する ([fork の子](#fork-の子))。D を通さない。Apple の OS は、カーネルが受け付ければ広げた sockaddr を使う
- 使える条件: `connect_any` 系だけ。他の経路が全部使えない
- 使えない時: 綴りが sockaddr (Apple の OS は広げた sockaddr) に入らない時は `ENAMETOOLONG`
- 届くファイル名: Linux / Android / illumos 107、Apple の OS 253、BSD 103
- 失うもの: `forked`
- `connect` / `connect_nonblocking` はここに来た所で `ENAMETOOLONG`

### D と R

D を通す経路 ([thread-cwd](#thread-cwd)・[at](#at)・[proc](#proc)・[fork](#fork)) が使う。[proc-held](#proc-held) は手順 1・2・5 を使う。

1. 置き場 ([D の置き場](#d-の置き場)) を開いて fd で掴み、その中に `mkdirat` で mode 0700 の D を作る。名前は `sockat.` (ソケットのディレクトリでは `.sockat.`) + 英数 62 種から 10 文字 (OS の安全な乱数)。`EEXIST` で引き直し、16 回で打ち切る
2. D を開く (Linux は `O_PATH | O_DIRECTORY | O_NOFOLLOW`、Apple の OS は `O_SEARCH | O_DIRECTORY | O_NOFOLLOW` (カーネルが `EISDIR` / `EINVAL` を返したら `O_RDONLY`)、他の OS は `O_RDONLY | O_DIRECTORY | O_NOFOLLOW`。`O_PATH` と `O_SEARCH` は umask が持ち主の読み取りを削っても開ける)。`fstat` で「ディレクトリ・持ち主が実効 uid・group と other に権限が無い」を確かめ、0700 にそろえる
   - `O_PATH` の fd: `/proc` を使えれば `chmod("/proc/self/fd/<fd>", 0700)`。使えなければ D を名前で `O_RDONLY | O_DIRECTORY | O_NOFOLLOW` で開き直し、`(st_dev, st_ino)` が最初の fd と同じことを確かめて `fchmod` (`O_PATH` の fd に `fchmod` は `EBADF`)
   - 他の fd: `fchmod`
   - 確認が通った後に開き直せない・そろえられない時は「作れない」とし、手順 5 で D を片付ける
3. D の中に R を作る: `symlinkat(<ソケットのディレクトリの realpath>, Dfd, R)`。R の名前は英数 62 種から 10 文字 (`sockat.` を付けない)。`EEXIST` で引き直し、16 回で打ち切る
4. D の fd を基準に `R/<ファイル名>` で bind / connect する (手段は各経路の節)
5. 片付け: R は自分が作れた時だけ `unlinkat(Dfd, R)`。D は手順 2 の確認が通り、`fstatat(置き場の fd, D の名前, AT_SYMLINK_NOFOLLOW)` の `(st_dev, st_ino)` が fd と一致する時だけ `unlinkat(置き場の fd, D の名前, AT_REMOVEDIR)`。fd を閉じる。成功でも失敗でもする。消す失敗は無視する

- 綴り `R/<ファイル名>` は 11 バイト + ファイル名
- R を乱数の名前にするのは事故を防ぐため (後で綴りが解決された時に、cwd 等にたまたまある同じ名前の物に当たらない)。他の利用者への防御ではない (綴りは他の利用者に見えうる。「[失うもの](#失うもの)」の `respelled`)
- 片付けた後は R がどこにも無いので、カーネルが返す綴りを後でプロセスの cwd 等の別の文脈で解決しても、無関係なファイルに当たらない
- 確認に落ちた D は他人の物とみなし、中身も含めて触らない
- 作った直後の D を開けない時 (umask が持ち主の権限を削った時。`O_SEARCH` / `O_RDONLY` で開く OS) は、`fstatat(置き場の fd, D の名前, AT_SYMLINK_NOFOLLOW)` が手順 2 と同じ条件 (ディレクトリ・持ち主が実効 uid・group と other に権限が無い) なら `unlinkat(置き場の fd, D の名前, AT_REMOVEDIR)` で消し、「作れない」として次の置き場へ。名前で確かめてから消すまでにすり替えられても、`AT_REMOVEDIR` は空のディレクトリしか消さない ([DR-0012](decisions/DR-0012-own-directory-and-thread-cwd.md))
- 長さと、手段を使えるか (確かめられる所まで) は D を作る前に確かめる。使えなければ何も作らずに次へ
- 呼び出し元がソケットを作り、D の fd を持つ。ブロックしない connect ではその前にソケットを非ブロッキングにする。bind の後の listen は呼び出し元がする

### D の置き場

| 順 | 置き場 | 条件 |
|---|---|---|
| 1 | `${TMPDIR:-/tmp}` | 相対パスも可 (一度開いて fd で掴む) |
| 2 | `/tmp` | 1 で作れない時だけ。1 と同じ綴りなら飛ばす |
| 3 | ソケットのディレクトリ | 2 でも作れない時だけ。名前は `.sockat.XXXXXXXXXX` (利用者のディレクトリなので、残っても sockat の物と分かり目立たない)。bind ではここに書けるはず。connect では書けるとは限らない |

- 「作れない」は、置き場を開けない、D を作れない、名前を使い切った、乱数が取れない、[D と R](#d-と-r) の手順 2 の確認が通らない、R を作れない
- どこにも作れない時、bind は [D 無しの形](#d-無しの形)に進む
- どこにも作れない時、connect 系は予備の経路に進む ([予備の経路 (connect 系)](#予備の経路-connect-系))
- 置き場の安全 (sticky 等) と長さは問わない。D を fd で掴み、綴りに置き場が出ない

### D 無しの形

D をどこにも作れない時の bind が使う。[thread-cwd-sockdir](#thread-cwd-sockdir)・[at-sockdir](#at-sockdir)・[proc-sockdir](#proc-sockdir)・[fork-sockdir](#fork-sockdir) がこの形。

- ソケットのディレクトリに R (名前は `.sockat.XXXXXXXXXX`、ソケットのディレクトリの realpath を指す) を作り、D の fd の代わりにソケットのディレクトリの fd を基準にして、`.sockat.XXXXXXXXXX/<ファイル名>` で bind する
- 手段は D と同じ順 (thread-cwd-sockdir (FreeBSD は at-sockdir) → proc-sockdir → fork-sockdir)
- 綴りは 19 バイト + ファイル名
- 片付け: R は自分が作れた時だけ `unlinkat(<ソケットのディレクトリの fd>, R)`。成功でも失敗でもする。消す失敗は無視する ([D と R](#d-と-r) の手順 5 と同じ)
- ソケットのディレクトリを開けない、R も作れない時は `ENAMETOOLONG`

### 使い捨てのスレッド

[thread-cwd](#thread-cwd) と [thread-cwd-sockdir](#thread-cwd-sockdir) が使う。

- 呼び出し元は使い捨てのスレッドが終わるまで待ってから R と D を片付け、fd を閉じる。待つのが割り込まれても (Python の `KeyboardInterrupt` 等)、スレッドが終わるまでは片付けない (先に閉じた fd の番号が使い回されると、スレッドが無関係なディレクトリに移って bind する)
- スレッドは sockat が作った使い捨てで、使い終わったら捨てる。呼び出し元のスレッドの cwd には触らない (`pthread_fchdir_np(-1)` で戻すと、呼び出し元がスレッドに付けた cwd を消しうる)
- Linux で seccomp の filter が掛かっている時は `unshare` を呼ばない。filter がプロセスの kill (SIGSYS) で断る環境 (systemd の `SystemCallFilter=` の既定) がある
- `unshare` の後の `fchdir` の失敗 (`EACCES` 等) は本当の失敗として返す
- `pthread_fchdir_np` は libSystem の非公開 API (`__pthread_fchdir` syscall)。実行時に引く

### fork の子

[fork](#fork)・[fork-sockdir](#fork-sockdir)・[fork-direct](#fork-direct) が使う。子が `fchdir` する fd と綴りは各経路の節。

1. 親がソケットを作り、fd を持ち、sockaddr を組み立ててから fork する。ブロックしない connect では fork の前にソケットを非ブロッキングにする
2. 子は `fchdir(fd)` → 綴りで `bind` / `connect` → `_exit(結果)` (0 が成功、1〜255 が errno)
3. 親はその pid だけを `waitpid` し、それから R と D を片付ける。bind の後の listen は必ず親がする ([DR-0010](decisions/DR-0010-fork-bind-listen-by-parent.md))

- 子の区間は async-signal-safe な呼び出しだけ (allocation・lock・言語の後始末を通さない)
- `waitpid` が `ECHILD` (status を他者に刈り取られた) なら、ソケットの状態から結果を読む: bind は `getsockname` にパスが入っているか、connect は `getpeername` が通るか。失敗は一般のエラー

### 予備の経路 (connect 系)

D を通す経路が使えない時 (手段が無い、D を作れない、綴りが収まらない) に試す。

| OS | 試す順番 |
|---|---|
| Linux / Android (`/proc` を使える) | [proc-direct](#proc-direct) → [proc-held](#proc-held) → [symlink](#symlink) |
| Linux / Android (`/proc` を使えない) | [relative](#relative) → [symlink](#symlink) |
| macOS / iOS 等 Apple の OS | [relative](#relative) → [widened](#widened) → [symlink](#symlink) |
| FreeBSD | [at-direct](#at-direct) |
| NetBSD / OpenBSD / illumos / その他の Unix | [relative](#relative) → [symlink](#symlink) |

- proc-held の `s` と symlink の先は、ソケットのファイルの綴りそのもの (相対パスなら cwd を前に付ける)

### 相対パスの作り方

[relative](#relative) が使う。

1. パスが cwd の綴り (`getcwd`、または `stat` の `(st_dev, st_ino)` が `.` と一致する `$PWD`) で始まれば、区切り単位でそれを削る
2. 1 で sockaddr に入る長さ以内にならない時だけ、ソケットのディレクトリと cwd を `realpath` で実パスにし、`..` で上る綴りを作る
3. 短い方を使う。使う前に相対パスのディレクトリと元のディレクトリの `(st_dev, st_ino)` が同じこと、cwd の `(st_dev, st_ino)` が 1 の前と同じことを確かめる。違えばこの経路は使えない
4. connect の後に cwd の `(st_dev, st_ino)` が変わっていたら、結果を捨てて一般のエラーを返す

### symlink の置き場と名前

[symlink](#symlink) が使う。

| 項目 | 仕様 |
|---|---|
| 置き場の候補 | connect: `TMPDIR` (空でない絶対パスの時)、`/tmp` の順<br>bind (`bind_any`): `XDG_RUNTIME_DIR` (空でない絶対パスの時)、`TMPDIR` (同)、`/tmp` の順<br>同じ綴りの候補は 1 回だけ |
| 持ち主だけが書ける置き場 | symlink を辿って stat し、ディレクトリで、持ち主が実効 uid で、`mode & 0o022 == 0` |
| 共有の置き場 | symlink を辿って stat し、ディレクトリで、sticky bit が立ち、持ち主が root か実効 uid |
| 安全な置き場 | 持ち主だけが書ける置き場か、共有の置き場。connect はこのどちらかの候補を順に使う |
| bind の試し方 | 候補のうち持ち主だけが書ける置き場を順に試し、無ければ共有の置き場を順に試す |
| symlink の先 | connect: ソケットのファイル<br>bind: ソケットのディレクトリの realpath |
| 名前 | `sockat.` + 英数 62 種から 10 文字。OS の安全な乱数から取る |
| 衝突 | `EEXIST` で名前を引き直す。16 回で打ち切り、その候補は使えないとみなす |
| 片付け | bind / connect が成功しても失敗しても消す。消す失敗は無視する |

- 候補ごとに、何かを作る前に綴りの長さと置き場の安全を確かめる。収まらない・安全でない・作れない候補には何も作らず次へ進む

## 経路の失敗の扱い

- 経路が実際に bind / connect して失敗したら (`ENOENT`、`EADDRINUSE`、`ECONNREFUSED` 等)、そのエラーを返し、次の経路も次の置き場も試さない
- 次へ進むのは、経路自体が使えない時だけ (各経路の節の「使えない時」)
  - 綴りが収まらない
  - D の置き場で D か R を作れない (次の置き場へ)
  - thread-cwd・at・proc とその `-sockdir` の手段が使えない
  - `/proc` を使えない
  - proc-held で D か `s` を作れない
  - widened でカーネルが広げた sockaddr を受け付けない
  - symlink で置き場が安全でない・symlink を作れない
  - relative で、作った綴りのディレクトリが元と `(st_dev, st_ino)` で一致しない、または cwd が既に変わっている
- ディレクトリが無い時はどの OS でも `ENOENT`。ディレクトリを先に引くので、長さの判定より前に決まる
- `connect` / `connect_nonblocking` は [fork-direct](#fork-direct) の手前で `ENAMETOOLONG` を返す

## どこから届かなくなるか

標準に渡す長さを超えるパスが `ENAMETOOLONG` になる時 (ディレクトリがあり、D を作れる前提。数字はバイト)。

| OS | `bind` | `connect` 系 | `connect_any` 系 |
|---|---|---|---|
| Linux / Android (`/proc` あり) | ファイル名 > 96 | 届く ([proc-held](#proc-held)) | 届く |
| Linux / Android (`/proc` 無し) | ファイル名 > 96 | [thread-cwd](#thread-cwd) が使えず (ファイル名 > 96 かスレッド cwd が使えない)、[relative](#relative) > 107、[symlink](#symlink) も使えない | ファイル名 > 107、symlink も使えない |
| FreeBSD | ファイル名 > 92 | ファイル名 > 103 | ファイル名 > 103 |
| macOS / iOS 等 Apple の OS | ファイル名 > 92 | [thread-cwd](#thread-cwd) が使えず (ファイル名 > 92 かスレッド cwd が使えない)、元のパスも相対パスも > 253、symlink も使えない | ファイル名 > 253、symlink も使えない |
| NetBSD / OpenBSD / その他の BSD | ファイル名 > 92 | relative > 103、symlink も使えない | ファイル名 > 103、symlink も使えない |
| illumos | ファイル名 > 96 | relative > 107、symlink も使えない | ファイル名 > 107、symlink も使えない |

- Linux で thread-cwd が使えない時、bind はファイル名およそ 79 バイトまで [proc](#proc)、その先 96 までは [fork](#fork)
- D をどこにも作れない時、bind は `-sockdir` の経路でファイル名 88 (Apple の OS / BSD 84、[proc-sockdir](#proc-sockdir) だけならおよそ 72) まで届く (ソケットのディレクトリに R を作れる時)。connect 系は予備の経路の分だけ届く (proc-held は使えない)
- `bind_any` は、bind の列で `ENAMETOOLONG` になる所でも、[symlink](#symlink) の綴り (`<置き場>/sockat.XXXXXXXXXX/<ファイル名>`) が sockaddr に入れば届く
- ディレクトリを引く等でフルパスを渡すので、PATH_MAX (macOS 1024、Linux 4096) を超えるパスは `ENAMETOOLONG`。sockat の責務外

## fork の副作用

| 範囲 | 副作用 |
|---|---|
| 相手から見える (`connect_any` 系だけ) | サーバに見える peer の pid は終了した子の pid。uid / gid は呼び出し元と同じ<br>Linux の `SO_PEERCRED` は子の pid のまま<br>macOS の `LOCAL_PEERPID` は呼び出し元が send すると呼び出し元の pid になる |
| 相手から見えない (`bind` と `connect_any` 系) | 子は終了まで全 fd の複製を持つ。その間に他のスレッドが閉じたソケットやパイプは開いたままになる<br>親に `SIGCHLD` が届く<br>`pthread_atfork` の handler が走る<br>監視ツールに短命の子が見える<br>他のスレッドの `waitpid(-1)` が子を刈り取りうる |

- bind は相手から見える副作用が無い。子は bind だけして listen は親がするので、クライアントに見えるサーバの peer 情報 (macOS の `LOCAL_PEERPID` / `LOCAL_PEEREPID` / audit token の pid と pidversion、Linux の `SO_PEERCRED` / `SO_PEERPIDFD`) は send の前から親 (実測 2026-11-18、macOS 26.5.2 と Linux) ([DR-0010](decisions/DR-0010-fork-bind-listen-by-parent.md))

## 長いパスで標準と違う点

| 点 | 内容 |
|---|---|
| カーネルが返すアドレス | bind した側の `getsockname` と、そこへ connect した側の `getpeername` は `R/<ファイル名>` ([proc](#proc) は `/proc/self/fd/<fd>/R/<ファイル名>`) を返す。R はもう無いので、後で解決しても普段は何にも当たらない (プロセスの cwd が他人も書ける場所だと、他の利用者が綴りを見て作り直せる。「[失うもの](#失うもの)」の `respelled`)。`bind_any` の [symlink](#symlink) は `<置き場>/sockat.XXXXXXXXXX/<ファイル名>` を返し、共有の置き場では他の利用者がそれを作り直せる。標準の型でアドレスを返す口を差し替えられる言語 (Python) は元のパスを返す (Python の asyncio は listener の `getsockname` の綴りを `stat` / unlink する)。差し替えられない言語は元のパスを呼び出し元が持つ |
| ディレクトリを先に引く | R を使う経路 (D を通す経路と D 無しの形) は R を作る時にソケットのディレクトリを realpath で引く。[proc-direct](#proc-direct)・[relative](#relative)・[at-direct](#at-direct)・[fork-direct](#fork-direct) はディレクトリを引いてからファイル名で渡す。その間の rename や symlink の張り替えは反映されない。[widened](#widened) と [symlink](#symlink) は標準と同じ |
| 他のスレッドの chdir | relative は、間に cwd が変わったままなら一般のエラー。変えて戻した場合は見えない |
| 他人も書けるソケットのディレクトリ | sticky でなく他人も書けるソケットのディレクトリでは、D 無しの形の R を作ってから bind するまでの間に R を差し替えられ、別のディレクトリに bind しうる (そこに同じ名前が既にあれば `EADDRINUSE` で、上書きはしない)。D の中の R は D が 0700 なので差し替えられない |
| 残骸 | D・R・置き場の symlink を消す前にプロセスが死ぬと、`sockat.XXXXXXXXXX` が置き場に、`.sockat.XXXXXXXXXX` (D か D 無しの形の R) がソケットのディレクトリに残る |

- 先頭以外の NUL は短いパスでも引数の誤り。標準が NUL で黙って切り詰める言語 (Go 等) では、README の「標準と違う点」に書く

## エラー

| 状況 | エラー |
|---|---|
| ディレクトリが無い / connect 先が無い | `ENOENT` |
| ディレクトリの位置にディレクトリでない物がある | `ENOTDIR` |
| bind 先に既にファイルがある | `EADDRINUSE` |
| 誰も listen していないソケットファイル | `ECONNREFUSED` |
| backlog が満杯 | Linux はブロックしない connect で `EAGAIN` (ブロックする connect は待つ)、macOS は `ECONNREFUSED` |
| どの経路にも収まらない。`connect` 系では fork-direct でしか届かない時も | `ENAMETOOLONG` |
| 標準に渡す長さを超えるパスで、名前で終わらない | 引数の誤り |
| 先頭以外に NUL を含むパス (長さによらない) | 引数の誤り |
| relative の途中で cwd が変わった | 一般のエラー |
| fork した子が正常に終了しなかった。または status を刈り取られ、bind / connect されていなかった | 一般のエラー |

- OS のエラーは、その言語の作法で errno を取り出せる形で返す
- 「引数の誤り」「一般のエラー」をどの型で表すかは各実装が決める

## 各実装に求めること

- 上の経路と順番に従う。その言語で作れない経路は飛ばし (使えない経路として次へ進む)、README に OS × 経路の表で明示する
- 自前で作ったソケットを標準の型に取り込む言語では、widened で connect したソケットを取り込んでも、取り込みやアドレスの取得で落ちないか確かめる。落ちるなら widened を作れない経路として飛ばす
- 経路は公開 API に出さない。試験はパッケージの中から各経路を直接呼んで強制する
- 環境を読む部分 (D の置き場、symlink の置き場の候補、`/proc/self/fd` の場所、Apple の OS で広げた sockaddr を受け付けるか、スレッド cwd を使えるか) は試験から差し替えられるようにする
- README とマニュアルにこの仕様へのリンクを置く。仕様と食い違う振る舞いを入れる時は、先にこの仕様を直す

## 実装が確かめる試験の観点

| 観点 | 確かめること |
|---|---|
| 短いパスの境界 | 標準に渡す長さちょうどは標準にそのまま渡り、1 バイト長いと経路に回る (標準自身で境界を確かめる) |
| D を通す経路 | 強制して、プロセスの cwd も呼び出し元のスレッドの cwd も変わらない、ソケットが元のパスにでき送受信できる、peer の pid が呼び出し元、片付けの後に置き場に何も残らない |
| 返る綴り | bind した後、返る綴り (`getsockname`) をそのまま unlink / stat しても無関係なファイル (cwd の同名ファイル、fd の番号を使い回させた別のディレクトリの同名ファイル) に当たらない |
| 差し替えたディレクトリ | D を作ってから開くまでに差し替えたディレクトリ (持ち主が違うか group / other に権限が付いた) を使わず、その中身も消さない |
| D の置き場 | `TMPDIR` に作れない時は `/tmp`、それも作れない時はソケットのディレクトリに `.sockat.` の名前で作る。相対パスや深い `TMPDIR` でも使える。どこにも作れない時、bind は D 無しの形 (thread-cwd-sockdir → proc-sockdir → fork-sockdir の順)、connect 系は予備の経路 |
| 手段が使えない時 | thread-cwd を使えなくして、`/proc` を使える Linux は proc に進む。それも使えない時、bind は fork (peer は親)、connect 系は予備の経路に進む |
| 予備の経路 | 各経路を強制して、ソケットに届き、置き場に何も残らない。symlink は安全でない置き場を飛ばす、深すぎる `TMPDIR` で `/tmp` に回る、名前の衝突を飛ばし 16 回で打ち切る |
| 失敗をやり直さない | `ENOENT` / `EADDRINUSE` / `ECONNREFUSED` を返し、後の経路・置き場に何も作らない |
| connect と fork | `connect` 系は fork-direct でしか届かない時に `ENAMETOOLONG`、`connect_any` 系は届いて `losses` が `forked` だけ |
| `bind_any` | 既定の bind が `ENAMETOOLONG` になる所で symlink を通って届く。持ち主だけが書ける置き場があればそこを使って `losses` が `respelled` だけ、共有の置き場しか無ければ `losses` が `respelled` と `recreatable-spelling`。置き場に何も残らない。既定の経路で届く所では `losses` がその経路のもの |
| 開けない D | umask が持ち主の権限を削って作った直後の D を開けない時、置き場に何も残らない |
| relative と cwd | relative の途中で cwd が変わったら一般のエラー |
| fork | fork・fork-sockdir で bind したサーバに connect したクライアントから見える peer が親 (send の前も後も)。fork-direct の peer の pid の振る舞い、`SIGCHLD` を `SIG_IGN` にした時の結果の読み取り |
| macOS | connect 系で 253 バイトのパスが widened で通る。bind は widened を使わない |
| ブロックしない connect | backlog が満杯で待たずに失敗する |
| 名前で終わらないパス、先頭以外の NUL | 何も作らずに引数の誤り。NUL は短いパスでも。先頭が NUL (abstract) は標準に渡る |
| カーネルが返すアドレス | 長いパスでも取得で落ちない。差し替えられる言語では、listener・accept したソケット・connect したソケットの各口が元のパスを返し、その言語の代表的な上のライブラリ (Python の asyncio の `start_unix_server(sock=...)` 等) が引数を足さずに短いパスと同じに動く |
| `_ex` | `discard()` でファイルが消え、listener は閉じない。間に別のファイルに置き換えられていたら消さない |

- 経路は OS で違うので、少なくとも macOS と Linux で回す。他の Unix は CI の VM で回す
- cwd やシグナルの扱いのようにプロセス全体に効く設定を変える試験は、子プロセスの中で行う
- fork の経路の子は全 fd の複製を一瞬持つので、「誰も listen していないソケット」は別プロセスで作る

## 未確定

- Android と macOS 以外の Apple の OS は全体が未確認
- NetBSD・OpenBSD・illumos は peer の資格情報が未確認
- ブロックしない connect が `EINPROGRESS` を返さないことは Linux と macOS でだけ確認済み
