# 適合試験

同じ入力で、全言語の実装が同じ結果 (通った経路、失うもの、飛ばした経路、errno、残った物) になることを機械で確かめる。統括のセッションが各言語の報告を読んで突き合わせる代わりに、差が出た所だけを人が判断する。

## 全体

| 部品 | 置き場 | 役目 |
|---|---|---|
| 場面の表 | ハブの `conformance/cases.json` | 何を試すか (操作、パスの形、前もって作る物) |
| 流すスクリプト | ハブの `conformance/run.py` | 場面ごとに環境を作り、各言語の CLI を起こし、結果を集めて比べる |
| 言語の一覧 | ハブの `conformance/langs.json` | 各言語の CLI の起こし方。`cwd` はリポの場所 (`cmd` の `{repo}` と、`/` を含む相対パスの `cmd[0]` の基準。CLI の cwd ではない)、`cmd` は起こすコマンド (まだ無ければ `null` で「未実装」)、`build` は CLI を作るコマンド (`just conformance` が流す前に各言語のリポで走らせる。`--no-build` で止める)、`lacks` はその言語が作らない経路の名前の並び (各言語の README の OS × 経路の表と同じ。比べ方を分けるのに使う)、`linux` は Linux のコンテナでの起こし方 ([コンテナの作り方](#コンテナの作り方)) |
| 試験用 CLI | 各言語のリポ | 1 回の bind / connect を経路の列で試し、結果を JSON で出す。公開しない |
| Linux の条件 | ハブの `conformance/linux/` | 経路を強制する場面で使う seccomp の profile ([経路を強制する場面](#経路を強制する場面)) |

- ハブの `just conformance` で流す。差があれば終了コード 1 で、場面 × 言語の表を出す
- `--on host` は手元で流す場面だけ、`--on linux` は Linux のコンテナで流す場面だけ。既定は両方。`--verbose` は差が無くても場面ごとの各言語の `route`・`skipped` 等を出す
- 比べるのは同じマシン・同じ環境で動かした言語どうし。OS や seccomp で結果が変わるのは正しいので、場面の表に OS ごとの期待値は持たない (全言語で変わらない値だけ `expect` に書ける)

## 試験用 CLI の決まり

起こし方: スクリプトが場面ごとに 1 回、CLI のプロセスを起こす。cwd・環境変数 (`TMPDIR`、`XDG_RUNTIME_DIR` 等)・umask はスクリプトが整えてから起こす。CLI は cwd も環境変数も変えない。

入力: 標準入力に JSON を 1 つ。

```json
{ "op": "bind", "path": "<渡すパス>", "last_resort": true }
```

| 項目 | 中身 |
|---|---|
| `op` | `bind` か `connect` |
| `path` | ライブラリに渡すパス (相対パスもある)。そのまま渡す |
| `last_resort` | 最終手段を使うか (`true` / `false`)。省略時は `false` |

出力: 標準出力に JSON を 1 つ。

```json
{ "ok": true, "error": null, "route": "thread-cwd", "losses": ["respelled"], "skipped": ["standard"] }
```

| 項目 | 中身 |
|---|---|
| `ok` | bind / connect が通ったか |
| `error` | 失敗の時、errno の名前 (`ENAMETOOLONG`、`ENOENT` 等)。引数の誤りは `invalid-argument`、一般のエラーは `general` |
| `route` | 通った経路の名前。失敗の時は実際に bind / connect して失敗した経路の名前か `null` (SPEC の「公開する操作」の `_ex` の決まり) |
| `losses` | 失うものの名前の並び (SPEC の「失うもの」の名前)。失敗の時は `[]` |
| `skipped` | 飛ばした経路の名前の並び (試した順)。`reason` は約束しないので出さない |

- bind が通ったら、CLI は listener を閉じずにプロセスを終える (終了で閉じる)。閉じる時にファイルを消す言語の標準 (Go の短いパス等) があり、閉じると言語の差を拾ってしまうため
- connect が通ったら、1 バイト `x` を送ってから閉じる
- 終了コード: 結果を出したら 0 (connect の後に `x` を送れなかった時も、結果を出して 0。届いたかはスクリプトが見る)。入力の JSON が不正なら標準出力に何も出さず 2。それ以外はスクリプトが「壊れた」とみなす
- 標準出力は結果の JSON 1 行だけ。ビルドの出力等は標準エラーへ
- `error` の名前: errno の名前は C の名前。同じ値に名前が 2 つあるものは `EAGAIN`・`EOPNOTSUPP`・`EDEADLK` に寄せる。名前の分からない errno は `errno-<番号>`。errno を持たない引数の誤りは `invalid-argument`、errno を持たないそれ以外は `general`
- 経路の情報は公開 API でなく、パッケージの中から経路の列を直接呼んで取ってよい (公開 API の形に依らずに作れる)
- `last_resort` が `false` なら、bind は既定の bind の経路の列、connect は既定の connect の経路の列で試す。`true` なら最終手段を使う `_ex` の列で試す (bind は最後に symlink-dir、connect は最後に fork-cwd-direct が足される)
- その言語で作れない経路 (`langs.json` の `lacks`) は、そこに来たら `skipped` に入れて次へ進む (SPEC の「各実装に求めること」)

## スクリプトが確かめること

CLI の出力に加えて、CLI が終わった後に:

| 確かめること | 中身 |
|---|---|
| ソケットのファイル | bind が通った時、元のパスにソケットのファイルがある |
| 残骸 | 置き場 (`TMPDIR`、`/tmp` の `sockat.*`) とソケットのディレクトリ (`.sockat.*`) に何も残っていない |
| 届いたか | connect が通った時、スクリプトが待ち受けていた側に `x` が届いた |

## 言語どうしの比べ方

| 場面 | 比べ方 |
|---|---|
| どの言語の `route` も、他の言語の `lacks` に入っていない | 全言語で比べる |
| ある言語の `route` が、他の言語の `lacks` に入っている (その経路を「きっかけの経路」と呼ぶ) | 「`lacks` のうちきっかけの経路に当たる部分」が同じ言語どうしで組を作り、組の中で比べる |

- 組の中で多数派と違う言語が「差」。多数派が決まらなければ組の全員が「差」
- 組を分けた場面では、場面の `expect` はきっかけの経路を作れる言語にだけ当てる。作れない言語には暗黙の期待 (残骸が無い等) と、作れないきっかけの経路が `skipped` に入っていることを当てる
- 自分の `lacks` に入った経路を `route` にした言語は、どの場面でも「期待違い」
- 組を分けた場面は、結果の表の後に組と一緒に出す

## 場面の表 (`conformance/cases.json`)

```json
{ "name": "long-absolute-bind", "op": "bind", "path": "{long}/s.sock", "cwd": "{root}", "setup": ["mkdir {long}"], "expect": { "ok": true, "losses": ["respelled"] } }
```

- `{root}` はスクリプトが場面ごとに作る空のディレクトリ (`$TMPDIR` の下)。`{long}` は `{root}` の下の、パス全体が 150 バイト以上になる深いディレクトリ。`{short}` は `/tmp/sockat-conformance-<8 桁>` に作る `{root}` を指す symlink (`$TMPDIR` が深い環境でも短い絶対パスを作るため。毎回消す)。`TMPDIR` と `XDG_RUNTIME_DIR` は場面ごとの空のディレクトリ (0700) で、`{tmpdir}`・`{xdg}` で書ける
- 場面の名前は英語の kebab-case
- `last_resort` は書いた時だけ CLI の入力にそのまま渡す。省略時は入力に入れない (CLI の既定の `false`)
- `setup` はスクリプトが CLI を起こす前にすること。`"動詞 パス"` の文字列で、動詞は `mkdir` (途中も作る)・`touch`・`listen` (待ち受けのソケット)・`stale-socket` (bind してすぐ閉じた、誰も listen していないソケット)。シェルには渡さない
- `expect` は全言語・全環境で変わらない値だけを書く
- `expect` に書かなくても、全場面で次を期待する: 残骸が無い、bind が通ったら元のパスにソケットがある、connect が通ったら `x` が届く、失敗したら `losses` が空。経路を試す前の失敗 (ディレクトリが無い、途中がファイル、引数の誤り) は `route` が `null` で `skipped` が空
- 環境で変わる値 (`route` 等) は言語どうしの比較だけで見る。`/tmp` の残骸は前後の差で見るので、同じ時に他で sockat を動かすと誤った差が出うる

最初の場面 (経路を強制しなくても作れるもの):

| 場面 | 確かめること |
|---|---|
| 短い絶対パスの bind | `route` が `standard`、`losses` が空 |
| 短い相対パスの bind | `losses` が `cwd-relative` |
| 長い絶対パスの bind | 通る、`losses` が `respelled`、残骸なし |
| 長いパスでディレクトリが無い | `ENOENT`、`route` が `null`、`skipped` が空 |
| 長いパスの途中がファイル | `ENOTDIR` |
| 長いパスの bind 先に既にファイルがある | `EADDRINUSE`、`route` が実際に bind した経路 |
| 長いパスへの connect | 通る、`x` が届く、残骸なし |
| 長いパスの、誰も listen していないソケットへの connect | `ECONNREFUSED` |
| 最後がファイル名でない長いパス、先頭以外に NUL | `invalid-argument`、何も作らない |
| 最終手段を使う、長い絶対パスの bind | 通る (既定の経路で届く所なので、`route` と `losses` は既定と同じ。fork の無い言語が既定で届かない OS では symlink-dir) |
| 長いファイル名 (100 バイト) の既定の bind | Linux 等の D を通す経路 (ファイル名 96 まで) を超える。macOS・NetBSD は symlink-file で通り、他は `ENAMETOOLONG` |
| 同じパスの、最終手段を使う bind | 既定で届かない所では symlink-dir を試して `skipped` に入れる (綴り `/tmp/sockat.XXXXXXXXXX/<ファイル名>` も sockaddr に入らない)。何も残らない |
| 最終手段を使う、長いパスへの connect | 通る、`x` が届く、`route` は既定と同じ (fork-cwd-direct を試さない) |
| 長いファイル名 (100 バイト) への connect | 通る、`x` が届く。D を通す経路 (ファイル名 96 まで) を超え、proc-held・widened・symlink-file 等で届く |
| 同じパスへの、最終手段を使う connect | 通る、`route` は既定と同じ |

## 経路を強制する場面

経路を使えなくする口はライブラリにも CLI にも作らず、スクリプトが Linux のコンテナの環境で条件を作る (kawaz 裁定 2026-11-20)。利用者が実際に当たる条件そのものを試すため。

| 条件 | 作り方 |
|---|---|
| スレッドの cwd を使えない | seccomp の filter を掛ける (SPEC は filter が掛かっていれば `unshare` を呼ばない) |
| `/proc` を使えない | CLI の間だけ `/proc` に空の tmpfs を被せる |
| 置き場に書けない | CLI の間だけ `TMPDIR`・`/tmp` 等を読み取り専用の bind mount にする |

- 強制できるのは Linux だけで、docker が要る。macOS 等の強制は各言語の自前の試験に任せる
- 環境では作れない場面は表に入れない (bind ではソケットのディレクトリに書けるので、そこに置き場を作れてしまい、D 無しの形には進めない 等)
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
- 強制の場面の `expect` は `ok`・`error`・残骸等だけにし、`route`・`losses`・`skipped` は言語どうしの比べで見る (経路の名前に場面を縛らない)

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
| no-thread-cwd-no-proc-bind | `kill-unshare`、`/proc` 無し | 両方使えない bind。fork の無い言語は組を分ける |
| no-thread-cwd-no-proc-bind-last-resort | 同じ、最終手段 | 同じ |
| no-tmpdir-bind | `{tmpdir}` に書けない | D を `/tmp` に作る |
| no-tmpdir-no-tmp-bind | `{tmpdir}`・`/tmp` に書けない | D をソケットのディレクトリに作り、残さない |
| no-tmp-no-thread-cwd-no-proc-bind | `kill-unshare`、`/proc` 無し、`{tmpdir}`・`/tmp` に書けない | fork の子がソケットのディレクトリの D で bind |
| no-tmp-no-xdg-no-thread-cwd-no-proc-bind-last-resort | 同じ + `{xdg}` に書けない、最終手段 | symlink-dir の置き場も無い |
| no-proc-long-filename-bind | `/proc` 無し、ファイル名 100 | どの経路も届かない時の `skipped` |
| linux-long-connect | 無し (`unconfined`) | 比べの基準 |
| no-proc-connect | `/proc` 無し | `/proc` を使えない connect |
| no-proc-connect-near-cwd | `/proc` 無し、cwd が `{long}` | relative |
| no-thread-cwd-no-proc-connect | `kill-unshare`、`/proc` 無し | 両方使えない connect |
| no-tmp-no-thread-cwd-no-proc-connect | 同じ + `{tmpdir}`・`/tmp` に書けない | symlink-file も使えない |
| no-tmp-no-thread-cwd-no-proc-connect-last-resort | 同じ、最終手段 | fork の無い言語は組を分ける |
| no-tmp-no-proc-connect | `/proc` 無し、`{tmpdir}`・`/tmp` に書けない | D をソケットのディレクトリに作る connect |
| no-place-no-proc-connect | `/proc` 無し、`{tmpdir}`・`/tmp`・`{long}` に書けない | D をどこにも作れない connect |
| linux-filename-93-connect | 無し (`unconfined`)、ファイル名 93 | 比べの基準 (proc-direct に収まらない) |
| no-thread-cwd-filename-93-connect | `default`、ファイル名 93 | スレッドの cwd を使えない connect |
