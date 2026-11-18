# sockat 仕様

> [English](./SPEC.md) | 日本語

言語によらない sockat の振る舞い。各言語の実装はこれに従う。設計の判断と却下した案は [sockat-rs の DR-0001](https://github.com/kawaz/sockat-rs/blob/main/docs/decisions/DR-0001-long-socket-path-routes.md)、Rust 固有の話 (型、`unsafe` の置き場、tokio) は [sockat-rs の MANUAL](https://github.com/kawaz/sockat-rs/blob/main/docs/MANUAL-ja.md) にある。

## 用語

| 用語 | 意味 |
|---|---|
| 標準 | その言語の標準ライブラリの Unix domain socket の bind / connect |
| 上限 | `sun_path` の長さ − 1 バイト (NUL の分を除く) |
| ディレクトリ / ファイル名 | パスの最後の要素の前と、最後の要素 |
| 綴り | カーネルに渡すパスの文字列。同じ場所を指す別の綴りを作るのが経路 |

## 対象

- pathname 型の Unix domain socket の bind (と listen) / connect
- Unix 系の OS。Windows は対象外

## 公開する操作

| 操作 | fork の経路 | ブロック | 戻り値 |
|---|---|---|---|
| `bind` | 最後に試す | (待たない) | listen 済みの listener |
| `connect` | 試さない | する | stream |
| `connect_nonblocking` | 試さない | しない | 非ブロッキングの stream |
| `connect_any` | 最後に試す | する | stream と、fork の経路を通ったか (bool) |
| `connect_any_nonblocking` | 最後に試す | しない | stream と、fork の経路を通ったか (bool) |

- 戻り値の listener / stream は、標準の bind / connect が返すのと同じ型。標準の代わりに置き換えるだけで使える
- 名前はその言語の命名の慣習に合わせてよい。振る舞いは上の表に従う
- fork の経路を作れない言語では `connect_any` 系を出さない。README の表に「fork の経路なし」と書く
- 標準の connect が元から待たない言語 (Node.js 等) では、標準と同じ形の connect を 1 つだけ出し、`_nonblocking` を分けない
- `connect` / `connect_nonblocking` は fork の経路に来た所で `ENAMETOOLONG` を返す
- `connect_any` 系は、他の経路が全部使えない時に fork してでも connect する。fork の経路を通った時だけ `true`。pid は返さない
- ブロックしない 2 つは、connect の前にソケットを非ブロッキングにし、そのまま返す。相手の backlog が満杯なら待たずに失敗する
- 自前で作るソケットは、その言語の標準が作るソケットと同じ設定にする (close-on-exec、`SO_NOSIGPIPE`、listen の backlog 等)
- ソケットファイルは listener を閉じても消さない (標準と同じ)

## 短いパス

その言語の標準が受け付ける長さまでは、標準にそのまま渡す。何も足さず、環境変数も読まない。それを超えたら経路に回す。多くの言語の標準は次の長さ (`sun_path` − 1) まで受け付ける。これより短い言語 (Java は `sun_path` − 2) は、その言語の標準の上限を使う。

| OS | `sun_path` − 1 |
|---|---|
| Linux / Android / illumos | 107 バイト |
| macOS / iOS / FreeBSD / NetBSD / OpenBSD | 103 バイト |

## 長いパスの経路と試す順番

上限を超えるパスは、OS ごとに次の順で試し、最初に使えた経路で bind / connect する。

| OS | 試す順番 |
|---|---|
| Linux / Android (`/proc` を使える) | /proc |
| Linux / Android (`/proc` を使えない) | 相対パス → symlink → fork |
| FreeBSD | bindat |
| macOS | 相対パス → 広げた sockaddr → symlink → fork |
| NetBSD / OpenBSD / illumos / その他の Unix | 相対パス → symlink → fork |

- 上限を超えるパスで、最後がファイル名でないもの (`dir/`、`dir/.`、`dir/..`、`..`) は、何も作らずに引数の誤りを返す
- どの経路も呼び出し元のプロセスの cwd を変えない

### 各経路

| 経路 | やり方 | 使える条件 |
|---|---|---|
| /proc | ディレクトリを `O_PATH \| O_DIRECTORY` で開き、`/proc/self/fd/<fd>/<ファイル名>` を標準に渡す | `/proc/self/fd/<fd>` を stat で引け、綴り全体が上限以内 (ファイル名はおよそ 90 バイトまで) |
| bindat | ディレクトリを `O_RDONLY` で開き、`bindat(2)` / `connectat(2)` でファイル名を渡す | FreeBSD。ファイル名が 103 バイトを超えたら `ENAMETOOLONG` |
| 相対パス | cwd からの相対パスを標準に渡す。文字列を書き直すだけで `chdir` しない | 元のパスが絶対パスで、相対パスが上限以内 |
| 広げた sockaddr | `sun_len` とアドレス長を `2 + パスの長さ` にした sockaddr で、元のパス、無理なら相対パスを渡す | macOS。パスが 253 バイト以内。カーネルが `EINVAL` / `ENAMETOOLONG` を返したら使えないとみなす |
| symlink | 置き場に短い symlink を作り、それを通した綴りを渡して、すぐ消す | 綴りが上限 (macOS は 253) 以内で、安全で symlink を作れる置き場がある |
| fork | ディレクトリの fd に `fchdir` した子を fork し、子がファイル名で bind / connect する | `bind` と `connect_any` 系だけ。ファイル名が上限 (macOS は 253) 以内 |

### 相対パスの作り方

1. パスが cwd の綴り (`getcwd`、または `stat` の `(st_dev, st_ino)` が `.` と一致する `$PWD`) で始まれば、区切り単位でそれを削る
2. 1 で上限以内にならない時だけ、ソケットのディレクトリと cwd を `realpath` で実パスにし、`..` で上る綴りを作る
3. 短い方を使う。使う前に相対パスのディレクトリと元のディレクトリの `(st_dev, st_ino)` が同じことを確かめる
4. bind / connect の後に cwd の `(st_dev, st_ino)` が変わっていたら、結果を捨てて一般のエラーを返す (できたかもしれないソケットファイルは消さない)

### symlink の置き場と名前

| 項目 | 仕様 |
|---|---|
| 置き場の候補 | `TMPDIR` (空でない絶対パスの時)、`/tmp` の順。`TMPDIR` が `/tmp` と同じ綴りなら 1 回だけ |
| 安全な置き場 | symlink を辿って stat し、次のどちらか<br>sticky bit が立ち、持ち主が root か実効 uid<br>持ち主が実効 uid で、`mode & 0o022 == 0` |
| 名前 | `sockat.` + 英数 62 種から 10 文字。OS の安全な乱数から取る |
| 衝突 | `symlink(2)` の `EEXIST` で名前を引き直す。16 回で打ち切り、その候補は使えないとみなす |
| bind の symlink | ソケットのディレクトリを指す。綴りは `<置き場>/sockat.XXXXXXXXXX/<ファイル名>` |
| connect の symlink | ソケットのファイル (元のパス) を指す。綴りは `<置き場>/sockat.XXXXXXXXXX` |
| symlink の先 | 利用者のパスの綴りそのもの (bind はそのディレクトリ部分。相対パスなら cwd を前に付ける) |
| 片付け | bind / connect が成功しても失敗しても消す。消す失敗は無視する |

- 候補ごとに、何かを作る前に綴りの長さと置き場の安全を確かめる。満たさない候補には何も作らず次へ進む
- symlink を作れない時 (置き場が無い・書けない、名前を使い切った、乱数が取れない) も次の候補へ進む

### fork の経路

1. 親がソケットを作り、ディレクトリを開いた fd を持ち、sockaddr を組み立ててから fork する。ブロックしない connect では fork の前にソケットを非ブロッキングにする
2. 子は `fchdir(dirfd)` → ファイル名で `bind` / `connect` → `_exit(結果)` (0 が成功、1〜255 が errno)
3. 親はその pid だけを `waitpid` する。bind の後の listen は親がする

- 子の区間は async-signal-safe な呼び出しだけ (allocation・lock・言語の後始末を通さない)
- `waitpid` が `ECHILD` (status を他者に刈り取られた) なら、ソケットの状態から結果を読む: bind は `getsockname` にパスが入っているか、connect は `getpeername` が通るか。失敗は一般のエラー
- ディレクトリの開き方: macOS は `O_SEARCH` (カーネルが `EISDIR` / `EINVAL` を返したら `O_RDONLY`)、Linux は /proc の経路で開いた `O_PATH` の fd、他は `O_RDONLY`

## 経路の失敗の扱い

- 経路が実際に bind / connect して失敗したら (`ENOENT`、`EADDRINUSE`、`ECONNREFUSED` 等)、そのエラーを返し、次の経路も次の置き場も試さない
- 次へ進むのは、経路自体が使えない時だけ (長さが足りない、`/proc` を使えない、カーネルが広げた sockaddr を受け付けない、置き場が安全でない・symlink を作れない)
- `connect` / `connect_nonblocking` はディレクトリを開いてから fork の手前で `ENAMETOOLONG` を返す。ディレクトリが無ければ `ENOENT`

## どこから届かなくなるか

上限を超えるパスが `ENAMETOOLONG` になる時 (数字はバイト)。

| OS | `bind` | `connect` 系 | `connect_any` 系 |
|---|---|---|---|
| Linux (`/proc` あり) | ファイル名 > 107 | ファイル名が `/proc` の綴りに収まらず、相対パス > 107、symlink も使えない | ファイル名 > 107、symlink も使えない |
| Linux (`/proc` 無し) | ファイル名 > 107 | 相対パス > 107、symlink も使えない | ファイル名 > 107、symlink も使えない |
| FreeBSD | ファイル名 > 103 | ファイル名 > 103 | ファイル名 > 103 |
| macOS | ファイル名 > 253 | 元のパスも相対パスも > 253、symlink も使えない | ファイル名 > 253、symlink も使えない |
| NetBSD / OpenBSD / その他の BSD | ファイル名 > 103 | 相対パス > 103、symlink も使えない | ファイル名 > 103、symlink も使えない |
| illumos | ファイル名 > 107 | 相対パス > 107、symlink も使えない | ファイル名 > 107、symlink も使えない |

- `/tmp` で symlink の経路を使えれば、connect はディレクトリの深さにもファイル名の長さにもよらず届く
- `/tmp` を通した bind はファイル名が 84 バイト (`sun_path` が 104 の OS は 80、macOS は 230) まで

## fork の副作用

| 副作用 | 内容 |
|---|---|
| peer の pid | fork の経路で connect すると、サーバに見える peer の pid は終了した子の pid。uid / gid は呼び出し元と同じ<br>Linux の `SO_PEERCRED` は子の pid のまま<br>macOS の `LOCAL_PEERPID` は呼び出し元が send すると呼び出し元の pid になる |
| fd の複製 | 子は終了まで全 fd の複製を持つ。その間に他のスレッドが閉じたソケットやパイプは開いたままになる |

bind は子が bind するだけで listen は親なので、相手から見える副作用は無い。

## 長いパスで標準と違う点

| 点 | 内容 |
|---|---|
| カーネルが返すアドレス | `getsockname` / `getpeername` は bind に使った綴りを返す (相対パス、`/proc/self/fd/...`、もう無い symlink、ファイル名だけ、途中で切れたパス)。元のパスは呼び出し元が持つ |
| ディレクトリを先に引く | /proc・相対パス・bindat・fork は、ディレクトリを引いてからファイル名で渡す。その間の rename や symlink の張り替えは反映されない。広げた sockaddr と symlink は標準と同じ |
| 他のスレッドの chdir | 相対パスの経路は、間に cwd が変わったままなら一般のエラー。変えて戻した場合は見えない |
| symlink の残骸 | symlink を消す前にプロセスが死ぬと `sockat.XXXXXXXXXX` が置き場に残る |

## エラー

| 状況 | エラー |
|---|---|
| ディレクトリが無い / connect 先が無い | `ENOENT` |
| bind 先に既にファイルがある | `EADDRINUSE` |
| 誰も listen していないソケットファイル | `ECONNREFUSED` |
| backlog が満杯 | Linux はブロックしない connect で `EAGAIN` (ブロックする connect は待つ)、macOS は `ECONNREFUSED` |
| どの経路にも収まらない。`connect` 系では fork の経路でしか届かない時も | `ENAMETOOLONG` |
| 上限を超えるパスで、名前で終わらない | 引数の誤り |
| NUL を含むパス | 引数の誤り |
| 相対パスの経路の途中で cwd が変わった | 一般のエラー |
| fork した子が正常に終了しなかった。または status を刈り取られ、bind / connect されていなかった | 一般のエラー |

- OS のエラーは、その言語の作法で errno を取り出せる形で返す
- 「引数の誤り」「一般のエラー」をどの型で表すかは各実装が決める

## 各実装に求めること

- 上の経路と順番に従う。その言語で作れない経路は飛ばし (使えない経路として次へ進む)、README に OS × 経路の表で明示する
- 経路は公開 API に出さない。試験はパッケージの中から各経路を直接呼んで強制する
- 環境を読む部分 (symlink の置き場の候補、`/proc/self/fd` の場所、macOS で広げた sockaddr を受け付けるか) は試験から差し替えられるようにする
- README とマニュアルにこの仕様へのリンクを置く。仕様と食い違う振る舞いを入れる時は、先にこの仕様を直す

## 実装が確かめる試験の観点

| 観点 | 確かめること |
|---|---|
| 短いパスの境界 | 上限ちょうどは標準にそのまま渡り、1 バイト長いと経路に回る (標準自身で境界を確かめる) |
| 場所 | 各経路で、ソケットファイルが元のパスにでき、置き場に何も残らない |
| 送受信 | 各経路で bind した listener と connect した stream で実際に送受信できる |
| 標準の型 | 戻り値が標準の型として使える (非同期ランタイムに渡せる言語では渡して使う) |
| 失敗をやり直さない | `ENOENT` / `EADDRINUSE` / `ECONNREFUSED` を返し、後の経路・置き場に何も作らない (後の候補のディレクトリの mtime が変わらない) |
| /proc が無い Linux | `/proc/self/fd` の場所を空のディレクトリ等に差し替えて、相対パス → symlink → fork に進む |
| symlink の置き場 | 安全でない置き場を飛ばす、深すぎる `TMPDIR` で `/tmp` に回る、名前の衝突を飛ばし 16 回で打ち切る、成功でも失敗でも symlink を消す |
| connect と fork | `connect` 系は fork でしか届かない時に `ENAMETOOLONG`、`connect_any` 系は届いて `true` |
| cwd | どの経路の後も cwd が変わっていない。相対パスの経路の途中で cwd が変わったら一般のエラー |
| fork | peer の pid の振る舞い、`SIGCHLD` を `SIG_IGN` にした時の結果の読み取り |
| macOS | 253 バイトのパスが広げた sockaddr で通る |
| ブロックしない connect | backlog が満杯で待たずに失敗する |
| 名前で終わらないパス、NUL | 何も作らずに引数の誤り |
| カーネルが返すアドレス | 長いパスでも取得で落ちない |

- 経路は OS で違うので、少なくとも macOS と Linux で回す。他の Unix は CI の VM で回す
- cwd やシグナルの扱いのようにプロセス全体に効く設定を変える試験は、子プロセスの中で行う
- fork の経路の子は全 fd の複製を一瞬持つので、「誰も listen していないソケット」は別プロセスで作る

## 未確定

- Android、macOS 以外の Apple OS、NetBSD・OpenBSD・illumos の peer の資格情報は確かめていない
