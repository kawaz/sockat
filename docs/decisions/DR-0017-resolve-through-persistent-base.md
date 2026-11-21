# DR-0017: 長いパスは、置き場 B の中の消さない symlink を通る短い綴りに resolve して bind / connect する。既定の bind も綴りを残し、fork はしない

- Status: Active
- Date: 2026-11-21

## Context

- カーネルは bind に渡された綴りを覚えて `getsockname` / `getpeername` で返し、上のライブラリや利用者はその綴りで unlink / stat する (Python の asyncio の後始末、Go の `UnixListener.Close`、利用者の `remove_file(local_addr)` 等)。DGRAM の受け手は送り元の綴りへ返信する
- 綴りは後で別の文脈で解決され直し、無関係なファイルに当たりうる

| bind の綴り | 後で解決すると |
|---|---|
| `/proc/self/fd/<n>/<ファイル名>` | 閉じた fd の番号が使い回され、別のディレクトリの同名ファイルに当たる (sockat-rs が docker で実測、無関係なファイルを消した) |
| ファイル名だけ (スレッド cwd / fork / bindat) | プロセスの cwd の同名ファイルに当たる (sockat-py が macOS で実測) |
| cwd からの相対パス | cwd が変わると別の場所に当たる |

- Apple の OS で広げた sockaddr で bind したソケットのアドレスは途中で切れ、読む側を壊す (CPython の `getsockname` が後ろに無関係なバイトを付けて asyncio の後始末が落ちる。Go の `net.FileConn` で相手の `RemoteAddr` が nil になり `.String()` が panic する)
- 綴りを呼び出しの中で片付けると、後で無関係なファイルには当たらないが、`getsockname` の綴りで消す上のライブラリ、DGRAM の返信 ([research](../research/2026-11-19-datagram-and-seqpacket.md) の実測で、長いパスに bind した送り元には返信が届かない)、運用の道具が元のパスに届かない
- fork の経路は副作用 (fd の複製、`SIGCHLD`、`waitpid(-1)`、`pthread_atfork`、connect では相手に見える pid) がプロセス全体に及ぶ
- 操作ごとに重視することが違う (kawaz 2026-11-20)

| 操作 | 使われ方の見込み | 重視すること |
|---|---|---|
| bind | 息が長く、大量には作らない | 速さ以外 (綴りの寿命、残るもの、安全) |
| connect | CLI や制御の問い合わせで、必要な時に都度行う | 手数・速さ・IO の回数・負荷。同じパスへの綴りを作り直さず再利用できること |

- 利用者 2 者 (sockat-rs 0.4.1 を使う llm-gateway・hyoui) の回答 ([issue](../issue/2026-11-20-resolve-and-persistent-base.md) の「利用者の回答」)
  - 使うのは STREAM の `bind`・`connect`・`connect_nonblocking` だけで、fork をやめても困らない
  - connect する側は短命で数が多く、書ける置き場が無いことがある。書き込みもスレッドも要らない経路を先に、を保ってほしい
  - 気になる点: 既定の `bind` が消さない物を作ると片付けの手がかりが無い、exec をまたぐと残る、並行する試験での競合と残骸、状態がアプリの置き場の外に増える、`connect_nonblocking` が待たないこと
- OS の一時ディレクトリの掃除 ([research](../research/2026-11-20-tmp-cleaners-and-persistent-base.md))

| 置き場 | 掃除 |
|---|---|
| Linux の `/tmp` | systemd-tmpfiles が 10 日の age で配下ごと消す。flock の掛かったディレクトリは配下ごと飛ばす (v242 以上) |
| `/run/user/<uid>` (`$XDG_RUNTIME_DIR`) | age の掃除は無い。最終ログアウトと再起動で消える |
| macOS の `/tmp` | 通常のファイルと空のディレクトリだけを消す。symlink の入ったディレクトリは消えない |
| macOS の `$TMPDIR` | dirhelper が 3 日で消しうる (種類ごとの扱いは未確認) |
| FreeBSD・NetBSD・OpenBSD・illumos | 既定は消えないか、再起動で消える。日次の掃除は symlink を消さない |

- 実測 (2026-11-19〜20、docker の Linux と macOS。issue の「実測」)

| 確かめたこと | 結果 |
|---|---|
| 開いて fd を持ったディレクトリを rmdir し、`/proc/<pid>/fd/<fd>/D` を mkdir | `ENOENT` (消したディレクトリの中には作れない) |
| 中に E のあるディレクトリを rmdir / unlink | `ENOTEMPTY` / `EISDIR`。rename はでき、rename 後も B に作れる |
| `/proc/<pid>/fd/<fd>/D/E/s.sock` (E → ソケットのディレクトリ) に bind | 通る。`getsockname` はその綴り、実体は元のパス |
| その綴りに別のプロセスが connect | 同じ uid: 届く。別の uid: `EACCES` |
| その綴りで unlink | 元のパスの実体が消える |
| macOS の `$TMPDIR` (`/var/folders/.../T/`) の権限 | `drwx------` (別の uid は辿れない) |
| 0700 の親の中の 0711 のディレクトリに別の uid が cd | できない。親も 0711 にするとできる |
| bind が最後の要素の symlink を辿るか | 辿るのは macOS と NetBSD だけ。Linux・FreeBSD・OpenBSD・illumos は辿らない ([findings](../findings/2026-11-19-bind-through-file-symlink.md)) |

## Decision

### 記号

| 記号 | 中身 |
|---|---|
| B | 置き場の中に作る実在のディレクトリ。利用者ごとで、プロセスをまたいで使い回す |
| D | B の中に (プロセス, B) ごとに 1 つ作るディレクトリ |
| E | symlink。ソケットのディレクトリを指す物 (link-dir と thread-cwd・at) とソケットのファイルを指す物 (link-file) がある。resolve の E は D の中に作り `cleanup` まで残す。thread-cwd・at の E と既定の connect の E は呼び出しの中で作ってすぐ消す |

### resolve

- resolve は、長いパスを、元のパスと同じ所を指し続ける短い綴りに言い換えて返す。綴りが生きている間は、`getsockname` の綴りで消す上のライブラリ、DGRAM の返信、運用の道具が元のパスと同じに働く
- 綴りはただのパスなので、ソケットの型 (stream / DGRAM / SEQPACKET) と操作 (bind / connect / `send_to`) を問わず、利用者が std に渡して使える
- 標準に渡す長さ以下のパスはそのまま返す (絶対パスは `Original`、相対パスは `CwdRelative`)
- 綴りは `B/D/E/<ファイル名>` (link-dir) か `B/D/E` (link-file)
- resolve は用途で 2 つに分ける (`resolve_for_bind` / `resolve_for_connect`)。bind は `link-file` を Linux 等で使えず `link-dir` を先に選び、connect は `link-file` を選ぶ (ファイル名の長さによらない)
- `resolve_for_bind` の `link-file` は、bind が symlink を辿ると実測した OS (macOS・NetBSD) だけで使う。未確認の OS では `link-dir` だけ (resolve の時点では bind しないので、辿るかを見分けられない)。既定の `bind` と `bind_ex` は実行時に見分ける (「link-file と、bind が symlink を辿る OS」)
- `resolve_for_connect` は、標準に渡す長さ以下ならそのまま、長ければ `link-file` (B の綴りは procB か実パス) の綴りを返す。B を作れない等で `link-file` を使えなければ `ENAMETOOLONG` (その時も既定の `connect` を使えば、書き込みの要らない経路と thread-cwd-direct を試せる)
- resolve は path を返すだけなので、thread-cwd・at でしか届かない長さでは `ENAMETOOLONG`。それも届かせたい人は `bind` / `connect` を使う
- 既定の `bind` は内部で resolve を使い、resolve で済まない長さには thread-cwd・at で届かせる。既定の `connect` は D を作らない (「既定の bind は綴りを残し、既定の connect は残さない」)
- 消す (`remove`) と片付ける (`cleanup` は E を片付ける。B と D は sockat が片付けない) は自動で行わない。どれも 1 回だけ働き、2 回目以降は何もしない (`remove` は resolve した綴りの物を 1 回だけ消す、の意味の冪等)
- resolve のたびに B の中を一覧しない (resolve の手数を増やさない)

