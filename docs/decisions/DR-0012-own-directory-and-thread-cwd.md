# DR-0012: 長いパスは自分専用のディレクトリ D を fd で掴み、その中の乱数の symlink R を通して bind / connect する

- Status: Active
- Date: 2026-11-19

## Context

- カーネルは bind に渡された綴りを覚えて `getsockname` / `getpeername` で返し、上のライブラリや利用者はその綴りで unlink / stat する (Python の asyncio の後始末、Go の `UnixListener.Close`、利用者の `remove_file(local_addr)` 等)
- 綴りは後で別の文脈で解決され直し、無関係なファイルに当たりうる

| bind の綴り | 後で解決すると |
|---|---|
| `/proc/self/fd/<n>/<ファイル名>` | 閉じた fd の番号が使い回され、別のディレクトリの同名ファイルに当たる (sockat-rs が docker で実測、無関係なファイルを消した) |
| ファイル名だけ (スレッド cwd / fork / bindat) | プロセスの cwd の同名ファイルに当たる (sockat-py が macOS で実測) |
| cwd からの相対パス | cwd が変わると別の場所に当たる |

- Apple の OS で広げた sockaddr で bind したソケットのアドレスは途中で切れ、読む側を壊す (CPython の `getsockname` が後ろに無関係なバイトを付けて asyncio の後始末が落ちる。Go の `net.FileConn` で相手の `RemoteAddr` が nil になり `.String()` が panic する)
- 置き場に名前で辿る symlink を置く形は、置き場の安全 (sticky 等) を確かめ、安全でない置き場には別の形を用意し、候補を順に試す処理が要る
- fork は副作用 (子が全 fd の複製を持つ、`SIGCHLD`、`pthread_atfork` 等) があり、最後の手にしたい

## Decision

### 中心の経路

1. 置き場を開いて fd で掴み、`sockat.` (ソケットのディレクトリでは `.sockat.`) + 英数 62 種 10 文字 (`EEXIST` で引き直し 16 回まで) の名前で 0700 の D を作る
2. D を fd で開き (Linux は `O_PATH | O_DIRECTORY | O_NOFOLLOW`、他は `O_DIRECTORY | O_NOFOLLOW`)、`fstat` で「ディレクトリ・持ち主が実効 uid・group と other に権限が無い」を確かめ、0700 にそろえる (Linux は `chmod("/proc/self/fd/<fd>")`、他は `fchmod`)
3. D の中に、ソケットのディレクトリの realpath を指す乱数の名前 (62 種 10 文字) の symlink R を `symlinkat` で作る。D の中に他のディレクトリは挟まない
4. D の fd を基準に `R/<ファイル名>` で bind / connect する
5. R は自分が作れた時だけ消す。D は手順 2 の確認が通り、名前の `(st_dev, st_ino)` が fd と一致する時だけ消す。成功でも失敗でも片付ける

| D の fd を基準にする手段 | OS |
|---|---|
| 使い捨てのスレッドで cwd を D に移す (`unshare(CLONE_FS)` → `fchdir`) | Linux / Android |
| 使い捨てのスレッドで `pthread_fchdir_np(Dfd)` | Apple の OS |
| `bindat` / `connectat` に D の fd を渡す (スレッドを使わない。kawaz 承認 2026-11-19、実機未確認) | FreeBSD |
| /proc 版: `/proc/self/fd/<Dfd>/R/<ファイル名>` (スレッドを使わない) | `/proc` を使える Linux / Android |
| fork した子が `fchdir(Dfd)` (bind だけ) | 全部 |

- スレッド cwd は、seccomp の filter が掛かっているか確かめられない時 (`prctl(PR_GET_SECCOMP)` が 0 以外か失敗)、`unshare` が断られた時、`pthread_fchdir_np` が無い・失敗した時、スレッドを作れない時、NetBSD / OpenBSD / illumos では使えない
- 呼び出し元のスレッドには触らない

### D の置き場

| 順 | 置き場 |
|---|---|
| 1 | `${TMPDIR:-/tmp}` (相対パスも可) |
| 2 | `/tmp` (1 で作れない時だけ) |
| 3 | ソケットのディレクトリ (2 でも作れない時だけ。名前は `.sockat.XXXXXXXXXX`) |

- 置き場の安全と長さは問わない
- どこにも作れない時、bind は D 無しの fork (子がソケットのディレクトリの fd に `fchdir` し、そこに作った R `.sockat.XXXXXXXXXX` を通して `.sockat.XXXXXXXXXX/<ファイル名>`。R も作れなければ `ENAMETOOLONG`)、connect 系は予備の経路へ。スレッド cwd と /proc 版は D 無しの形を試さない
- ソケットのディレクトリに作る物 (D と D 無しの fork の R) は名前の先頭にドットを付ける。利用者のディレクトリなので、残っても sockat の物と分かり目立たない (kawaz 裁定)
- 置き場の 3 番目と、どこにも作れない時の扱いは kawaz 承認 (2026-11-19)

### 試す順番

| 順 | bind | `connect` / `connect_nonblocking` | `connect_any` 系 |
|---|---|---|---|
| 1 | 標準に渡す長さ以下なら標準にそのまま | 同じ | 同じ |
| 2 | 中心の経路 (スレッド cwd。FreeBSD は bindat) | 中心の経路 (スレッド cwd。FreeBSD は connectat) | 同左 |
| 3 | 中心の経路の /proc 版 (`/proc` を使える Linux / Android) | 同左 | 同左 |
| 4 | 中心の経路を fork で | 予備の経路 | 予備の経路 |
| 5 | `ENAMETOOLONG` | `ENAMETOOLONG` | fork (ソケットのディレクトリの fd とファイル名) |

