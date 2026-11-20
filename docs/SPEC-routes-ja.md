# sockat 仕様: 経路の作り方

> [English](./SPEC-routes.md) | 日本語

各言語の実装者に向けた、経路の作り方。利用者への約束 (公開する操作、試す順、綴りの性質、エラー) は [SPEC](SPEC-ja.md) が正本で、この文書はそれを満たす作り方を書く。用語 (B・D・E・置き場・procB・試す・使えない 等) は [SPEC の用語](SPEC-ja.md#用語)。数字はバイト。

## 共通

- ディレクトリの開き方 (ソケットのディレクトリ等): Apple の OS は `O_SEARCH` (カーネルが `EISDIR` / `EINVAL` を返したら `O_RDONLY`)、Linux / Android は `O_PATH | O_DIRECTORY`、他は `O_RDONLY | O_DIRECTORY`
- 最初にソケットのディレクトリを `stat` で引き、realpath を取る。無ければ `ENOENT`、ディレクトリでなければ `ENOTDIR`、realpath を引けなければそのエラー (どれも長さの判定や B・D・E を作るより前)
- ソケットのディレクトリの fd が要る経路 ([proc-direct](#proc-direct)、[at-direct](#at-direct)、[thread-cwd-direct](#thread-cwd-direct)) だけがそれを開き、開けなければその経路は使えない (他の OS の `O_RDONLY` は読み取り権限の無いディレクトリを開けない)
- 呼び出し元がソケットを作る。ブロックしない connect ではその前にソケットを非ブロッキングにする。bind の後の listen は呼び出し元がする
- どの経路も、呼び出し元のプロセスの cwd も呼び出し元のスレッドの cwd も変えない

## B の作り方

自動の置き場も `Options.base` も同じ手順。

1. 置き場のパス (`Options.base` は親のパス) を realpath で実パスにする (macOS の `/tmp` → `/private/tmp` 等)。以後の確かめ・開く・綴るは、この実パスで行う
2. ルートから親までの途中を全部確かめる: どれも、持ち主が root か自分で、かつ他人が書けないか sticky が立っている (sticky でも持ち主は中の物を付け替えられるので、持ち主の条件は外さない。OpenSSH の StrictModes と同じ考え。祖先が他人に書けると親ごと付け替えられる)。プロセスで最初の 1 回だけ
3. 親を `O_DIRECTORY | O_NOFOLLOW` で開いて fd で掴み、`mkdirat(親の fd, 名前, 0700)` で作る
4. 作った直後に `fchmodat(親の fd, 名前, 0711)` で mode をそろえ (umask で削られた分を戻す。親は確かめ済みで他人は付け替えられない)、それから `O_DIRECTORY | O_NOFOLLOW` で開いて `fstat` で実ディレクトリ・持ち主が自分を確かめる。そろえられない・開けない時は、作った自分の空のディレクトリを消して次の置き場へ (`Options.base` はエラー)
5. `EEXIST` なら、既にある物を同じく確かめる (実ディレクトリ・持ち主が自分・他人が書けない)。mode が 0711 でなくても使い、mode を変えない。外れたら、自動の置き場は `sockat-<uid>.<乱数 10 文字>` に落とし、`Options.base` はエラー

- 「他人が書けない」は group も含む (`mode & 022 == 0`)
- 途中のディレクトリが無い時、sockat は作らずにエラー (アプリの管理する場所の作り方はアプリが決める)
- 名前は `sockat-<uid>` (`$XDG_RUNTIME_DIR` の下は `sockat`、ソケットのディレクトリの下は `.sockat.<乱数 10 文字>`)。`Options.base` は B そのもののパスで、その最後の要素が名前
- `Options.base` のエラー: 相対パスの時と、最後がファイル名でない時 (`dir/`・`..`・`/`) は引数の誤り、途中のディレクトリが無い時は `ENOENT`、base がディレクトリでない時は `ENOTDIR`、持ち主・権限の確かめに外れた時は `EPERM`
- `Options.base` の確かめ (途中と、既にあれば B 自身。何も作らない) は、長いパスでソケットのディレクトリを引いた後、経路を試す前に bind でも connect でも行う。外れたら `route` は無し、`skipped` は空。B を作るのは、B を使う経路に来た時だけ

### 実体の置き場

B の実体をどこに作るかと、B をどう綴るか ([綴りの形](#綴りの形)) は別の軸。B はプロセスごとに、利用者が `Options.base` を指定しなければ次の順で最初に作れた所の 1 つ (OS の掃除で死んだ D が消え、生きている D が守られる所を先に)。

| 順 | 置き場 | 理由 |
|---|---|---|
| 1 | `/tmp` | Linux は死んだ D を 10 日で消し、生きている D は flock で守られる。macOS は生きている D を消さない |
| 2 | `$XDG_RUNTIME_DIR` | age の掃除が無く、死んだ D はログアウトまで残る |
| 3 | `$TMPDIR` | macOS の `$TMPDIR` は dirhelper が 3 日で消しうる (生きている D も) |
| 4 | ソケットのディレクトリ | 1〜3 のどこにも作れない時 |

- `$TMPDIR`・`$XDG_RUNTIME_DIR` が空か相対パスの時は、その置き場を使わない
- 1 つのプロセスが使う B が 1 つなのは置き場 1〜3 のこと。4 (ソケットのディレクトリ) の B はソケットのディレクトリごと
- 綴りが収まらないと先に分かる時 (置き場の実パスの長さから見積もれる時) は、B を作らない
- 既定の connect が link-file で B を初めて作った時も、その B (と fd) をプロセスの B として以後も使う (D は作らない)
- `Options.base` を指定した時は、そのパスを B にする。sockat は中にプロセスごとの D を作るだけで、B の掃除はアプリに任せる。確かめて外れたらエラーで、自動の置き場に落とさない
- 呼び出しごとに違う `Options.base` を渡せば、1 つのプロセスが複数の B を持ち、D は (プロセス, B) ごとに作る
- `usable_cross_uid` の時の B の選び方は「[別の uid と PrivateTmp](#別の-uid-と-privatetmp)」

### 綴りの形

sockat が自分で判断する。上から順に、収まる物。

| 綴り | 形 | 使う時 | 診断の `base` | 他のプロセスが辿れるか |
|---|---|---|---|---|
| procB | `/proc/<pid>/fd/<B の fd>/D/…` | `/proc` を使えて収まる時 (`usable_cross_uid` の時は使わない) | `proc` (B がソケットのディレクトリの時は `sockdir`、`Options.base` の B の時は `given`) | 同じ uid・同じ PID 名前空間だけ (root は辿れる)。プロセスが終われば辿れない |
| 実パス | B の実パス `…/B/D/…` | 収まる時 | B の置き場 (`tmp` / `runtime` / `tmpdir`。`Options.base` の B の時は `given`) | B までの途中と B 自身が全部 other に x を持てば別の uid も (`/tmp` の B)、そうでなければ同じ uid だけ (`/run/user/<uid>` と macOS の `$TMPDIR` は 0700) |

- procB は実体の置き場がどこでも同じ形
- `/proc` を使えるかは、`/proc/<pid>/fd/<B の fd>` を stat した `(st_dev, st_ino)` が、B の fd の `fstat` と同じ時だけ使えるとする (PID 名前空間と `/proc` の mount の食い違いに備える)
- 診断の `base` は、B が一時の置き場 (`/tmp`・`$XDG_RUNTIME_DIR`・`$TMPDIR`) の時は綴りの形 (procB は `proc`、実パスは置き場の名前)、一時の置き場でない B (ソケットのディレクトリ・`Options.base`) の時は綴りの形によらずその B (`sockdir`・`given`) を表す。綴りが procB か実パスかは `Spelling` の `until` で分かる
- B をソケットのディレクトリに作った時は、実パスの綴りは元のパスより長くなるので、使えるのは procB の綴りだけ。`/proc` を使えない OS では resolve の綴りを使えず、thread-cwd / at へ
- どの綴りも収まらなければ thread-cwd / at へ

### 別の uid と PrivateTmp

- `Options.usable_cross_uid` の時は、実体の置き場の順のうち、B までの途中のディレクトリと B 自身が全部 other に x (辿る権限) を持つ所だけを B に使い (その中で最初に作れた所。既にある B が 0700 なら満たさない)、procB の綴りは使わない (子が 0711 でも親が 0700 なら別の uid は辿れない。実測)
  - `/tmp` (1777) はいつも当たる
  - `$XDG_RUNTIME_DIR` (`/run/user/<uid>`) と macOS の `$TMPDIR` は 0700 なので外れる。`$TMPDIR` を辿れる場所に向けた環境なら当たる
- 当たる所が無いか、その B の綴りが収まらなければ、満たさない綴りに落とさず thread-cwd / at (`Dangling`) に進む。その D は、`usable_cross_uid` を見ない普段の B (置き場 1〜4 の順) に作る
- `Options.base` と一緒の時は、その base までの途中と base 自身が全部 other に x を持つかを確かめ、外れたら `EPERM` (自動の置き場に落とさない)
- connect 系 (既定の connect、`connect_ex`、`resolve_for_connect`) は `usable_cross_uid` を見ない (connect の綴りは相手に残らない)。`Options.base` は connect 系でも B の置き場として使う
- この B が普段の B と違う所になる時は、もう 1 つの B として使う (自動の置き場で 1 つのプロセスが複数の B を使うのはこの時だけ)
- 相手の `/tmp` が隔離されている場合 (systemd の `PrivateTmp` 等) は選択肢にしない (procB を先に試すので Linux ではまず起きない)。辿れるかは結果の `Spelling` の `usable_with_private_tmp` で分かる

## D と E

| | D | E |
|---|---|---|
| 置く所 | B の中 | resolve の E と thread-cwd・at の E は D の中。既定の connect の link-file の E は B の直下 |
| 作る単位 | (プロセス, B) ごとに 1 つ。作るのは、綴りを残す bind (thread-cwd・at を含む) と `resolve_for_connect` だけ | resolve ごと。thread-cwd・at と既定の connect の link-file は呼び出しごと |
| 名前 | 乱数 10 文字 | resolve の E はプロセスの中のカウンタ (36 進。D が (プロセス, B) ごとに一意なので短くてよい)。thread-cwd・at の E と B の直下の E は乱数 10 文字 |
| mode | 0711 (`/tmp` の B の綴りを別の uid が辿れるように) | 無し (symlink の mode は辿る権限に効かない) |
| 生きている間 | プロセスが flock (共有ロック) を掛けた fd を持ち続ける | resolve の E は消さない |
| 片付け | sockat はしない。`sweep()` を呼んだ時だけ、ロックの外れた D を消す | resolve の E は `cleanup`。呼び出しごとの E は呼び出しの中で unlink |

D の作り方:

1. B の fd を基準に、乱数の名前で `mkdirat(B の fd, 名前, 0700)` する。`EEXIST` なら名前を引き直し、16 回で打ち切る
2. 作った直後に `fchmodat(B の fd, 名前, 0711)` で mode をそろえ、それから `O_DIRECTORY | O_NOFOLLOW` で開いて `fstat` で実ディレクトリ・持ち主が自分を確かめる。そろえられない・開けない時は、作った自分の空のディレクトリを消して次の置き場へ
3. その fd に flock (共有ロック) を掛けて持ち続ける。fd は close-on-exec
4. 名前で `lstat` した `(st_dev, st_ino)` が fd と同じかを確かめる。違えば (1 と 3 の間に他のプロセスの `sweep()` が消した) fd を閉じて 1 から作り直す

- `sweep()` と `sweep_base(path)` は、B の中の D に `flock(LOCK_EX | LOCK_NB)` が取れたら持ち主が死んだとみなして消す (対象の B は [SPEC の `sweep`](SPEC-ja.md#sweep))。B の直下の E (既定の connect の物) には触らず、symlink でない物がある D は残す
- 乱数は英数 62 種の文字で、OS の安全な乱数から作る。名前の作り方は 3 言語でそろえる
- D の名前をカウンタにしないのは、プロセスが終わった後に同じ PID・同じ fd 番号の別のプロセスが現れても綴りが同じにならないため
- D が生きている間は flock で守られ、B と D が 0711 なので、綴りが後で無関係なファイルに当たらない (procB はプロセスが終われば辿れない、実パスの綴りは D が消えるまで同じ所を指す)
- systemd-tmpfiles (v242 以上) はロックの掛かったディレクトリを配下ごと掃除しない
- 既定の connect は D を作らない (D と flock の fd がプロセスに残らないように)

## 経路

節の順は [SPEC の経路の名前](SPEC-ja.md#経路の名前)の表の順。試す順は [bind の順](SPEC-ja.md#bind-の順)と [connect の順](SPEC-ja.md#connect-の順)。

### standard

- やり方: 標準にそのまま渡す ([SPEC の短いパス](SPEC-ja.md#短いパス))
- 使う時: パスが標準に渡す長さ以下。bind も connect も最初
- 届く長さ: パス全体が標準に渡す長さ以下
- 綴りの性質: 絶対パスは `Original`、相対パスは `CwdRelative`

### link-dir

- やり方: D の中にソケットのディレクトリの realpath を指す E を作り、`B/D/E/<ファイル名>` で bind する。E は `cleanup` まで残す。bind して失敗した時は ([経路の失敗の扱い](#経路の失敗の扱い))、E をその場で消してからエラーを返す
- 使う時: bind の順の 2 (procB) と 3 (実パス)。`resolve_for_bind` が先に選ぶ綴り。procB と実パスで試しても `skipped` には 1 件 (理由は最後の物)
- 使えない時: 綴りが sockaddr に入らない、B・D・E を作れない、procB では `/proc` を使えないか `usable_cross_uid`
- 届くファイル名: sockaddr に入る長さ − (B の綴り + D + E + 区切り 3)。procB の Linux はおよそ 70 ([SPEC の未確定](SPEC-ja.md#未確定))
- 綴りの性質: `Linked` (`removable` は true)

### link-file

- やり方: ソケットのファイルの綴り (相対パスなら cwd を前に付ける) を指す E を作り、その綴りで bind / connect する
  - bind と `resolve_for_bind`・`resolve_for_connect`: E は D の中、綴りは `B/D/E` (B の綴りは「[綴りの形](#綴りの形)」の procB か実パス)。E は `cleanup` まで残す。bind して失敗した時は (エラーを返す時も、下の見分け方で次へ進む時も)、E をその場で消す
  - 既定の connect 系: D を作らず、B の直下に乱数の名前の E を作り、B の実パスの `B/E` で connect し (procB は使わない。B は `/tmp` が先なので短い)、connect の後すぐ E を unlink する。片付けは unlink だけで待ちは入らない
- 使う時: bind の順の 4 (実パスだけ。procB の link-file は無い: `/proc` のある Linux は bind が symlink を辿らない)。connect の順の 4。`resolve_for_bind` は bind が symlink を辿ると実測した OS (macOS・NetBSD) だけで使い、未確認の OS では使わない (resolve の時点では bind しないので、下の見分け方を使えない)。`resolve_for_connect` はこれだけを使い、使えなければ `ENAMETOOLONG`
- 使えない時: 綴りが sockaddr に入らない、B・D・E を作れない。bind では、カーネルが symlink を辿らなかった (下)
- 届くファイル名: 綴りにファイル名が出ないので、ファイル名の長さによらない (綴りが sockaddr に入る長さ以内。元のパス全体は PATH_MAX まで)
- 綴りの性質 (bind): `Linked` (`removable` は false: 綴りで unlink しても、最後の symlink は辿られず E が消える)
- connect は最後の要素の symlink をいつも辿る

bind が最後の要素の symlink を辿るかの見分け方:

- 辿らないと実測した OS (Linux / Android、FreeBSD 15、OpenBSD 8、illumos (OmniOS)) では試さない。辿るのは macOS 26 と NetBSD 11 (実測 2026-11-19、[findings](findings/2026-11-19-bind-through-file-symlink.md))
- 他の OS では (既定の `bind` と `bind_ex`)、bind が失敗した時に元のパスを `lstat` し、物があればそのエラー (`EADDRINUSE` 等) を返して次は試さない。無いか確かめられなければ、カーネルが辿らなかったとみなしてこの経路を使えないとして次へ進む (`skipped` に入り、作った E は残さない)。本当の失敗なら次の経路でも同じ失敗になり、そこで返る
- 元のパスの最後の要素に bind の前から symlink が置かれていた時に bind がそれを辿るのは標準の bind の性質で、sockat は確かめない

### thread-cwd

- やり方: [thread-cwd と at の手順](#thread-cwd-と-at-の手順)で、[使い捨てのスレッド](#使い捨てのスレッド)の cwd を D に移して `E/<ファイル名>` で bind する。Linux / Android は `unshare(CLONE_FS)` → `fchdir(D の fd)`、Apple の OS は `pthread_fchdir_np(D の fd)`
- 使う時: bind の順の 5。Linux / Android・Apple の OS
- 使えない時:
  - Linux / Android: seccomp の filter が掛かっているか確かめられない (`prctl(PR_GET_SECCOMP)` が 0 以外か失敗)、`unshare` が断られた
  - Apple の OS: `pthread_fchdir_np` が無い・失敗した
  - スレッドを作れない
  - NetBSD / OpenBSD / illumos
  - B も D も作れない、綴りが sockaddr に入らない
- 届くファイル名: sockaddr に入る長さ − (E の名前 + 1)
- 綴りの性質: `Dangling`

### at

- やり方: [thread-cwd と at の手順](#thread-cwd-と-at-の手順)で、スレッドを使わず `bindat(D の fd, E/<ファイル名>)` で bind する
- 使う時: bind の順の 5。FreeBSD
- 使えない時: B も D も作れない、綴りが sockaddr に入らない
- 届くファイル名: sockaddr に入る長さ − (E の名前 + 1)
- 綴りの性質: `Dangling`

### proc-direct

- やり方: ソケットのディレクトリを開き、`/proc/self/fd/<fd>/<ファイル名>` で connect する
- 使う時: connect の順の 2。`/proc` を使える Linux / Android
- 使えない時: ソケットのディレクトリを開けない、`/proc/self/fd/<fd>` を stat で引けない、綴りが sockaddr に入らない
- 届くファイル名: およそ 90 (fd の桁で変わる)
- bind は使わない (綴りの fd の番号が後で使い回され、別のディレクトリの同名ファイルに当たる)

### relative

- やり方: cwd からの相対パスで connect する。文字列を書き直すだけで `chdir` しない ([相対パスの作り方](#相対パスの作り方))
- 使う時: connect の順の 2。元のパスが絶対パス。`/proc` を使えない Linux / Android、Apple の OS、NetBSD / OpenBSD / illumos / その他の Unix
- 使えない時: 相対パスが sockaddr に入る長さを超える、作った綴りのディレクトリが元と `(st_dev, st_ino)` で一致しない、cwd が既に変わっている
- 届く長さ: 相対パスが sockaddr に入る長さ以内
- bind は使わない (cwd が変わると綴りが別の所に当たる)

### widened

- やり方: `sun_len` とアドレス長を `2 + パスの長さ` にした sockaddr で、元のパス、無理なら相対パスを渡して connect する
- 使う時: connect の順の 2 で relative の次。Apple の OS。パスが 253 バイト以内
- 使えない時: カーネルが `EINVAL` / `ENAMETOOLONG` を返した
- 届く長さ: 元のパスか相対パスが 253 以内
- bind は使わない (アドレスが途中で切れ、CPython の `getsockname` や Go の `net.FileConn` の読む側を壊す)

### at-direct

- やり方: ソケットのディレクトリを開き、`connectat(fd, <ファイル名>)` で connect する。E を通さない
- 使う時: connect の順の 2。FreeBSD
- 使えない時: ソケットのディレクトリを開けない、ファイル名が 103 バイトを超える
- 届くファイル名: 103
- bind は使わない (綴りがファイル名だけになり、後でプロセスの cwd の同名ファイルに当たる)

### thread-cwd-direct

- やり方: ソケットのディレクトリを開き、[使い捨てのスレッド](#使い捨てのスレッド)の cwd をそこへ移して (手段は [thread-cwd](#thread-cwd) と同じ)、ファイル名で connect する。D も E も要らない (connect の綴りは相手に残らない)
- 使う時: connect の順の 3 (stream と DGRAM)。Linux / Android・Apple の OS
- 使えない時: [thread-cwd](#thread-cwd) の「使えない時」のうち B・D によらないもの、ソケットのディレクトリを開けない、ファイル名が sockaddr に入る長さを超える
- 届くファイル名: sockaddr に入る長さ

## thread-cwd と at の手順

resolve の綴りが収まらない時の bind が使う。

1. プロセスの D を fd で掴んだまま基準にする (B も D も作れなければ thread-cwd・at は使えないとして飛ばす)
2. D の中に、ソケットのディレクトリの realpath を指す乱数の名前の E を `symlinkat` で作る
3. D の fd を基準に `E/<ファイル名>` で bind する (下の手段)
4. E を、成功でも失敗でもすぐ消す (自分が作れた時だけ)。綴りは `Dangling`

| 手段 | 基準にする fd (thread-cwd・at は D、thread-cwd-direct はソケットのディレクトリ) の使い方 | OS |
|---|---|---|
| thread-cwd | 使い捨てのスレッドで cwd を移す (`unshare(CLONE_FS)` → `fchdir`) | Linux / Android |
| thread-cwd | 使い捨てのスレッドで `pthread_fchdir_np(fd)` | Apple の OS |
| at | `bindat` に fd を渡す (スレッドを使わない) | FreeBSD |

- 綴りの中に既に消した乱数の名前 E があるので、後で fd の番号が使い回されても、cwd に同じ名前の物がたまたまある以外は当たらない (綴りは他の利用者に見えうるので、プロセスの cwd が他人も書ける場所だと、見て作り直されうる。元のパスで消せば当たらない)
- E はソケットのディレクトリの realpath を指すので、E を作った後のディレクトリの rename や symlink の張り替えは反映されない
- 途中でプロセスが死ぬと E が D に残る (D と一緒に OS の掃除で消える)

## 使い捨てのスレッド

[thread-cwd](#thread-cwd) と [thread-cwd-direct](#thread-cwd-direct) が使う。

- スレッドは sockat が作った使い捨てで、使い終わったら捨てる。呼び出し元のスレッドの cwd には触らない (`pthread_fchdir_np(-1)` で戻す形は、呼び出し元がスレッドに付けた cwd を消しうる)
- 呼び出し元は使い捨てのスレッドが終わるまで待ってから E を片付け、fd を閉じる。待つのが割り込まれても (Python の `KeyboardInterrupt` 等)、スレッドが終わるまでは片付けない (先に閉じた fd の番号が使い回されると、スレッドが無関係なディレクトリに移って bind / connect する)
- Linux / Android で seccomp の filter が掛かっている時は `unshare` を呼ばない。filter がプロセスの kill (SIGSYS) で断る環境 (systemd の `SystemCallFilter=` の既定) がある
- `unshare` の後の `fchdir` の失敗 (`EACCES` 等) は本当の失敗として返す
- `pthread_fchdir_np` は libSystem の非公開 API (`__pthread_fchdir` syscall)。実行時に引き、無ければ次へ進む

## 相対パスの作り方

[relative](#relative) が使う。

1. パスが cwd の綴り (`getcwd`、または `stat` の `(st_dev, st_ino)` が `.` と一致する `$PWD`) で始まれば、区切り単位でそれを削る
2. 1 で sockaddr に入る長さ以内にならない時だけ、ソケットのディレクトリと cwd を `realpath` で実パスにし、`..` で上る綴りを作る
3. 短い方を使う。使う前に相対パスのディレクトリと元のディレクトリの `(st_dev, st_ino)` が同じこと、cwd の `(st_dev, st_ino)` が 1 の前と同じことを確かめる。違えばこの経路は使えない
4. connect の後に cwd の `(st_dev, st_ino)` が変わっていたら、結果を捨てて一般のエラーを返す (別の所へ届くことは無い)

## 経路の失敗の扱い

- 経路が実際に bind / connect して失敗したら (`ENOENT`、`EADDRINUSE`、`ECONNREFUSED` 等)、そのエラーを返し、次の経路を試さない
- その時、その呼び出しで作った E は返す前に消す (link-dir・link-file・thread-cwd・at。既定の connect の link-file も)。D と B は残す
- 次へ進むのは、経路自体が使えない時だけ (各経路の節の「使えない時」)
  - 綴りが収まらない
  - B・D・E を作れない
  - thread-cwd・at・thread-cwd-direct の手段が使えない
  - `/proc` を使えない
  - widened でカーネルが広げた sockaddr を受け付けない
  - link-file の bind が失敗し、元のパスに物が無いか確かめられない (カーネルが symlink を辿らなかったとみなす)
  - relative で、作った綴りのディレクトリが元と `(st_dev, st_ino)` で一致しない、または cwd が既に変わっている
  - `usable_cross_uid` を満たす B が無い
- ディレクトリが無い時はどの OS でも `ENOENT`。ディレクトリを先に引くので、長さの判定より前に決まる