### B・D・E

| | B | D | E |
|---|---|---|---|
| 作る単位 | 利用者ごと。プロセスをまたいで使い回す。1 つのプロセスが使う置き場 1〜3 の B は 1 つ (`usable_cross_uid` の時だけ、もう 1 つ使いうる)。置き場 4 (ソケットのディレクトリ) の B はディレクトリごと。`Options.base` の B は指定ごと。綴りが収まらないと先に分かる時は作らない | (プロセス, B) ごとに 1 つ。作るのは、綴りを残す bind (thread-cwd・at を含む) と `resolve_for_connect` だけ | resolve ごと。thread-cwd・at と既定の connect の link-file は呼び出しごと |
| 置く所 | 「実体の置き場」の順で最初に作れた所か、利用者が `Options.base` で指定した所 | B の中 | D の中。既定の connect の link-file は B の直下 |
| 名前 | `sockat-<uid>` (`$XDG_RUNTIME_DIR` の下は `sockat`、ソケットのディレクトリの下は `.sockat.<乱数 10 文字>`)。使う前に、実ディレクトリ・持ち主が自分・他人が書けない、を確かめ、外れたら `sockat-<uid>.<乱数 10 文字>` (指定された所なら外れたらエラー) | 乱数 10 文字 (カウンタにしない。プロセスが終わった後に同じ PID・同じ fd 番号の別のプロセスが現れても綴りが同じにならないため) | resolve の E はプロセスの中のカウンタ (36 進。D が (プロセス, B) ごとに一意なので短くてよい)。thread-cwd・at の E と B の直下の E は乱数 10 文字 |
| mode | 作る B は 0711。既にある B は、持ち主が自分で他人が書けなければ 0711 でなくても使い、mode を変えない | 0711 (`/tmp` の B の綴りを別の uid が辿れるように) | 無し (symlink の mode は辿る権限に効かない) |
| 中身 | D (と、既定の connect の link-file の E) | E | ソケットのディレクトリを指す symlink (link-dir、綴り `B/D/E/<ファイル名>`) か、ソケットのファイルを指す symlink (link-file、綴り `B/D/E`) |
| 生きている間 | 消さない | プロセスが flock (共有ロック) を掛けた fd を持ち続ける。systemd-tmpfiles (v242 以上) はロックの掛かったディレクトリを配下ごと掃除しない | resolve の E は消さない |
| 片付け | sockat はしない (利用者が指定した B はアプリが管理) | sockat はしない。死んだプロセスの D は OS の一時ディレクトリの掃除で消える (Linux の `/tmp` は 10 日。macOS の `/tmp` は symlink の入ったディレクトリを消さないので再起動まで残る)。明示の `sweep()` を呼んだ時だけ、ロックの外れた D を消す | resolve の E は `cleanup`。呼び出しごとの E は呼び出しの中で unlink |

- systemd v242 より古い環境 (RHEL 8 の v239 等) では、生きている D も 10 日で消されうる。綴りが辿れなくなるだけで危険はない (説明に書く)
- link-dir の E と thread-cwd・at の E は、ソケットのディレクトリの realpath を指す
- 乱数は英数 62 種の文字で、OS の安全な乱数から作る。名前の作り方は 3 言語でそろえる

### D の作り方

1. B の fd を基準に、乱数の名前で `mkdirat(B の fd, 名前, 0700)` する。`EEXIST` なら名前を引き直し、16 回で打ち切る
2. 作った直後に `fchmodat(B の fd, 名前, 0711)` で mode をそろえ (umask で削られた分を戻す。B は確かめ済みで他人は付け替えられない。Linux の `O_PATH` の fd には `fchmod` できないため名前で行う)、それから `O_DIRECTORY | O_NOFOLLOW` で開いて `fstat` で確かめる。そろえられない・開けない時は、作った自分の空のディレクトリを消し、その呼び出しでは D を使う経路を使えないとする (別の B は探さない。B の作り方の 4 は次の置き場へ)
3. その fd に flock (共有ロック) を掛けて持ち続ける。fd は close-on-exec
4. 名前で `lstat` した `(st_dev, st_ino)` が fd と同じかを確かめる。違えば (1 と 3 の間に他のプロセスの `sweep()` が消した) fd を閉じて 1 から作り直す

### `sweep`

- B の中の D に `flock(LOCK_EX | LOCK_NB)` が取れたら、持ち主が死んだとみなして消す
- `sweep()` の対象は、置き場 1〜3 の既定の名前の B (`sockat-<uid>`・`sockat`)。あるものだけで、B を作らない
- `sweep` に base を渡す形 (Rust は `sweep_base(path)`、名前は各言語の慣習) は、`Options.base` の B の中の死んだ D を消す。その B を管理するアプリが呼ぶ
- 乱数の名前の B (`sockat-<uid>.<乱数>`) とソケットのディレクトリの B は対象にしない。この 2 つは OS の掃除でも消えないことがある (ソケットのディレクトリの B は利用者のディレクトリに残る)。SPEC の「置き場に残る物」に書き、各言語の README にも書く
- B の直下の E (既定の connect の物) には触らない。symlink でない物がある D は残す
- 対象にするのは、B の直下の、名前が D の形 (英数字 62 種の 10 文字) のディレクトリだけ。B (`Options.base` の B も) は sockat 専用で、利用者は他の物を置かない (統括)

### B の作り方

自動の置き場も `Options.base` も同じ (kawaz と合意 2026-11-21)。

1. 置き場のパス (`Options.base` は親のパス) を realpath で実パスにする (macOS の `/tmp` → `/private/tmp` 等)。以後の確かめ・開く・綴るは、この実パスで行う
2. ルートから親までの途中を全部確かめる: どれも、持ち主が root か自分で、かつ他人が書けないか sticky が立っている (sticky でも持ち主は中の物を付け替えられるので、持ち主の条件は外さない。OpenSSH の StrictModes と同じ考え。祖先が他人に書けると親ごと付け替えられる)。プロセスで最初の 1 回だけ
3. 親を `O_DIRECTORY | O_NOFOLLOW` で開いて fd で掴み、`mkdirat(親の fd, 名前, 0700)` で作る
4. 作った直後に `fchmodat(親の fd, 名前, 0711)` で mode をそろえ、それから `O_DIRECTORY | O_NOFOLLOW` で開いて `fstat` で実ディレクトリ・持ち主が自分を確かめる。そろえられない・開けない時は、作った自分の空のディレクトリを消して次の置き場へ (`Options.base` はエラー)
5. `EEXIST` なら、既にある物を同じく確かめる (実ディレクトリ・持ち主が自分・他人が書けない)。mode が 0711 でなくても使い、mode を変えない。外れたら、自動の置き場は `sockat-<uid>.<乱数 10 文字>` に落とし、`Options.base` はエラー

- 「他人が書けない」は group も含む (`mode & 022 == 0`)
- 途中のディレクトリが無い時、sockat は作らずにエラー (アプリの管理する場所の作り方はアプリが決める)
- `Options.base` のエラーの種類: 相対パスの時と、最後がファイル名でない時 (`dir/`・`..`・`/`) は引数の誤り、途中のディレクトリが無い時は `ENOENT`、base がディレクトリでない時は `ENOTDIR`、持ち主・権限の確かめに外れた時は `EPERM`

### 実体の置き場

B の実体をどこに作るかと、B をどう綴るかは別の軸。B はプロセスごとに、利用者が指定しなければ次の順で最初に作れた所の 1 つ (OS の掃除で死んだ D が消え、生きている D が守られる所を先に)。

| 順 | 置き場 | 理由 |
|---|---|---|
| 1 | `/tmp` | Linux は死んだ D を 10 日で消し、生きている D は flock で守られる。macOS は生きている D を消さない |
| 2 | `$XDG_RUNTIME_DIR` | age の掃除が無く、死んだ D はログアウトまで残る |
| 3 | `$TMPDIR` | macOS の `$TMPDIR` は dirhelper が 3 日で消しうる (生きている D も) |
| 4 | ソケットのディレクトリ (名前は `.sockat.XXXXXXXXXX`) | 1〜3 のどこにも作れない時 |