| OS | connect 系の予備の経路 |
|---|---|
| Linux / Android (`/proc` あり) | /proc → fd で掴む形 (D の中のファイルを指す symlink) → symlink |
| Linux / Android (`/proc` 無し) | 相対パス → symlink |
| Apple の OS | 相対パス → 広げた sockaddr → symlink |
| FreeBSD | connectat (ソケットのディレクトリの fd とファイル名) |
| NetBSD / OpenBSD / illumos | 相対パス → symlink |

- bind は /proc (D を通さない形)・相対パス・広げた sockaddr・置き場の symlink を使わない
- connect の予備の経路は綴りにランダムな部品を挟まない (connect した側のソケットは bind されず、綴りが相手に残らない)

理由:

- 綴りの中に、自分しか知らず既に消した R があるので、後で fd の番号が使い回されても cwd が何でも当たらない
- D を fd で掴むので、置き場が安全でなくても深くても使える。名前を差し替えられても fd は変わらず、作ってから開くまでのすり替えは `fstat` で弾く
- スレッド cwd と /proc 版は副作用が無い (sockat-go の実測: peer の pid は呼び出し元のまま、fd の複製も無い、並行する `getcwd` は変わらない)。`connect` も fork 無しで届く
- seccomp の filter はプロセスの kill (SIGSYS) で `unshare` を断ることがある (systemd の `SystemCallFilter=` の既定) ので、filter が掛かっていれば呼ばない
- `pthread_fchdir_np(-1)` で戻す形は、呼び出し元がスレッドに付けた cwd を消しうる。使い捨てのスレッドなら触らずに済む
- bind が使わない経路は、綴りが後で無関係なファイルに当たる (/proc、相対パス)、アドレスが切れて読む側を壊す (広げた sockaddr)、中心の経路で足りる (置き場の symlink)

悪い面:

- ファイル名の上限が `R/` の 11 バイト分短い (Linux / illumos 96、Apple の OS / BSD 92。/proc 版はおよそ 79、D 無しの fork は 88 / 84)
- 長いパスの bind / connect のたびに D と R を作って消す
- 途中でプロセスが死ぬと D や R が残る (置き場に `sockat.XXXXXXXXXX`、ソケットのディレクトリに `.sockat.XXXXXXXXXX`)
- R はソケットのディレクトリの realpath を指すので、R を作った後のディレクトリの rename や symlink の張り替えは反映されない
- `pthread_fchdir_np` は libSystem の非公開 API で、将来消えうる (消えたら次へ進む)
- 上のライブラリが元のパスのソケットのファイルを自動で消すことは効かない (kawaz が許容。消すのは `_ex` の `discard()`)

## Alternatives Considered

- 案 A: 置き場の安全 (sticky 等) を確かめ、安全な置き場には symlink、安全でない置き場には fd で掴む形を作り、候補を順に試して一番良い置き場を探す
  - 不採用理由: D を fd で掴めば置き場の安全も長さも関係しない。処理と試験が増えるだけ
- 案 B: bind の綴りにランダムな部品を挟まない (ファイル名だけ、`/proc/self/fd/<fd>/<ファイル名>`)
  - 不採用理由: 後で解決すると無関係なファイルに当たる。消すのは利用者のコードでなく上のライブラリで、利用者が避けられない
- 案 C: D の中に `s` 等のディレクトリを挟む
  - 不採用理由: 綴りが伸びるだけで、R だけで何にも当たらない (kawaz 裁定)
- 案 D: Apple の OS の bind で広げた sockaddr を使う
  - 不採用理由: アドレスが切れて CPython / Go の標準を壊す。bind は fork でも相手から見える副作用が無い ([DR-0010](DR-0010-fork-bind-listen-by-parent.md))
- 案 E: スレッド cwd を使わず fork だけにする
  - 不採用理由: fork の副作用があり、`connect` は fork しないので届かない範囲が残る

## Consequences

- 試験 (中心の経路を強制して): プロセスの cwd が変わらない、元のパスにソケットができ届く、返る綴りを unlink / stat しても無関係なファイルに当たらない、片付けの後に置き場に何も残らない、差し替えたディレクトリを使わず中身も消さない、`TMPDIR` に作れない時は `/tmp`、それも作れない時はソケットのディレクトリ、スレッド cwd が使えない時は /proc 版、それも使えない時は bind は fork・connect は予備の経路
- 各言語の実装は経路を作り直す (bind の /proc・symlink・相対パスの経路を外し、中心の経路を足す)

## 未確定

kawaz 未確認。SPEC はこの形で書く。

- `connect_any` 系の fork と FreeBSD の connect の予備の経路は D を通さない (ソケットのディレクトリの fd とファイル名。connect の綴りは相手に残らないので今の経路のまま)

## 関連

- [docs/SPEC-ja.md](../SPEC-ja.md) の「長いパスの経路と試す順番」「どこから届かなくなるか」「長いパスで標準と違う点」「実装が確かめる試験の観点」
- 裁定: kawaz (2026-11-19)
- [DR-0007](DR-0007-connect-any-is-opt-in.md)、[DR-0010](DR-0010-fork-bind-listen-by-parent.md)
