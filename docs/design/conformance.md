# 適合試験

同じ入力で、全言語の実装が同じ結果 (通った経路、通った B、綴りの性質、飛ばした経路、errno、置き場に残した物) になることを機械で確かめる。統括のセッションが各言語の報告を読んで突き合わせる代わりに、差が出た所だけを人が判断する。

## 全体

| 部品 | 置き場 | 役目 |
|---|---|---|
| 場面の表 | ハブの `conformance/cases.json` | 何を試すか (操作、パスの形、前もって作る物) |
| 流すスクリプト | ハブの `conformance/run.py` | 場面ごとに環境を作り、各言語の CLI を起こし、結果を集めて比べる |
| 言語の一覧 | ハブの `conformance/langs.json` | 各言語の CLI の起こし方。`cwd` はリポの場所 (`cmd` の `{repo}` と、`/` を含む相対パスの `cmd[0]` の基準。CLI の cwd ではない)、`cmd` は起こすコマンド (まだ無ければ `null` で「未実装」)、`build` は CLI を作るコマンド (`just conformance` が流す前に各言語のリポで走らせる。`--no-build` で止める)、`lacks` はその言語が作らない経路の名前の並び (各言語の README の OS × 経路の表と同じ。比べ方を分けるのに使う)、`linux` は Linux のコンテナでの起こし方 ([コンテナの作り方](#コンテナの作り方)) |
| 試験用 CLI | 各言語のリポ | 1 回の bind / connect を `_ex` で試し、結果を JSON で出す。公開しない |
| Linux の条件 | ハブの `conformance/linux/` | 経路を強制する場面で使う seccomp の profile ([経路を強制する場面](#経路を強制する場面)) |

- ハブの `just conformance` で流す。差があれば終了コード 1 で、場面 × 言語の表を出す
- `--on host` は手元で流す場面だけ、`--on linux` は Linux のコンテナで流す場面だけ。既定は両方。`--verbose` は差が無くても場面ごとの各言語の `route`・`base`・`spelling`・`skipped` 等を出す
- 比べるのは同じマシン・同じ環境で動かした言語どうし。OS や seccomp で結果が変わるのは正しいので、場面の表に OS ごとの期待値は持たない (全言語で変わらない値だけ `expect` に書ける)

## 試験用 CLI の決まり

起こし方: スクリプトが場面ごとに 1 回、CLI のプロセスを起こす。cwd・環境変数 (`TMPDIR`、`XDG_RUNTIME_DIR` 等)・umask はスクリプトが整えてから起こす。CLI は cwd も環境変数も変えない。

入力: 標準入力に JSON を 1 つ。

```json
{ "op": "bind", "path": "<渡すパス>", "usable_cross_uid": false, "base": null }
```

| 項目 | 中身 |
|---|---|
| `op` | `bind` か `connect` |
| `path` | ライブラリに渡すパス (相対パスもある)。そのまま渡す |
| `usable_cross_uid` | `Options.usable_cross_uid` (SPEC の「`Options`」)。省略時は `false` |
| `base` | `Options.base` に渡すパス。省略時と `null` は指定しない |

出力: 標準出力に JSON を 1 つ。

```json
{ "ok": true, "error": null, "route": "link-dir", "base": "proc", "spelling": { "kind": "Linked", "removable": true, "until": "Process", "usable_cross_uid": false, "usable_with_private_tmp": true }, "skipped": ["standard"] }
```

| 項目 | 中身 |
|---|---|
| `ok` | bind / connect が通ったか |
| `error` | 失敗の時、errno の名前 (`ENAMETOOLONG`、`ENOENT` 等)。引数の誤りは `invalid-argument`、一般のエラーは `general` |
| `route` | 通った経路の名前。失敗の時は実際に bind / connect して失敗した経路の名前か `null` (SPEC の「診断」) |
| `base` | bind の診断の `base` (通った B の綴り。`proc`・`sockdir`・`runtime`・`tmpdir`・`tmp`・`given` のどれかで、`given` は入力の `base` に渡した B。SPEC の「診断」)。綴りが B を通らなかった時 (standard・thread-cwd・at)、connect、失敗の時は `null` |
| `spelling` | bind が通った時の綴りの性質 (下の形)。connect と失敗の時は `null` |
| `skipped` | 飛ばした経路の名前の並び (試した順)。`reason` は約束しないので出さない |

`spelling` は SPEC の `Spelling` を JSON にした形。`kind` は値の名前で、`Linked` だけが属性を持つ。項目の名前と値は SPEC の Rust の名前のまま (言語によらず同じ綴り)。

| `kind` | 他の項目 |
|---|---|
| `Original` | 無し |
| `CwdRelative` | 無し |
| `Linked` | `removable` (bool)、`until` (`Process` か `Cleanup`)、`usable_cross_uid` (bool)、`usable_with_private_tmp` (bool) |
| `Dangling` | 無し |

- bind は `bind_ex`、connect は `connect_ex` (各言語の名前。Python は `sockat.ex`、Go は `ListenEx` / `DialEx`) に、入力の `Options` を渡して呼ぶ。`Options` を全部既定にした `_ex` は既定の操作と同じ経路を試すので、既定の操作は呼ばない
- `remove()` と `cleanup()` を呼ばない (置き場に残す物をスクリプトが見る)
- bind が通ったら、CLI は listener を閉じずにプロセスを終える (終了で閉じる)。閉じる時にファイルを消す言語の標準 (Go の短いパス等) があり、閉じると言語の差を拾ってしまうため
- connect が通ったら、1 バイト `x` を送ってから閉じる
- 終了コード: 結果を出したら 0 (connect の後に `x` を送れなかった時も、結果を出して 0。届いたかはスクリプトが見る)。入力の JSON が不正なら標準出力に何も出さず 2。それ以外はスクリプトが「壊れた」とみなす
- 標準出力は結果の JSON 1 行だけ。ビルドの出力等は標準エラーへ
- `error` の名前: errno の名前は C の名前。同じ値に名前が 2 つあるものは `EAGAIN`・`EOPNOTSUPP`・`EDEADLK` に寄せる。名前の分からない errno は `errno-<番号>`。errno を持たない引数の誤りは `invalid-argument`、errno を持たないそれ以外は `general`
- その言語で作れない経路 (`langs.json` の `lacks`) は、そこに来たら `skipped` に入れて次へ進む (SPEC の「各実装に求めること」)

## スクリプトが確かめること

CLI の出力に加えて、CLI が終わった後に:

| 確かめること | 中身 |
|---|---|
| ソケットのファイル (`file`) | bind が通った時、元のパスにソケットのファイルがある |
| B の中に残した物 (`left`) | B の中に増えた D と E。B は `/tmp` の `sockat-<uid>`、`$TMPDIR` の `sockat-<uid>`、`$XDG_RUNTIME_DIR` の `sockat`、ソケットのディレクトリの `.sockat.<乱数 10>`、`base` に渡した所 |
| B の外の残骸 (`residue`) | `TMPDIR`・`XDG_RUNTIME_DIR` の直下と、`/tmp` の `sockat` で始まる名前のうち、B の外に増えた物 |
| `{root}` の木に増えた物 (`created`) | B の外に増えた物 (ソケットのファイル等) |
| 届いたか (`received`) | connect が通った時、スクリプトが待ち受けていた側に `x` が届いた |

`left` は場所と名前を記号にした文字列の並び。言語ごとに場所と乱数が違っても比べられるようにする。

| 残した物 | 形 |
|---|---|
| D | `<B>/<D>/` |
| D の中の E | `<B>/<D>/<E> -> <指す先>` |
| B の直下の E | `<B>/<E> -> <指す先>` |

- `<B>` は `/tmp/sockat-<uid>`・`{tmpdir}/sockat-<uid>`・`{xdg}/sockat`・`{long}/.sockat.<rand>` のように、置き場の placeholder と、uid・乱数を記号にした名前。`base` の B は渡したパスの placeholder の形
- 指す先は placeholder の形 (link-dir は `{long}`、link-file は `{long}/s.sock`)
- スクリプトは場面の後に、その場面で B の中に増えた物を消す (B は消さない。`/tmp` の B に場面ごとの D が溜まらないように)
- `/tmp` の B は前後の差で見るので、同じ時に他で sockat を動かすと誤った差が出うる

## 言語どうしの比べ方

| 場面 | 比べ方 |
|---|---|
| どの言語の `route` も、他の言語の `lacks` に入っていない | 全言語で比べる |
| ある言語の `route` が、他の言語の `lacks` に入っている (その経路を「きっかけの経路」と呼ぶ) | 「`lacks` のうちきっかけの経路に当たる部分」が同じ言語どうしで組を作り、組の中で比べる。加えて、きっかけの経路に来るまでの経過は組をまたいで全言語で比べる |

- 組の中で多数派と違う言語が「差」。多数派が決まらなければ組の全員が「差」
- きっかけの経路に来るまでの経過は、`skipped` のうち最初のきっかけの経路より前の部分 (きっかけの経路を `route` にした言語は `skipped` 全部)。どの言語もそこまでは同じ経路を同じ順で試しているはずなので、組によらず全言語の多数派と違う言語が「差」。詳細の表では `skipped (きっかけより前、組をまたいで)` の行に出る
- 組を分けた場面では、場面の `expect` はきっかけの経路を作れる言語にだけ当てる。作れない言語には暗黙の期待 (残骸が無い等) と、作れないきっかけの経路が `skipped` に入っていることを当てる
- 自分の `lacks` に入った経路を `route` にした言語は、どの場面でも「期待違い」
- 組を分けた場面は、結果の表の後に組と一緒に出す

## 場面の表 (`conformance/cases.json`)

```json
{ "name": "long-absolute-bind-cross-uid", "op": "bind", "usable_cross_uid": true, "path": "{long}/s.sock", "cwd": "{root}", "setup": ["mkdir {long}"], "expect": { "ok": true, "file": true } }
```

- `{root}` はスクリプトが場面ごとに作る空のディレクトリ (`$TMPDIR` の下)。`{long}` は `{root}` の下の、パス全体が 150 バイト以上になる深いディレクトリ。`{short}` は `/tmp/sockat-conformance-<8 桁>` に作る `{root}` を指す symlink (`$TMPDIR` が深い環境でも短い絶対パスを作るため。毎回消す)。`TMPDIR` と `XDG_RUNTIME_DIR` は場面ごとの空のディレクトリ (0700) で、`{tmpdir}`・`{xdg}` で書ける
- 場面の名前は英語の kebab-case
- `usable_cross_uid` と `base` は書いた時だけ CLI の入力に渡す (`base` は placeholder を置き換えて)。省略時は入力に入れない (CLI の既定)
- `setup` はスクリプトが CLI を起こす前にすること。`"動詞 パス"` の文字列で、動詞は `mkdir` (途中も作る)・`touch`・`listen` (待ち受けのソケット)・`stale-socket` (bind してすぐ閉じた、誰も listen していないソケット)。シェルには渡さない
- `expect` は全言語・全環境で変わらない値だけを書く
- `expect` に書かなくても、全場面で次を期待する: `residue` が空、bind が通ったら元のパスにソケットがある、connect が通ったら `x` が届く、失敗と connect では `spelling` が `null`、connect では `base` が `null` で `left` が空 (D を作らず、B の直下の E は connect の後に消す)、失敗した bind では `left` に E が無い (実際に bind して失敗した経路は作った E を消してからエラーを返す。初めての bind でできた D は残ってよいので、`left` を空とは期待しない)。経路を試す前の失敗 (ディレクトリが無い、途中がファイル、引数の誤り) は `route` が `null` で `skipped` が空
- 値が 1 つに決まらないが満たすべき決まりも全場面で確かめる: 通った bind の `spelling` が `Linked` なら `left` に E が 1 つ (CLI は `cleanup` を呼ばないので綴りの E が残る)、`Original`・`CwdRelative`・`Dangling` なら `left` に E が無い。`usable_cross_uid` を渡した bind の `spelling` が `Linked` なら、その `usable_cross_uid` が true (満たさない綴りに落とさない)
- 環境で変わる値 (`route`・`base`・`spelling` 等) は言語どうしの比較だけで見る

最初の場面 (経路を強制しなくても作れるもの):

| 場面 | 確かめること |
|---|---|
| 短い絶対パスの bind | `route` が `standard`、`spelling` が `Original`、`left` が空 |
| 短い相対パスの bind | `spelling` が `CwdRelative` |
| 長い絶対パスの bind | 通る、ソケットが元のパスにある |
| 長いパスでディレクトリが無い | `ENOENT`、`route` が `null`、`skipped` が空 |
| 長いパスの途中がファイル | `ENOTDIR` |
| 長いパスの bind 先に既にファイルがある | `EADDRINUSE`、`route` が実際に bind した経路 |
| 長いパスへの connect | 通る、`x` が届く、`left` が空 |
| 長いパスの、誰も listen していないソケットへの connect | `ECONNREFUSED` |
| 最後がファイル名でない長いパス、先頭以外に NUL | `invalid-argument`、何も作らない |
| `usable_cross_uid` を渡した、長い絶対パスの bind | 通る。`spelling` が `Linked` なら `usable_cross_uid` が true |
| 長いファイル名 (100 バイト) の bind | thread-cwd・at (ファイル名 92〜96 まで) を超える。bind が symlink を辿る OS (macOS・NetBSD) は link-file で通り、他は `ENAMETOOLONG` (link-dir の綴りも収まらない) |
| `base` に `{root}/b` を渡した、長い絶対パスの bind | B が `{root}/b` になり、`left` がその中に出る。B を通る綴りで届いた時の `base` は `given` (届くかは `{root}` の長さと OS で変わる) |
| `base` の親が無い bind | `ENOENT`、`{root}` の木に何も作らない (自動の置き場に落とさない) |
| `usable_cross_uid` と、途中が other に x を持たない `base` を渡した bind | `EPERM` (自動の置き場に落とさない) |
| 長いファイル名 (100 バイト) への connect | 通る、`x` が届く。proc-direct (ファイル名 90 まで) を超え、widened・thread-cwd-direct・link-file 等で届く |

## 経路を強制する場面

経路を使えなくする口はライブラリにも CLI にも作らず、スクリプトが Linux のコンテナの環境で条件を作る (kawaz 裁定 2026-11-20)。利用者が実際に当たる条件そのものを試すため。

| 条件 | 作り方 |
|---|---|
| スレッドの cwd を使えない | seccomp の filter を掛ける (SPEC は filter が掛かっていれば `unshare` を呼ばない) |
| `/proc` を使えない | CLI の間だけ `/proc` に空の tmpfs を被せる |
| 置き場に書けない | CLI の間だけ `TMPDIR`・`/tmp` 等を読み取り専用の bind mount にする |

- 強制できるのは Linux だけで、docker が要る。macOS 等の強制は各言語の自前の試験に任せる
- 環境では作れない場面は表に入れない (bind ではソケットのディレクトリに書けるので、そこに B を作れてしまい、B の無い形には進めない 等)
- docker が無い・動かない・実行のイメージを取れない時は「Linux の場面を飛ばした」と出し、失敗にしない。イメージを取れた後の各言語の Linux 向けの build の失敗は、Linux だけのコードの誤りでありうるので止める (終了コード 1)

### 条件の書き方

場面に `linux` を書くと、その場面は Linux のコンテナで流す (手元では流さない)。

```json
{ "name": "no-thread-cwd-no-proc-bind", "op": "bind", "path": "{long}/s.sock", "cwd": "{root}", "setup": ["mkdir {long}"],
  "linux": { "seccomp": "kill-unshare", "proc": false, "readonly": ["{tmpdir}", "/tmp"] },
  "expect": { "ok": true, "error": null, "file": true, "residue": [] } }
```

| 項目 | 中身 |
|---|---|
| `seccomp` | 必須。`default` (docker の既定の profile)、`unconfined` (filter 無し)、`kill-unshare` (`conformance/linux/seccomp-kill-unshare.json`。`unshare` を呼ぶとプロセスを SIGSYS で殺す filter、他は通す) |
| `proc` | `false` で CLI に `/proc` を見せない。省略時は `true` |
| `readonly` | CLI の間だけ書けなくする場所の並び。絶対パスか、`{tmpdir}`・`{xdg}`・`{root}`・`{long}` で始めたもの。省略時は空 |

- `default` は `proc: false`・`readonly` と組めない。mount に要る `SYS_ADMIN` を docker に足すと、docker は既定の profile で `unshare` を通すようになり、既定の seccomp でなくなるため (実測)。filter を掛けて mount もする場面は `kill-unshare` を使う
- 条件は CLI の間だけ作り、CLI が終わったら外す (待ち受けの手伝いや残骸の確かめは条件の外で動く)。作った後に効いているかを確かめ (書けなくした場所に書けない、`/proc/self` が無い、`prctl(PR_GET_SECCOMP)` が条件どおり)、効いていなければ「準備失敗」
- 強制の場面の `expect` は `ok`・`error`・`left`・`residue` 等だけにし、`route`・`base`・`spelling`・`skipped` は言語どうしの比べで見る (経路の名前に場面を縛らない)

docker の seccomp の実測 (2026-11-20、OrbStack の docker 29.8.2、arm64):

| docker run | `PR_GET_SECCOMP` | `unshare(CLONE_FS)` |
|---|---|---|
| 既定 | 2 (filter) | `EPERM` |
| 既定 + `--cap-add SYS_ADMIN` | 2 (filter) | 通る |
| `--security-opt seccomp=unconfined` | 0 | 通る |
| `kill-unshare` の profile (`SYS_ADMIN` の有無によらない) | 2 (filter) | SIGSYS でプロセスが死ぬ |

- 既定の profile は filter が掛かっているので、SPEC に従う実装はスレッドの cwd を使わない。ただし filter を見ずに `unshare` を呼ぶ実装も `EPERM` で同じ結果になり、見分けられない。`kill-unshare` ではその実装が「壊れた」になる (試験用の CLI で `unshare` を呼ぶ物を流して実測)

### コンテナの作り方

| 部品 | 中身 |
|---|---|
| 実行のイメージ | `rust:1` (python3 が入っていて、run.py・py の CLI・rs の CLI がそのまま動く) |
| 各言語の CLI | `langs.json` の `linux.build` が公式イメージの中で作り、docker の volume `sockat-conformance-out` に置く。rs は `rust:1` で `cargo build`、go は `golang:1` で `CGO_ENABLED=0` の `go build`、py は作らない。build の cache も言語ごとの volume (`sockat-conformance-cargo` 等) |
| リポ | 各言語のリポを読み取り専用で mount する (`/langs/<言語>`)。言語のリポには書かない |
| 流し方 | 1 場面に 1 コンテナ (seccomp はコンテナごとに決まる)。コンテナの中で run.py が全言語を流し、結果を JSON で返す。比べと表は手元の run.py がする |
| 置き場 | コンテナの中の `TMPDIR` は tmpfs の `/work`。場面の `{root}` 等はこの下に作る (`/tmp` を書けなくしても巻き込まない)。`--keep` は効かない |
| 権限 | CLI は root で動く (書けなくするのは読み取り専用の mount で、root にも効く)。`proc: false` か `readonly` がある場面だけ `SYS_ADMIN` を足す。network は無し |

`langs.json` の `linux`:

| 項目 | 中身 |
|---|---|
| `cmd` | コンテナの中の argv。`{repo}` はコンテナの中のリポの場所 (`/langs/<言語>`、読み取り専用)。volume は `/out` (読み取り専用) |
| `build` | 手元で走らせる argv (`{repo}` は手元のリポの場所、cwd はリポ)。CLI を volume `sockat-conformance-out` に置く。作る物が無ければ `null` |

選んだ理由: 3 言語の toolchain を入れたイメージを 1 つ作る形は、Dockerfile の保守と、toolchain を上げるたびの作り直し (数 GB) が要る。公式イメージで作って volume に置く形は、各言語のリポの Linux の試験と同じイメージを使い、2 回目以降の build は cache で数秒で終わる。実行のイメージを rs を作る `rust:1` と同じにするのは、rs の CLI が動的にリンクする glibc をそろえるため (go は静的リンクでイメージに依らない)。

### 強制の場面

パスは `{long}/s.sock` (ファイル名 93・100 の場面はその長さのファイル名)、cwd は `{root}` (`relative` が収まらない)。seccomp を書いていない行は `unconfined`。

| 場面 | 条件 | 確かめること |
|---|---|---|
| linux-long-bind | 無し (`unconfined`) | 比べの基準 |
| no-thread-cwd-bind | `default` | スレッドの cwd を使えない bind |
| no-thread-cwd-bind-kill-unshare | `kill-unshare` | 同じ。`unshare` を呼ばない |
| no-proc-bind | `/proc` 無し | `/proc` を使えない bind |
| no-thread-cwd-no-proc-bind | `kill-unshare`、`/proc` 無し | 両方使えない bind。`/tmp` の B の実パスの link-dir |
| no-thread-cwd-no-proc-bind-cross-uid | 同じ、`usable_cross_uid` | `/tmp` の B の実パスの link-dir で、`spelling` の `usable_cross_uid` が true |
| no-tmpdir-bind | `{tmpdir}` に書けない | B を `/tmp` に作る |
| no-tmpdir-no-tmp-bind | `{tmpdir}`・`/tmp` に書けない | B を `{xdg}` に作る |
| no-tmp-no-thread-cwd-no-proc-bind | `kill-unshare`、`/proc` 無し、`{tmpdir}`・`/tmp` に書けない | `{xdg}` の B の実パスの link-dir |
| no-tmp-no-thread-cwd-no-proc-bind-cross-uid | 同じ、`usable_cross_uid` | 別の uid が辿れる B が無く (`{xdg}` は 0700)、thread-cwd も使えないので `ENAMETOOLONG` |
| no-proc-long-filename-bind | `/proc` 無し、ファイル名 100 | どの経路も届かない時の `skipped` |
| linux-long-connect | 無し (`unconfined`) | 比べの基準 |
| no-proc-connect | `/proc` 無し | `/proc` を使えない connect |
| no-proc-connect-near-cwd | `/proc` 無し、cwd が `{long}` | relative |
| no-thread-cwd-no-proc-connect | `kill-unshare`、`/proc` 無し | 両方使えない connect。`/tmp` の B の直下の E を通す link-file |
| no-tmp-no-thread-cwd-no-proc-connect | 同じ + `{tmpdir}`・`/tmp`・`{xdg}` に書けない | B がソケットのディレクトリにしか作れず、link-file も使えないので `ENAMETOOLONG` |
| no-tmp-no-thread-cwd-no-proc-connect-base | 同じ、`base` に `{root}/b` | `base` の B の直下の E を通す link-file で届く |
| no-tmp-no-proc-connect | `/proc` 無し、`{tmpdir}`・`/tmp` に書けない | thread-cwd-direct |
| no-place-no-proc-connect | `/proc` 無し、`{tmpdir}`・`/tmp`・`{xdg}`・`{long}` に書けない | B をどこにも作れなくても thread-cwd-direct で届く |
| linux-filename-93-connect | 無し (`unconfined`)、ファイル名 93 | 比べの基準 (proc-direct に収まらない) |
| no-thread-cwd-filename-93-connect | `default`、ファイル名 93 | スレッドの cwd を使えない connect |