- `$TMPDIR`・`$XDG_RUNTIME_DIR` が空か相対パスの時は、その置き場を使わない
- 1 つのプロセスが使う B が 1 つなのは置き場 1〜3 のこと。4 (ソケットのディレクトリ) の B はソケットのディレクトリごと
- 綴りが収まらないと先に分かる時 (置き場の実パスの長さから見積もれる時) は、B を作らない
- 既定の connect が link-file で B を初めて作った時も、その B (と fd) をプロセスの B として以後も使う (D は作らない)
- `Options.base` を指定した時は、その所に B を作る。sockat は中にプロセスごとの D を作るだけで、B の掃除はアプリに任せる。確かめて外れたらエラーで、自動の置き場に落とさない
- `Options.base` は B そのもののパス。呼び出しごとに違う `base` を渡せば、1 つのプロセスが複数の B を持ち、D は (プロセス, B) ごと
- `Options.base` と `usable_cross_uid` を一緒に指定した時は、その base までの途中と base 自身が全部 other に x を持つかを確かめ、外れたらエラー (自動の置き場に落とさない)
- `Options.base` は connect 系 (`connect_ex`、`resolve_for_connect`) でも B の置き場として使う
- `usable_cross_uid` の時の B の選び方は「別の uid と PrivateTmp」

### 綴りの形

sockat が自分で判断する。上から順に、収まる物。

| 綴り | 形 | 使う時 | 診断の `base` | 他のプロセスが辿れるか |
|---|---|---|---|---|
| procB | `/proc/<pid>/fd/<B の fd>/D/…` | `/proc` を使えて収まる時 (`usable_cross_uid` の時は使わない) | `proc` (B がソケットのディレクトリの時は `sockdir`、`Options.base` の B の時は `given`) | 同じ uid・同じ PID 名前空間だけ (root は辿れる)。プロセスが終われば辿れない |
| 実パス | B の実パス `…/B/D/…` | 収まる時 | B の置き場 (`tmp` / `runtime` / `tmpdir`。`Options.base` の B の時は `given`) | B までの途中が全部 other に x を持てば別の uid も (`/tmp` の B)、そうでなければ同じ uid だけ (`/run/user/<uid>` と macOS の `$TMPDIR` は 0700) |

- procB は実体の置き場がどこでも同じ形
- `/proc` を使えるかは、`/proc/<pid>/fd/<B の fd>` を stat した `(st_dev, st_ino)` が、B の fd の `fstat` と同じ時だけ使えるとする (PID 名前空間と `/proc` の mount の食い違いに備える)
- 診断の `base` は、B が一時の置き場 (`/tmp`・`$XDG_RUNTIME_DIR`・`$TMPDIR`) の時は綴りの形 (procB は `proc`、実パスは置き場の名前) を、一時の置き場でない B (ソケットのディレクトリ・`Options.base`) の時は綴りの形によらずその B (`sockdir`・`given`) を表す。一時の置き場の procB は置き場によらず同じ綴りなので `proc` にまとめ、一時の置き場でない B は利用者のディレクトリやアプリの指定の場所に物ができたことを知らせる。綴りが procB か実パスかは `Spelling` の `until` で分かる
- B をソケットのディレクトリに作った時は、実パスの綴りは元のパスより長くなるので、使えるのは procB の綴りだけ。`/proc` の無い OS では resolve の綴りを使えず、thread-cwd / at へ
- どの綴りも収まらなければ thread-cwd / at へ

| 綴り | 綴りで消せるか | 片付け |
|---|---|---|
| `B/D/E/<ファイル名>` (link-dir) | 消せる (途中の E を辿る) | `cleanup` |
| `B/D/E` (link-file) | 消せない (最後の symlink は辿られず E が消える)。`remove` が要る | `cleanup` |

| B の綴り | プロセスが終わった後 |
|---|---|
| procB | 辿れない |
| 実パス | E は `cleanup` まで、D はプロセスが終わった後の OS の掃除まで残る。B が `/tmp` にある時は、B が消えた後に他人が同じ名前で作り直しうる (std の元のパスを消した後に、そのディレクトリに書ける人が作り直せるのと同じ。片付けた後の綴りは使わない、と説明に書く) |

### 別の uid と PrivateTmp

- 利用者が `Options.usable_cross_uid` で「別の uid にも辿らせる」と指定した時は、実体の置き場の順のうち、B までの途中のディレクトリと B 自身が全部 other に x (辿る権限) を持つ所だけを B に使い (既にある B が 0700 なら満たさない) (その中で最初に作れた所)、procB の綴りは使わない (子が 0711 でも親が 0700 なら別の uid は辿れない。実測)
  - `/tmp` (1777) はいつも当たる
  - `$XDG_RUNTIME_DIR` (`/run/user/<uid>`) と macOS の `$TMPDIR` は 0700 なので外れる。`$TMPDIR` を辿れる場所に向けた環境なら当たる
- 当たる所が無いか、その B の綴りが収まらなければ、満たさない綴りに落とさず thread-cwd / at (`Dangling`) に進む。満たせたかは結果の `Spelling` で分かる。その D は、`usable_cross_uid` を見ない普段の B (置き場 1〜4 の順) に作る
- connect 系 (既定の connect、`connect_ex`、`resolve_for_connect`) は `usable_cross_uid` を見ない (connect の綴りは相手に残らない)
- この B が普段の B と違う所になる時は、もう 1 つの B として使う (自動の置き場で 1 つのプロセスが複数の B を使うのはこの時だけ)
- 相手の `/tmp` が隔離されている場合 (systemd の `PrivateTmp` 等) は選択肢にせず説明に書く (procB を先に試すので Linux ではまず起きない)。辿れるかは結果の `Spelling` の `usable_with_private_tmp` で分かる

### 既定の bind は綴りを残し、既定の connect は残さない (RS-Q4、kawaz 裁定 2026-11-20: a)

- bind の綴りはカーネルがソケットの寿命の間覚えるので、綴りが辿れ続けることが正しく動く条件 (`getsockname` の綴りで消す、DGRAM の返信)。connect の綴りは相手に残らず、残すのは速さのためのキャッシュでしかない。だから bind は既定でも残し、connect は既定では残さず、再利用したい人が resolve を選ぶ
- 既定の `bind` は、綴りが収まれば resolve の綴りを使う。thread-cwd・at は収まらない時の後ろ
- 既定の `bind` は `SocketFile` を返さないので、その E はプロセスが終わるまで残り、D と一緒に OS の一時ディレクトリの掃除で消える。exec をまたぐプロセスの掃除の仕組みは作らない。片付けを気にする利用者は `_ex` か resolve を使う
- 既定の `connect` はプロセスの中に D と E を残さない (B を初めて作った時は、その B と fd をプロセスの B として以後も使う)。link-file まで進んだ時は、プロセスの D を作らず、B の直下に乱数の名前の E を作って `B/E` で connect し、connect の後すぐ E を unlink する。片付けは unlink だけで待ちは入らない (`connect_nonblocking` は待たずに返る)
- 既定の `connect` の link-file の綴りは B の実パスの `B/E` だけ (procB を使わない。B は `/tmp` が先なので短い)。収まらなければこの経路は使えない
- D と flock の fd を持つのは、綴りを残す bind と `resolve_for_connect` だけ
- 同じパスへの connect の再利用は、`resolve_for_connect` で 1 度作った綴り (`B/D/E`) を何度も connect に使い、最後に `cleanup` する

### bind の試す順

| 順 | route | B の綴り | 綴り | 使う時 |
|---|---|---|---|---|
| 1 | `standard` | | 元のパス | 標準に渡す長さ以下 |
| 2 | `link-dir` | procB | `B/D/E/<ファイル名>` (E → ソケットのディレクトリ) | `/proc` を使えて収まる (`usable_cross_uid` の時は使わない) |
| 3 | `link-dir` | 実パス | 同 | 収まる |
| 4 | `link-file` | 実パス | `B/D/E` (E → ソケットのファイル) | bind が symlink を辿る OS |
| 5 | `thread-cwd` (FreeBSD は `at`) | | `E/<ファイル名>` (E は片付け済み) | Linux / Android・Apple の OS (`at` は FreeBSD) |
| 6 | `ENAMETOOLONG` | | | |

