# 適合試験

同じ入力で、全言語の実装が同じ結果 (通った経路、失うもの、飛ばした経路、errno、残った物) になることを機械で確かめる。統括のセッションが各言語の報告を読んで突き合わせる代わりに、差が出た所だけを人が判断する。

## 全体

| 部品 | 置き場 | 役目 |
|---|---|---|
| 場面の表 | ハブの `conformance/cases.json` | 何を試すか (操作、パスの形、前もって作る物) |
| 流すスクリプト | ハブの `conformance/run.py` | 場面ごとに環境を作り、各言語の CLI を起こし、結果を集めて比べる |
| 言語の一覧 | ハブの `conformance/langs.json` | 各言語の CLI の起こし方。`cwd` はリポの場所 (`cmd` の `{repo}` と、`/` を含む相対パスの `cmd[0]` の基準。CLI の cwd ではない)、`cmd` は起こすコマンド (まだ無ければ `null` で「未実装」)、`build` は CLI を作るコマンド (流す前に各言語のリポで実行しておく) |
| 試験用 CLI | 各言語のリポ | 1 回の bind / connect を経路の列で試し、結果を JSON で出す。公開しない |

- ハブの `just conformance` で流す。差があれば終了コード 1 で、場面 × 言語の表を出す
- 比べるのは同じマシン・同じ環境で動かした言語どうし。OS や seccomp で結果が変わるのは正しいので、場面の表に OS ごとの期待値は持たない (全言語で変わらない値だけ `expect` に書ける)

## 試験用 CLI の決まり

起こし方: スクリプトが場面ごとに 1 回、CLI のプロセスを起こす。cwd・環境変数 (`TMPDIR`、`XDG_RUNTIME_DIR` 等)・umask はスクリプトが整えてから起こす。CLI は cwd も環境変数も変えない。

入力: 標準入力に JSON を 1 つ。

```json
{ "op": "bind", "path": "<渡すパス>" }
```

| 項目 | 中身 |
|---|---|
| `op` | `bind` か `connect` |
| `path` | ライブラリに渡すパス (相対パスもある)。そのまま渡す |

出力: 標準出力に JSON を 1 つ。

```json
{ "ok": true, "error": null, "route": "thread-cwd", "losses": ["respelled"], "skipped": ["standard"] }
```

| 項目 | 中身 |
|---|---|
| `ok` | bind / connect が通ったか |
| `error` | 失敗の時、errno の名前 (`ENAMETOOLONG`、`ENOENT` 等)。引数の誤りは `invalid-argument`、一般のエラーは `general` |
| `route` | 通った経路の名前。失敗の時は実際に bind / connect して失敗した経路の名前か `null` (SPEC の「公開する操作」の any 系の決まり) |
| `losses` | 失うものの名前の並び (SPEC の「失うもの」の名前)。失敗の時は `[]` |
| `skipped` | 飛ばした経路の名前の並び (試した順)。`reason` は約束しないので出さない |

- bind が通ったら、CLI は listener を閉じずにプロセスを終える (終了で閉じる)。閉じる時にファイルを消す言語の標準 (Go の短いパス等) があり、閉じると言語の差を拾ってしまうため
- connect が通ったら、1 バイト `x` を送ってから閉じる
- 経路の情報は公開 API でなく、パッケージの中から経路の列を直接呼んで取ってよい (公開 API の形に依らずに作れる)
- bind は既定の bind の経路の列、connect は既定の connect の経路の列で試す (最終手段は使わない)

## スクリプトが確かめること

CLI の出力に加えて、CLI が終わった後に:

| 確かめること | 中身 |
|---|---|
| ソケットのファイル | bind が通った時、元のパスにソケットのファイルがある |
| 残骸 | 置き場 (`TMPDIR`、`/tmp` の `sockat.*`) とソケットのディレクトリ (`.sockat.*`) に何も残っていない |
| 届いたか | connect が通った時、スクリプトが待ち受けていた側に `x` が届いた |

## 場面の表 (`conformance/cases.json`)

```json
{ "name": "long-absolute-bind", "op": "bind", "path": "{long}/s.sock", "cwd": "{root}", "setup": ["mkdir {long}"], "expect": { "ok": true, "losses": ["respelled"] } }
```

- `{root}` はスクリプトが場面ごとに作る空のディレクトリ (`$TMPDIR` の下)。`{long}` は `{root}` の下の、パス全体が 150 バイト以上になる深いディレクトリ。`{short}` は `/tmp/sockat-conformance-<8 桁>` に作る `{root}` を指す symlink (`$TMPDIR` が深い環境でも短い絶対パスを作るため。毎回消す)。`TMPDIR` と `XDG_RUNTIME_DIR` は場面ごとの空のディレクトリ (0700)
- 場面の名前は英語の kebab-case
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

経路を強制する場面 (thread-cwd を使えない、D をどこにも作れない 等) と、最終手段を使う場面は、`_ex` の形が決まり、強制の口を CLI に足してから表に足す。
