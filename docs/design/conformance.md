# 適合試験

同じ入力で、全言語の実装が同じ結果 (通った経路、失うもの、飛ばした経路、errno、残った物) になることを機械で確かめる。統括のセッションが各言語の報告を読んで突き合わせる代わりに、差が出た所だけを人が判断する。

## 全体

| 部品 | 置き場 | 役目 |
|---|---|---|
| 場面の表 | ハブの `conformance/cases.json` | 何を試すか (操作、パスの形、前もって作る物) |
| 流すスクリプト | ハブの `conformance/run.py` | 場面ごとに環境を作り、各言語の CLI を起こし、結果を集めて比べる |
| 言語の一覧 | ハブの `conformance/langs.json` | 各言語の CLI の起こし方。`cwd` はリポの場所 (`cmd` の `{repo}` と、`/` を含む相対パスの `cmd[0]` の基準。CLI の cwd ではない)、`cmd` は起こすコマンド (まだ無ければ `null` で「未実装」)、`build` は CLI を作るコマンド (`just conformance` が流す前に各言語のリポで走らせる。`--no-build` で止める)、`lacks` はその言語が作らない経路の名前の並び (各言語の README の OS × 経路の表と同じ。比べ方を分けるのに使う) |
| 試験用 CLI | 各言語のリポ | 1 回の bind / connect を経路の列で試し、結果を JSON で出す。公開しない |

- ハブの `just conformance` で流す。差があれば終了コード 1 で、場面 × 言語の表を出す
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

- `{root}` はスクリプトが場面ごとに作る空のディレクトリ (`$TMPDIR` の下)。`{long}` は `{root}` の下の、パス全体が 150 バイト以上になる深いディレクトリ。`{short}` は `/tmp/sockat-conformance-<8 桁>` に作る `{root}` を指す symlink (`$TMPDIR` が深い環境でも短い絶対パスを作るため。毎回消す)。`TMPDIR` と `XDG_RUNTIME_DIR` は場面ごとの空のディレクトリ (0700)
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
| `/proc` を使えない | コンテナに `/proc` を見せない |
| 置き場に書けない | `TMPDIR`・`/tmp` 等を書けなくする |

- 強制できるのは Linux だけで、docker が要る。macOS 等の強制は各言語の自前の試験に任せる
- 環境では作れない場面は表に入れない (bind ではソケットのディレクトリに書けるので、そこに置き場を作れてしまう 等)