- procB の `link-file` は無い (`/proc` のある Linux は bind が symlink を辿らない)
- link-dir・link-file で実際に bind して失敗した時 (`EADDRINUSE` 等) は、作った E をその場で消してからエラーを返す (残さない。thread-cwd・at の E と同じ)。link-file を実行時に見分けて次へ進む時も E を消す
- E の片付け (既定の connect の E、bind が失敗した時の E、thread-cwd・at の E) が失敗しても、呼び出しの成否も元のエラーも変えずに黙る。消す失敗を理由に成功した connect を失敗にせず、元のエラーを消す側のエラーに置き換えない。利用者が呼ぶ `cleanup()` は E の unlink の失敗 (`ENOENT` 以外) をエラーで返し、`remove()` はファイルを消す側のエラーを先に、無ければ `cleanup` のエラーを返す (利用者が頼んだ片付けの結果は知らせる。統括)。`cleanup()`・`remove()` は成功した後は何もせず、失敗した後の呼び出しはやり直す (失敗を覚えて返し続けると片付ける手段が無くなる。統括)
- どの B を使ったかは診断用の `base` で返す
- bind は proc-direct・relative・widened・at-direct を使わない。綴りが後で無関係なファイルに当たる (proc-direct、relative、at-direct) か、アドレスが途中で切れて読む側を壊す (widened)

### link-file と、bind が symlink を辿る OS

- link-file の E は、元のパスのソケットのファイルの綴り (相対パスなら cwd を前に付ける) を指す。bind が最後の要素の symlink を辿る OS では元のパスにソケットができ、綴りにファイル名が出ないので、ファイル名の長さによらず届く (元のパス全体は PATH_MAX まで)
- 辿らないと実測した OS (Linux / Android、FreeBSD 15、OpenBSD 8、illumos (OmniOS)) の bind では試さない。辿るのは macOS 26 と NetBSD 11 (実測 2026-11-19、[findings](../findings/2026-11-19-bind-through-file-symlink.md))
- 他の OS では実行時に見分ける: bind が失敗した時に元のパスを `lstat` し、物があればそのエラー (`EADDRINUSE` 等) を返して次は試さない。無いか確かめられなければ、カーネルが辿らなかったとみなしてこの経路を使えないとして次へ進む (`skipped` に入る)。本当の失敗なら次の経路でも同じ失敗になり、そこで返る
- 元のパスの最後の要素に bind の前から symlink が置かれていた時に bind がそれを辿るのは標準の bind の性質で、sockat は確かめない (責務外。kawaz 2026-11-19)
- connect は最後の要素の symlink をいつも辿る

### thread-cwd・at

resolve の綴りが収まらない時の bind。

1. プロセスの D を fd で掴んだまま基準にする (B も D も作れなければ thread-cwd・at は使えないとして飛ばす)
2. D の中に、ソケットのディレクトリの realpath を指す乱数の名前の E を `symlinkat` で作る
3. D の fd を基準に `E/<ファイル名>` で bind する (下の手段)
4. E を、成功でも失敗でもすぐ消す (自分が作れた時だけ)。綴りは `Dangling`

| 手段 | fd (thread-cwd・at は D、connect の thread-cwd-direct はソケットのディレクトリ) を基準にする手段 | OS |
|---|---|---|
| thread-cwd | 使い捨てのスレッドで cwd を移す (`unshare(CLONE_FS)` → `fchdir`) | Linux / Android |
| thread-cwd | 使い捨てのスレッドで `pthread_fchdir_np(fd)` | Apple の OS |
| at | `bindat` / `connectat` に fd を渡す (スレッドを使わない。kawaz 承認 2026-11-19) | FreeBSD |

- thread-cwd は、seccomp の filter が掛かっているか確かめられない時 (`prctl(PR_GET_SECCOMP)` が 0 以外か失敗)、`unshare` が断られた時、`pthread_fchdir_np` が無い・失敗した時、スレッドを作れない時、NetBSD / OpenBSD / illumos では使えない
- seccomp の filter はプロセスの kill (SIGSYS) で `unshare` を断ることがある (systemd の `SystemCallFilter=` の既定) ので、filter が掛かっていれば呼ばない
- 呼び出し元のスレッドには触らない (`pthread_fchdir_np(-1)` で戻す形は、呼び出し元がスレッドに付けた cwd を消しうる)
- 綴りの中に既に消した乱数の名前 E があるので、後で fd の番号が使い回されても、cwd に同じ名前の物がたまたまある以外は当たらない (綴りは他の利用者に見えうるので、プロセスの cwd が他人も書ける場所だと、見て作り直されうる。元のパスで消せば当たらない)

### connect の試す順

書き込みもスレッドも要らない経路を先に、スレッドを立てる経路と置き場に書く経路をその後にする (kawaz 裁定 2026-11-19)。

| 順 | route | 中身 |
|---|---|---|
| 1 | `standard` | 元のパス |
| 2 | `proc-direct` / `relative` / `widened` / `at-direct` | 書き込みもスレッドも要らない (OS ごと、下の表) |
| 3 | `thread-cwd-direct` | 使い捨てのスレッドがソケットのディレクトリへ `fchdir` してファイル名で connect (D も E も要らない。connect の綴りは相手に残らないため) |
| 4 | `link-file` | B の直下の乱数の E を通す `B/E`。ファイル名の長さによらず届く。connect の後すぐ E を unlink する (`resolve_for_connect` の綴りは `B/D/E`) |
| 5 | `ENAMETOOLONG` | |

| OS | 2 の経路 |
|---|---|
| Linux / Android (`/proc` あり) | proc-direct (`/proc/self/fd/<ソケットのディレクトリの fd>/<ファイル名>`) |
| Linux / Android (`/proc` 無し) | relative |
| Apple の OS | relative → widened |
| FreeBSD | at-direct (ソケットのディレクトリの fd とファイル名) |
| NetBSD / OpenBSD / illumos / その他の Unix | relative |

- connect の綴りは相手に残らない (connect した側のソケットは bind されない) ので、E を残す必要が無い。書き込みもスレッドも要らない経路が速く、relative や widened は置き場を通す経路より遠くまで届く場面がある
- relative は途中で cwd が変わると一般のエラーになる (事後に確かめるので、別の所へ届くことは無い)
- thread-cwd-direct の届くファイル名は sockaddr に入る長さ
- connect の綴りの性質は返さない
- DGRAM の connect は stream の connect と同じ順

### fork をしない (RS-Q2、kawaz 裁定 2026-11-20)

- fork の経路を作らない (bind・connect とも)。fork の副作用はプロセス全体に及び、してほしくない利用者の方が多い
- 最終手段も無い。共有の置き場 (`/tmp`) の symlink を通す bind は `/tmp` の B として既定の順に入り、fork でしか届かない connect は作らない。引数から最終手段が消え、`forked` も無い
- 3 言語で届く所がそろう (Python・Go はもともと fork の経路を作らない)
- fork をやめて届かなくなる場面と、fork の手法の説明は [pages/fork-cwd-ja.md](../../pages/fork-cwd-ja.md)。sockat で届かない場面の全体は [届く範囲の表](../../pages/reach/README-ja.md)

### 綴りの性質 `Spelling` (RS-Q1、kawaz 裁定 2026-11-20: S1)

bind の綴りの性質を 1 つの値で返す。利用者が知りたいのは「この綴りを後で使えるか」の 1 点で、性質は互いに排他な種類 + 種類ごとの属性になるため。connect の綴りは相手に残らないので返さない。

```rust
#[non_exhaustive]
pub enum Spelling {
    Original,     // 元の絶対パス
    CwdRelative,  // 元の相対パス (cwd を変えると別の所を指す)
    Linked {
        removable: bool,               // 綴りで unlink すると実体が消えるか (link-dir: true、link-file: false)
        until: Until,                  // Process (procB) / Cleanup (実パス)
        usable_cross_uid: bool,        // 別の uid の相手が辿れるか
        usable_with_private_tmp: bool, // 自分と相手のどちらかが /tmp を隔離していても (systemd の PrivateTmp 等) 相手が辿れるか (procB の綴りはいつも true。B の実パスの綴りは、B の置き場の realpath する前のパスと綴りの実パスのどちらかが /tmp・/var/tmp を通れば false。mount 名前空間が丸ごと違う相手 (コンテナ等) までは保証しない)
    },
    Dangling,     // 片付け済みの E を含む綴り。どこにも届かない (thread-cwd・at)
}
```

- `CwdRelative` は sockat が経路で失わせたものでなく標準が元から持つ危険だが、知らせる (kawaz 裁定 2026-11-19)
- 「標準にそのまま渡したか」の bool は持たない (`spelling == Original` か `route == "standard"` で分かる)
- `usable_with_private_tmp` の「/tmp・/var/tmp を通る」は、要素単位で `/tmp`・`/var/tmp` であるか、それらの realpath の下にあること。procB の綴りは `/tmp` を通らないのでいつも true
- abstract の名前 (Linux / Android で先頭が NUL) の `Spelling` は `Original`

### 関数と引数 (RS-Q3、kawaz 裁定 2026-11-20: F1)

- 型ごとのモジュールに std の形で置く (stream は crate 直下、`datagram::`、`seqpacket::`)。操作ごとに `_ex(…, Options)`。resolve は用途ごとに 2 つ
- any 系 (`bind_any` 等) は作らない。`_ex` を既定の操作ごとに 1 つずつ置く
- 名前は各言語の慣習で決める。Python は `_ex` を子モジュール `sockat.ex` に置く (標準の `socket.connect_ex` と紛れるため。kawaz 裁定 2026-11-19)
- 既定の操作は path だけを取る。プロセス全体の既定を変える関数は、隠れた状態になるので作らない
- 経路を利用者が選ぶ・組み合わせる口は作らない (kawaz「素人が下手な組み合わせで微妙な使い方をする意味は無い」)

`Options`:

| 項目 | 中身 |
|---|---|
| `usable_cross_uid: bool` | 別の uid の相手も辿れる綴りを求める。bind 系 (`bind_ex`、`resolve_for_bind`) だけが見て、connect 系は見ない。B の選び方と procB を使わないことに効き、満たせなければ thread-cwd / at に進む。満たせたかは結果の `Spelling` で分かる (「別の uid と PrivateTmp」) |
| `base: Option<Path>` | 利用者が B の実体の場所を指定する (アプリが自分の管理する場所を渡す。例 `/tmp/app-<uid>/sockat`)。bind 系も connect 系も B の置き場として使う。綴りの形は自動の時と同じ順で選ぶ |

Rust の一覧:

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
sockat::resolve_for_bind(path, Options) -> Result<ForBind, ExError>       // path / spelling / cleanup() / socket_file() / 診断 (remove は持たない)
sockat::resolve_for_connect(path, Options) -> Result<ForConnect, ExError> // path / cleanup() / 診断 (route・skipped。base は持たない)

// 置き場 B を片付ける
sockat::sweep() -> io::Result<()>              // 呼んだ時だけ、置き場 1〜3 の既定の名前の B の中の、持ち主の死んだ D (ロックの外れた D) を消す
sockat::sweep_base(path) -> io::Result<()>     // Options.base の B の中の死んだ D を消す
```

```rust
pub struct Bound<S> {
    pub socket: S,
    pub file: SocketFile,   // remove(): bind したファイルを 1 回だけ消し、cleanup もする / cleanup(): E を 1 回だけ片付ける
    pub spelling: Spelling,
    pub route: &'static str, pub base: Option<&'static str>, pub skipped: Vec<Skipped>, // 診断用
}
pub struct Connected<S> { pub socket: S, pub route: &'static str, pub skipped: Vec<Skipped> }
pub struct Report { pub route: &'static str, pub skipped: Vec<Skipped> }
```

- resolve の戻り値は `remove` を持たない。`ForBind` は、利用者が自分で bind した後に `SocketFile` を受け取る口 (Rust は `socket_file(&self) -> io::Result<SocketFile>`、名前は各言語の慣習) を持ち、消すのはその `SocketFile` の `remove`。呼ばなければ消す口は無い (「`ForBind` の `SocketFile`」)
- connect 用の resolve には `SocketFile` を受け取る口を持たせず、消し間違いを型で防ぐ

### `SocketFile` の `remove`

- `remove` はファイルを消すだけで、listener を閉じない。閉じるのは利用者 (Rust は listener を move するので、閉じる対象を持てない。渡した先のライブラリが閉じた後の二重の close も起きない)
- bind したソケットのファイルの realpath と `(st_dev, st_ino)` を覚え、そのパスの `(st_dev, st_ino)` が同じ時だけ消す
- 置き換えの見分けは `(st_dev, st_ino)` だけで行い、約束するのは listener を開いている間の置き換えまで。閉じた後に消して作り直された物は、番号をすぐ使い回すファイルシステム (ext4、BSD の UFS / FFS) で見分けられない。`remove` は listener を閉じる前に呼ぶよう勧める (kawaz 裁定 2026-11-19。実測は [findings](../findings/2026-11-19-inode-reuse-after-close.md))
- 相対パスの時は、パスを何も引く前と、bind と覚えるための realpath の両方の後でプロセスの cwd の `(st_dev, st_ino)` を比べ、違えば覚えられない時と同じに扱う (間の cwd の変更で、元の cwd の無関係なファイルを覚えて消さないため。sockat-go の指摘 2026-11-19)
- bind の後、元のパスの最後の要素が symlink なら (macOS・NetBSD では標準の bind が辿り、その先にソケットを作る)、辿った先の実パスと `(st_dev, st_ino)` を覚える。`remove` が利用者の symlink を消さないため。最後の要素が symlink でない時も含め、覚える物がソケットでなければ覚えられない扱い (`bind_ex` は listener を閉じ E を片付けてエラー、`socket_file()` はエラー。bind の直後に置き換わった物を覚えると `remove` がそれを消すため) (統括)
- `remove()` が失敗した時も `cleanup` まで行い、remove のエラーを返す
- listener を閉じた時: 既定の bind (Go の `Listen`) は標準と同じにする。閉じる時に綴りで unlink する標準 (Go) では、link-dir の綴りは途中の E を辿って実体を消し (標準と同じ)、link-file の綴りは unlink が最後の symlink を辿らないので E 自体が消えてソケットのファイルは残る (標準と違う。README に書く)。`Dangling` の綴りは unlink させない (Go は `SetUnlinkOnClose(false)`)。`_ex` の bind は、どの綴りでも閉じた時に消さない。消すのは `SocketFile` の `remove()` だけ (綴りで消すと、置き換わったファイルを見分けずに消すため)

| 言語 | 形 |
|---|---|
| Rust | `SocketFile` の `remove`。Drop では消さない |
| Python | 戻り値に引数なしの関数を含める |
| Go | `*SocketFile` の method `Remove()` / `Cleanup()`。`ListenEx` の listener は短いパスでも閉じた時に消さず、消すのはこれだけにする (`SetUnlinkOnClose(false)`) |

### `ForBind` の `SocketFile`

- resolve の時点では bind していないので、ソケットのファイルの `(st_dev, st_ino)` を覚えられない。だから `ForBind` は `remove` を持たず、bind した後に呼ぶ口で `SocketFile` を返す
- 呼んだ時点で綴りを辿り、ソケットのファイルの realpath と `(st_dev, st_ino)` を覚えた `SocketFile` を返す。辿れなければ (bind する前、ファイルが無い) エラー
- 元のパスの最後の要素が symlink なら、辿った先の実パスと `(st_dev, st_ino)` を覚え、辿った先がソケットでなければエラー (`remove` と同じ。統括)
- 返す `SocketFile` は `Bound` の物と同じ働き (`remove` はファイルを 1 回だけ消して `cleanup` もし、`cleanup` は `ForBind` の `cleanup` と同じ E を 1 回だけ片付ける)
- 約束の範囲は `Bound` の `remove` と同じく listener を開いている間の置き換えまでで、呼ぶのは bind の後・listener を閉じる前。bind から呼ぶまでの間の置き換えは見分けられない
- 綴りが `CwdRelative` の時は、resolve の時と呼んだ時でプロセスの cwd の `(st_dev, st_ino)` を比べ、違えばエラー (間の cwd の変更で無関係なファイルを覚えないため)

### 診断と、失敗した時

| 項目 | 中身 |
|---|---|
| `route` | 通った経路の名前 |
| `base` | bind で使った B の綴り (`proc`・`sockdir`・`runtime`・`tmpdir`・`tmp`・`given`。`given` は `Options.base` の B で、procB でも実パスでも同じ。「綴りの形」)。綴りが B を通る時 (link-dir・link-file) だけ値を持ち、他 (standard・thread-cwd・at) は無し。`Connected`・`Report`・`ForConnect` には持たせない |
| `skipped` | 試して使えなかった経路の並び (試した順)。各要素は `{ name: 経路の名前, reason: 使えなかった理由 }`。経路の名前ごとに 1 件 (link-dir を procB と実パスで試しても 1 件で、理由は最後の物)。`usable_cross_uid` で procB を使わないのは経路を飛ばすことではないので、何も足さない。入るのは、その呼び出しの順の表 (bind は OS で、connect は OS と `/proc` を使えるかで決まる行) に並ぶ経路だけ (`/proc` を使えない Linux の connect の行に proc-direct は無いので入れない) |

- 成功した時、`route` より前に試した経路はすべて「使えなかった」もの (実際に bind / connect して失敗したら、そこでエラーを返して次を試さない。bind の link-file を実行時に見分ける時だけは次へ進む)。そのため「使えたか」の真偽値は持たない
- `route`・`base`・`skipped` の名前と `reason` は診断用で、中身を約束しない。経路の名前は「手段 + 何についてか」(`link-dir`・`link-file`・`thread-cwd`・`thread-cwd-direct`・`at`・`at-direct`・`proc-direct`・`relative`・`widened`・`standard`。接尾辞 `-direct` は E を通さずファイル名で渡す形) で、日英で同じ ASCII
- `_ex` が失敗した時も、エラーに `skipped` を付ける。実際に bind / connect して失敗した経路があれば、その名前 (`route`) も付ける (全部が使えなかった `ENAMETOOLONG` では無い)
- 付け方は各言語の慣習に従う。OS のエラーの errno はこれまでどおり取り出せる形を保つ (Rust は errno を持つエラー型に `skipped` を持たせる、Go は `Unwrap` で errno に届くエラー型、Python は例外の属性 等)

### DGRAM と SEQPACKET

- この上に作る。DGRAM の API は std の `UnixDatagram` の形に合わせ、パスを取る関数と、それと組で使う `unbound` だけを写す (`datagram::bind(path)`、`unbound()`、`connect(&sock, path)`、`send_to(&sock, buf, path)`)。`pair` は写さない
- Go の DGRAM の connect は `DialUnixgram(path)` (作成と connect を 1 回で。Go の標準の形)。bind したソケットを長いパスへ connect したい人は、resolve で綴りを作って標準に渡す
- SEQPACKET は `seqpacket::` に stream と同じ操作を置く。返す型は未決
- 細部は「未決」

理由:

- 綴りが消さない B・D・E を通るので、生きている間は `getsockname` の綴りで消す上のライブラリ、DGRAM の返信、運用の道具が元のパスと同じに働き、ソケットの型と操作によらず std に渡せる
- D の名前が乱数で、D が生きている間は flock で守られ、B と D が 0711 なので、綴りが後で無関係なファイルに当たらない (procB はプロセスが終われば辿れない、実パスの綴りは D が消えるまで同じ所を指す)
- B を利用者ごとに使い回し、D を flock で守り、死んだ D を OS の一時ディレクトリの掃除に任せると、sockat が掃除の仕組みを持たずに済む。PID の判定も exec をまたぐ仕組みも要らない
- 実体の置き場は、OS の掃除で死んだ D が消え、生きている D が守られる所を先にする。B をプロセスごとに 1 つにすると、その順の理由がどの OS でもそのまま効き、D もプロセスに 1 つで済む
- 既定の connect は D を作らず、B の直下の E を unlink するだけなので、プロセスの中に D と E を残さず、待ちも入らない
- connect は書き込みもスレッドも要らない経路を先にするので、CLI の 1 回だけの connect は普通そこで終わり、置き場に書けない sandbox でも届く
- fork をやめると、副作用がプロセス全体に及ぶ経路が無くなり、3 言語で届く所がそろう
- resolve を用途で分けると、bind と connect で選ぶ綴りが違うことと、connect に消す口が無いことを型で表せる
- `ForBind` が bind の後に `SocketFile` を返すと、resolve の時点で覚えられない `(st_dev, st_ino)` を bind の後に覚え、`Bound` の `remove` と同じ約束で消せる

悪い面:

- 状態がアプリの置き場の外 (`/tmp`・`$XDG_RUNTIME_DIR`・`$TMPDIR`) に増える。既定の `bind` の E と死んだプロセスの D は OS の掃除まで残る (macOS の `/tmp` は再起動まで、`$XDG_RUNTIME_DIR` はログアウトまで)
- B が macOS の `$TMPDIR` にある時 (`/tmp` にも `$XDG_RUNTIME_DIR` にも作れない時) は、dirhelper が生きている D も 3 日で消しうる。systemd v242 より古い Linux では生きている D も 10 日で消されうる (綴りが辿れなくなるだけ)
- `/tmp` の B は、B が消えた後に他人が同じ名前で作り直しうる (片付けた後の綴りは使わない、と説明に書く)
- procB の綴りは `/proc/<pid>/fd/<fd>/` + D + `/E/` の分だけ長く、Linux で届くファイル名は thread-cwd より短い
- fork でしか届かなかった場面 (スレッドの cwd も書ける置き場も無い環境等) は届かない
- `usable_cross_uid` を満たす置き場が無いか綴りが収まらない時は、`Dangling` の綴りになる
- thread-cwd・at はファイル名の上限が `E/` の分短い。呼び出しのたびに E を作って消し、途中でプロセスが死ぬと E が D に残る (D と一緒に OS の掃除で消える)
- thread-cwd・at の E はソケットのディレクトリの realpath を指すので、E を作った後のディレクトリの rename や symlink の張り替えは反映されない
- exec をまたぐと D の flock の fd が閉じ、引き継いだ listener が生きていても D・E は `sweep()` や OS の掃除で消されうる (綴りが辿れなくなるだけ)。procB の綴りは exec の時点で辿れなくなる (kawaz の「exec は気にしない」の範囲)
- `pthread_fchdir_np` は libSystem の非公開 API で、将来消えうる (消えたら次へ進む)

## Alternatives Considered

- 案 A: 綴りを呼び出しの中で片付け、片付けた後は綴りがどこにも無い形 (既定の bind を今の形で呼び出しの中で片付ける、を含む。RS-Q4 の b)
  - 不採用理由: bind の綴りが辿れ続けることが正しく動く条件 (`getsockname` の綴りで消す、DGRAM の返信)。fork をやめた分、OpenBSD・illumos (スレッドの cwd も symlink を辿る bind も無い) と、Linux で seccomp が掛かり `/proc` も無い環境で、既定の `bind` が長いパスに全く届かない (届く範囲の表で分かった)
- 案 B: B を開いて fd で掴んだ後に消し、`/proc/<pid>/fd/<B の fd>/D/…` だけで使う (置き場に何も残さない)
  - 不採用理由: 消したディレクトリの中には作れない (`ENOENT`、実測)
- 案 C: B を使い回さずプロセスごとに新しく作り、B を片付ける口 (`cleanup_base`) を置く
  - 不採用理由: 既定の `bind` は片付けの口を返さないので、片付け損ねた B の掃除が必須になる
- 案 D: 片付け損ねた B・D を、名前に PID を入れて次の sockat が掃除する
  - 不採用理由: exec をまたぐプロセス (pid を変えずに execve して listener を引き継ぐ) では「その PID は生きている」ので消されない。PID の使い回しで、生きている他人の B を消さない確かめ方が要る
- 案 E: resolve のたびに B の中を一覧して、死んだ D を掃除する
  - 不採用理由: resolve の手数が増える (connect は手数・IO の回数を重視する)。明示の `sweep()` を呼んだ時だけにする
- 案 F: exec をまたぐプロセスにも効く掃除の仕組みを作る
  - 不採用理由: 死んだ D は OS の一時ディレクトリの掃除に任せる。片付けを気にする利用者は `_ex` か resolve を使う
- 案 G: D の名前をカウンタにする
  - 不採用理由: プロセスが終わった後に同じ PID・同じ fd 番号の別の sockat のプロセスが現れると、カウンタの D は同じ綴りで他人のソケットを指す
- 案 H: 実体の置き場を `$XDG_RUNTIME_DIR` → `$TMPDIR` → `/tmp` の順にする
  - 不採用理由: `$XDG_RUNTIME_DIR` は age の掃除が無く死んだ D がログアウトまで残り、macOS の `$TMPDIR` は生きている D も 3 日で消しうる。`/tmp` は Linux で死んだ D が 10 日で消え生きている D が flock で守られ、macOS で生きている D が消えない
- 案 I: 既定の `connect` が綴りをキャッシュして使い回す
  - 不採用理由: 隠れた状態がプロセスの中にでき、いつ片付くかが利用者から見えず、長命のプロセスでは宛先の数だけ symlink が溜まる。connect の綴りは相手に残らないので、残すのは速さのためのキャッシュでしかない。再利用したい人は resolve を使う
- 案 J: fork の経路 (fork-cwd・fork-cwd-direct) を残す、または connect の最終手段 (`Options.last_resort`) として残す
  - 不採用理由: bind の子に listen させず親がすれば相手から見える副作用は無い (実測 2026-11-18) が、見えない副作用 (親に `SIGCHLD`、`pthread_atfork` の handler、他のスレッドの `waitpid(-1)` が子を刈り取りうる、子が全 fd の複製を持つ) と、connect では相手に見える pid がプロセス全体に及ぶ。してほしくない利用者の方が多い。thread-cwd-direct と link-file の後なので、出番はスレッドも B も使えない環境だけ
- 案 K: `Spelling::Linked` に `recreatable_after_cleanup` (cleanup の後に他人が作り直せるか) を持たせる
  - 不採用理由: std の元のパスを消した後に、そのディレクトリに書ける人が作り直せるのと同じで、分岐させるほどの差でない
- 案 L: 綴りの性質を名前の並び (`forked`・`cwd-relative`・`dangling`・`unremovable-by-spelling`・`temporary`・`owner-only` 等) で返す (S2)
  - 不採用理由: 種類と属性が混ざり、組み合わせの意味を利用者が考えることになる
- 案 M: 型を引数で渡す (`bind(path, Type)`、F2)
  - 不採用理由: std の形から外れる
- 案 N: builder (`Options::new().usable_cross_uid(true).bind(path)`、F3)
  - 不採用理由: `_ex` の数は減るが、型ごとの操作が builder に集まる
- 案 O: resolve を 1 つにする
  - 不採用理由: 戻り値に `SocketFile` を受け取る口があるかが用途で変わる。型で区別して消し間違いを防ぐ
- 案 P: `PrivateTmp` の相手を `Options` の選択肢にする
  - 不採用理由: procB を先に試すので Linux ではまず起きない。説明に書き、辿れるかは `Spelling` で分かる
- 案 Q: プロセス全体の既定を変える関数を置く
  - 不採用理由: 隠れた状態になる
- 案 R: bind の綴りにランダムな部品を挟まない (ファイル名だけ、`/proc/self/fd/<fd>/<ファイル名>`)
  - 不採用理由: 後で解決すると無関係なファイルに当たる。消すのは利用者のコードでなく上のライブラリで、利用者が避けられない
- 案 S: Apple の OS の bind で広げた sockaddr を使う
  - 不採用理由: アドレスが途中で切れて CPython / Go の標準を壊す
- 案 T: any 系を別の関数・別のパッケージで置く (`bind_any`、Rust の feature `any`、Python の `sockat.any`、Go の `atanycost`)
  - 不採用理由: API が増える。Go のパッケージ名の問題がある。feature の後ろに隠すと推奨コードと結び付けにくい
- 案 U: 経路を自由に選べる引数を `_ex` に持たせる
  - 不採用理由: 素人が下手な組み合わせで微妙な使い方をする意味は無い (kawaz)
- 案 V: 経路の名前を契約として返す
  - 不採用理由: 経路の追加・変更が破壊的変更になる
- 案 W: 試した経路を `{名前, 使えたか, 理由?}` の 1 つの並びで返す
  - 不採用理由: 成功時は最後の 1 つだけが使えたものになるので、真偽値と省略できる理由が起きない組み合わせを許す
- 案 X: `remove` が listener を閉じてから消す
  - 不採用理由: Rust は listener を move するので作れず、言語ごとに形が割れる。渡した先のライブラリが閉じた後の二重の close も起きる
- 案 Y: `bind_ex` が `O_PATH` (のある OS) でソケットのファイルを開いて持ち、閉じた後も番号を使い回させない
  - 不採用理由: `remove` を呼ばない利用者も fd を持ち続け (Python・Go は GC まで)、閉じた後もファイルシステムを umount できない。`O_PATH` の無い OS (NetBSD・OpenBSD・illumos・Apple の OS) では効かず、OS で約束が割れる
- 案 Z: `remove` の見分けに birth time か ctime も比べる
  - 不採用理由: birth time は取れない OS・ファイルシステム・言語の版があり、時刻の粒度が粗いカーネルでは同じ tick の作り直しを見分けられない。ctime は利用者の chmod / chown で変わり、自分のファイルを消さなくなる
- 案 AA: link-file の bind の後に元のパスを `lstat` して、ソケットが元のパスにできたかを確かめる
  - 不採用理由: 元のパスの最後の要素に bind の前から置かれていた symlink を辿るのは標準の bind の性質で、sockat の責務外 (kawaz 2026-11-19)
- 案 AB: link-file で bind したソケットの fd の `fstat` と元のパスの `lstat` の `(st_dev, st_ino)` を照らし合わせて確かめる
  - 不採用理由: ソケットの fd の `fstat` はソケットのファイルの inode を返さない (macOS で `st_dev` が -1、inode も一致しない。[findings](../findings/2026-11-19-bind-through-file-symlink.md) で実測)
- 案 AC: 相対パスの `bind_ex` を入口で絶対パスにする
  - 不採用理由: 短い相対パスが標準と違う経路に回り振る舞いが変わる
- 案 AD: B の綴りを procB → dirB (`$XDG_RUNTIME_DIR` と `$TMPDIR` の実パスの短い方の B) → tmpB (`/tmp` の B) の順に、別々の B で試す
  - 不採用理由: `/proc` の無い macOS で `$TMPDIR` の B が `/tmp` の B より先に使われ、実体の置き場の順の理由 (`$TMPDIR` は生きている D も消しうる) とぶつかる。1 つのプロセスが複数の B と D を持つ
- 案 AE: thread-cwd・at に、呼び出しごとのディレクトリ (置き場を `${TMPDIR:-/tmp}` → `/tmp` → ソケットのディレクトリの順に試す) と、その中の symlink を作って呼び出しの最後に消す
  - 不採用理由: プロセスの D を fd で掴んでいるので、D の中に E を作って消すだけで足りる
- 案 AF: 既定の connect の link-file も、プロセスの D の中に E を作る
  - 不採用理由: D と flock の fd がプロセスに残り、既定の connect がプロセスの中に状態を残す

- 案 AG: `ForBind` が `remove()` を持ち、呼ばれた時にそのパスを確かめずに消す
  - 不採用理由: 置き換えを見分ける `(st_dev, st_ino)` を覚えていないので、`Bound` の `remove` の約束 (置き換えたファイルを消さない) を守れない
- 案 AH: プロセスが初めて B を使う時に 1 回だけ、上限つき (死んだ D を最大 16) で `sweep` する
  - 不採用理由 (kawaz 裁定 2026-11-21、AS-Q1 = a): `/tmp` に置く利用者ごとの socket や一時物 (ssh-agent、tmux 等) は、作った側が他人の残骸を消さず OS の掃除に任せるのが通例。次のプロセスが片付ける形は容量が増え続けるキャッシュ (Go のビルドキャッシュ、Gradle 等) のもので、D と E は容量がほぼ 0。試験を繰り返す利用者は `sweep()` を呼ぶ (利用者の実測は [findings](../findings/2026-11-21-consumer-measurements-0-5.md))
- 案 AI: 終了時に自分の D を消す exit ハンドラを sockat が登録する
  - 不採用理由: ライブラリが黙ってプロセス全体の終了の振る舞いを変える (fork した子でも走る)。Go には仕組みが無く 3 言語でそろわない。クラッシュ・kill・exec では走らない。一時物の片付けを exit で行うライブラリは、利用者が頼んだ時だけ動く形が通例 (Node の `tmp` の `setGracefulCleanup()`、Java の `deleteOnExit()`) で、それは `sweep()` を呼ぶ形と変わらない

## Consequences

- SPEC を書き直す (公開する操作、経路の名前と試す順番、B・D・E、置き場、綴りの性質、どこから届かなくなるか、長いパスで標準と違う点、試験の観点)。各言語の実装は経路と API を作り直す
- fork の経路 (fork-cwd・fork-cwd-sockdir・fork-cwd-direct)、bind の proc・symlink-file・symlink-dir、connect の thread-cwd・at・proc・proc-held・symlink-file、`-sockdir` の経路、呼び出しごとのディレクトリ、最終手段、`losses` は無くなる
- 説明 (SPEC・利用者向けの文書) に書くこと: 状態がアプリの置き場の外に増えること、片付けた後の綴りは使わないこと、`PrivateTmp` の相手、systemd v242 より古い環境と macOS の `$TMPDIR` で生きている D が消されうること
- 経路ごとの費用 (syscall の数、時間、置き場への書き込み) をベンチマークで測り、届く範囲の表と経路の説明に数字で載せる
- 試験の観点: 綴りを unlink / stat しても無関係なファイルに当たらない、B の途中の確認で外れた置き場を使わない、`Options.base` が外れたらエラー、並行する多数の bind / connect で B・D の作成が競合しない、`sweep()` が生きている他のプロセスの D を消さない、`cleanup` の後に E が残らない、既定の connect の後に B の直下に何も残らず待ちも入らない、`remove` が置き換えたファイルを消さない、thread-cwd・at でプロセスの cwd が変わらず呼び出しの後に E が残らない、link-file が辿らない OS で `skipped` に入り何も残らない

## 未決

- 届く長さ: procB の綴りは `/proc/<pid>/fd/<fd>/` + D + `/E/` でおよそ 35 バイト食い、Linux で届くファイル名はおよそ 70。thread-cwd (96) との間は thread-cwd に回す
- FreeBSD の connect で link-file を使えるか (未確認)
- `send_to` は resolve の綴りに送るので relative (送った後に取り消せない) を使わない。resolve で済まない長さの `send_to` をどうするか (thread-cwd で送る、`ENAMETOOLONG` にする)
- 長いパスに bind した DGRAM の送り手への返信は、綴りが生きている間は届く (procB は同じ uid、`/tmp` の B の実パスは別の uid も)。届かない場面 (`cleanup` の後、procB で別の uid) を `Spelling` でどう表すか
- Rust の SEQPACKET の返す型

## 関連

- [docs/SPEC-ja.md](../SPEC-ja.md)
- [resolve と置き場 B の issue](../issue/2026-11-20-resolve-and-persistent-base.md) (合意と裁定の記録、利用者の回答)、[DGRAM / SEQPACKET の issue](../issue/2026-11-18-datagram-and-seqpacket.md)
- [OS の一時ディレクトリの掃除の調査](../research/2026-11-20-tmp-cleaners-and-persistent-base.md)、[DGRAM / SEQPACKET の調査](../research/2026-11-19-datagram-and-seqpacket.md)
- [ファイルを指す symlink を通した bind の実測](../findings/2026-11-19-bind-through-file-symlink.md)、[閉じたソケットのファイルの inode 番号の使い回し](../findings/2026-11-19-inode-reuse-after-close.md)
- [届く範囲の表](../../pages/reach/README-ja.md)、[fork-cwd](../../pages/fork-cwd-ja.md)
- 裁定: kawaz (2026-11-21: AS-Q1 = a (死んだ D を自動では消さない)。2026-11-19: connect の順、thread-cwd・at、`remove` の約束の範囲、`CwdRelative`、link-file の責務外。2026-11-20: RS-Q1 = S1、RS-Q2 = fork をしない、RS-Q3 = F1、RS-Q4 = a、B と D。2026-11-21: B の作り方)。統括 (2026-11-21: B をプロセスごとに 1 つ、`usable_cross_uid` を満たせない時は thread-cwd / at、既定の connect は D を作らない、thread-cwd・at は D を基準にする、D と E の mode。同日の SPEC の書き直しで: `resolve_for_bind` の link-file は実測した OS だけ、`skipped` は名前ごとに 1 件、`base` を持つのは B を通る綴りだけ、`Options.base` は B そのもので複数の B を持ちうる、`Options.base` のエラーの種類、link-dir の E は realpath、D の作り方と `sweep()` の見分け方、`resolve_for_connect` の返す物、既定の connect の link-file は実パスの `B/E`、thread-cwd-direct の届く長さ、DGRAM の connect の順。診断の `base` の値 `given` (`Options.base` の B、綴りの形によらない)、link-dir・link-file で bind に失敗した時は E を消してからエラーを返す、`ForBind` は `remove` を持たず bind の後に `SocketFile` を受け取る口を持つ、置き場の realpath と `usable_with_private_tmp`、connect 系は `usable_cross_uid` を見ない、B・D・E の名前と乱数、既にある B の mode と `usable_cross_uid` の B 自身の x、空・相対パスの `$TMPDIR` / `$XDG_RUNTIME_DIR`、`ForConnect` は `base` を持たない、`sweep()` の対象と `sweep_base`、既定の connect が作った B をプロセスの B にする、D を作った後の `lstat` の確かめ、置き場 4 の B はディレクトリごと・収まらないと分かれば B を作らない。sockat-go の問いへの答えで: Go の DGRAM は `DialUnixgram`、Go の消す口は `*SocketFile` の `Remove()` / `Cleanup()`、listener を閉じた時の扱い (既定の bind は標準と同じ、`_ex` は消さない)、`skipped` は呼び出しの順の行に並ぶ経路だけ、`/proc` を使えるかの確かめ、D と B の作り方 (0700 → 確かめ → 0711、umask で開けなければ消して次へ)、procB の `usable_with_private_tmp` はいつも true、`usable_cross_uid` で thread-cwd・at に進む時の D の置き場、`sweep` の対象外の B が残ること、`Options.base` の相対パスと名前で終わらないパスは引数の誤り、`remove()` が失敗した時も `cleanup`、abstract の `Spelling`、「/tmp を通る」の定義、`sweep` が触らない物、「他人が書けない」は group も含む。同日の決定で: `remove` と `ForBind` の `socket_file()` は bind の後に元のパスの最後の要素の symlink を辿った先の実パスと `(st_dev, st_ino)` を覚え、辿った先がソケットでなければ覚えられない扱い、`sweep` / `sweep_base` は B の直下の D の形の名前のディレクトリだけを対象にする、E の片付けが失敗しても呼び出しの成否も元のエラーも変えずに黙る)
- [DR-0003](DR-0003-single-connect-when-standard-never-blocks.md)、[DR-0004](DR-0004-standard-length-per-language.md)、[DR-0006](DR-0006-nul-is-invalid-at-any-length.md)
