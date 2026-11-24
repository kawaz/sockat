# CLI `sockat` の決まり

長いパスを、同じ場所を指し、OS の上限 (sockaddr に入る長さ) に収まる綴りにして出すコマンド。目的は短くすることでなく、bind / connect がエラーにならない綴りを出すこと (URL の短縮の道具とは違う)。出した綴りが一見長くても、上限に収まっていることを約束する。判断と理由は [DR-0018](../decisions/DR-0018-cli-resolve-with-reused-hashed-link.md)。実装は sockat-rs のリポに置く。この文書は、サブコマンド・オプション・出力・終了コードを決める。

## 使われ方

| 客 | 使い方 |
|---|---|
| 主な客: 短い綴りが欲しい人 | sockat を組み込めないプログラムに、長いパスの代わりに渡す。アプリに組み込む前に、sockat がどんな綴りを作るかを試す |
| 手法を確かめたい人 | 手法を名指しして、どんな性質のソケットができるかを見る (`--help-all` の側) |

```console
$ sockat /very/long/…/app.sock
/tmp/sockat-1000/3f9c2a7b1e04/app.sock

$ curl --unix-socket "$(sockat /very/long/…/app.sock)" http://localhost/
```

- 綴りは置き場の実パスで出す。macOS では `/private/tmp/sockat-501/3f9c2a7b1e04/app.sock` の形になる (`/tmp` より長く見えても、出す綴りはいつも sockaddr に入る長さに収まっている)

## 呼び方

```text
sockat <パス>                 sockat resolve <パス> の省略形
sockat resolve [オプション] <パス>
sockat sweep
sockat completion <シェル>
sockat --help | --help-all | --version
```

- 引数なしは `--help` を表示する
- 最初の引数がサブコマンドの名前なら、サブコマンドとして扱う。同じ名前の相対パスを渡す時は `./resolve` のように書くか、`sockat resolve resolve` と書く
- オプションはパスの前にも後ろにも置ける。`--` の後ろはパスとして扱う
- オプションはロングオプションだけ (指示なくショートオプションを足さない)
- `--help` に載せるのは `resolve`・`sweep`・`completion` と、下の「基本のオプション」。`--help-all` は「進んだオプション」と手法を試すサブコマンドも載せる
- `--help` の文言・補完の定義・実装は、同じ変更でそろえる

## `resolve`

作り方は [DR-0018 の「`resolve` の既定の綴り」](../decisions/DR-0018-cli-resolve-with-reused-hashed-link.md#resolve-の既定の綴り)。

### 基本のオプション

| オプション | 中身 |
|---|---|
| `--json` | 綴りだけでなく、長さや作り方を JSON で出す |
| `--for <bind\|connect>` | 綴りの使い道。普段は指定しなくてよい (ソケットのディレクトリを指す綴りは、どの使い道にも使える)。効くのは、ファイル名が長くてソケットのファイルを指す綴りに回る時だけ。指定が無ければ connect 用の綴りを出す。`--for bind` は bind に使える綴りだけを求め、この OS で作れなければエラーにする。sendto は `connect`、返信を受けるために bind する送り手は `bind` |
| `--base <ディレクトリ>` | 置き場 (B そのもののパス) を指定する。確かめはライブラリの `Options.base` と同じ |

### 進んだオプション (`--help-all`)

| オプション | 中身 |
|---|---|
| `--base-fd <N>` と `--base-pid <PID>` | 利用者が開いたディレクトリの fd の番号と、それを持つプロセスの pid。`/proc/<PID>/fd/<N>` を B の綴りにする。2 つは組で渡す。片方だけならエラー |
| `--route <名前>[,<名前>…]` | 手法を名指しして、並べた順に試す。その環境で使えない手法はエラー。preset の名前も渡せる |

- 進んだオプションの名前・手法の名前は試す用で、約束しない

### 出力

標準出力に綴りを 1 行で出す (最後に改行)。他は何も出さない。

`--json` の時は、JSON のオブジェクトを 1 つ出す。

```json
{
  "path": "/tmp/sockat-1000/3f9c2a7b1e04/app.sock",
  "bytes": 38,
  "limit": 107,
  "original": "/very/long/…/app.sock",
  "original_bytes": 214,
  "route": "link-dir",
  "link": "/tmp/sockat-1000/3f9c2a7b1e04",
  "target": "/very/long/…",
  "for": ["bind", "connect"]
}
```

| 項目 | 中身 |
|---|---|
| `path` | 出した綴り |
| `bytes` | 綴りのバイト数 |
| `limit` | この OS の sockaddr に入る長さ |
| `original`・`original_bytes` | 渡されたパスと、そのバイト数 |
| `route` | 作り方の名前 (`standard`: 渡されたパスのまま、`link-dir`: ソケットのディレクトリを指す E を通す、`link-file`: ソケットのファイルを指す E を通す)。診断用で、名前を約束しない |
| `link`・`target` | 使った E のパスと、それが指す先。`standard` の時は無い |
| `for` | この綴りを使える使い道 (`bind`・`connect`) |
| `warnings` | 注意の文の並び (無ければ空の並び。どの `--json` の出力にも置く)。標準エラーに出す警告から、先頭の `sockat: warning: ` を除いた文を入れる |

- 項目は足すことがある。読む側は知らない項目を無視する

### 終了コードとエラー

| 終了コード | 場面 |
|---|---|
| 0 | 綴りを出した |
| 1 | 綴りを作れなかった (ディレクトリが無い、収まらない、置き場を作れない、使い道の指定が要る等) |
| 2 | 引数の誤り |

- エラーは標準エラーに、原因と次にすることを 1〜2 行で出す。標準出力には何も出さない (`$(sockat …)` に半端な文字列が入らないように)
- 満たせない時に、満たさない綴りを出さない
- 相対パスを渡されたら、絶対パスにしてから長さで分ける (出した綴りは別のプロセスが別の cwd で使いうる)。絶対パスの作り方はライブラリと同じ ([DR-0019](../decisions/DR-0019-absolutize-relative-path-on-bind.md)): 実パスと、`$PWD` に文字列でつないで `..` を畳んだ綴り (元と同じ所を指すと確かめた物) を候補にし、上限に収まる物があればそれを出す。どちらも収まらなければ E を通す綴りにする。`--json` の `original` には渡されたままの文字列を入れる
- 上限を超える絶対パスも、E を作る前に実パスの候補 (ソケットのディレクトリの realpath + ファイル名) を試し、収まればそれを出す (置き場に何も作らない)
- 候補を出した時の `--json` の `route` は `standard` で、`link` と `target` は無い
- 相対の綴りは出さない。候補も E も作れない時 (とても深い cwd 等) はエラー。相対パスでソケットのディレクトリが無い時は、短くても終了コード 1 (`ENOENT`)。上限に収まる絶対パスは、何も確かめずにそのまま出す
- `--base` を渡された時も、その B の直下に同じ作り方の E を置く
- 名前で終わらないパス (`dir/`・`dir/.`・`dir/..`・`..`)、空のパス、NUL を含むパスは、長さによらず引数の誤り (終了コード 2)。ライブラリと同じ
- `--json` で、出す綴りが UTF-8 でない時は終了コード 1 のエラーにし、`--json` 無しを勧める
- 出す綴りは、いつも sockaddr に入る長さ以下 (出す前に確かめる)。元のパスが収まっていれば、そのまま出す。短さは競わない
- `--help` 等の文言は「短くする」でなく「上限に収まるパスにする」で書く

### ファイル名が長い時

ファイル名が長くて、ソケットのディレクトリを指す綴りに収まらない時は、ソケットのファイルを指す綴りを出す (kawaz 裁定 2026-11-22、CL-Q1 = b)。

- `--for` の指定が無ければ、connect 用の綴りとして出し、終了コードは 0
- この綴りは、どの OS でも bind には勧めない。標準エラーに、その旨と理由の警告を 1 行出す。標準出力は綴りだけのまま

| OS | bind に勧めない理由 | `for` |
|---|---|---|
| bind が symlink を辿らない OS (Linux 等) | この綴りで bind すると失敗する | `["connect"]` |
| bind が symlink を辿る OS (macOS・NetBSD) | bind はできるが、この綴りで unlink しても symlink が消えるだけで、ソケットのファイルが残る (片付けのつもりで消しても消えない) | `["bind", "connect"]` |

- `--json` の時は標準エラーに出さず、`warnings` に同じ文を入れる
- `--for connect` を指定した時は警告を出さない (connect には、どの OS でもそのまま使える)
- `--for bind` を指定した時: bind が symlink を辿る OS では綴りを出し、unlink しても消えない旨の警告を出す。辿らない OS では終了コード 1 のエラー

```console
$ sockat /very/long/…/nnnnnnnn…nnnn.sock
/tmp/sockat-1000/9c41d7e2a0b3
sockat: warning: this path is for connect; not recommended for bind (bind does not follow the symlink on this OS)
```

macOS と NetBSD の警告は、理由の所が「unlinking this path removes only the symlink, not the socket file」になる。`--for bind` を指定した時の警告は「unlinking this path removes only the symlink, not the socket file (remove the socket by its original path)」。

## `sweep`

ライブラリの `sweep()` と同じことをする (置き場 1〜3 の既定の名前の B の中の、死んだ D を消す)。`resolve` が B の直下に置いた E には触らない。何も出さず、終了コード 0。

## `completion`

`sockat completion <シェル>` は、そのシェルの補完の定義を標準出力に出す。

## 手法を試すサブコマンド (`--help-all`)

```text
sockat bind [--route <名前>[,<名前>…]] [--base <ディレクトリ>] [--json] [--keep] <パス>
sockat connect [--route <名前>[,<名前>…]] [--base <ディレクトリ>] [--json] <パス>
```

`bind <パス>` と `connect <パス>` は、実際に bind / connect して、どの手法で通ったかと結果を表示する。手法の動きを試す・確かめるための物で、出力の項目も手法の名前も約束しない。

- `--route` が無ければ、ライブラリの既定と同じ順で試す (`bind` は [bind の順](../SPEC-ja.md#bind-の順)、`connect` は [connect の順](../SPEC-ja.md#connect-の順))
- `--base` はライブラリの `Options.base` と同じ
- `bind` は stream のソケットを bind して listen し、結果を表示した後、作ったソケットのファイルと置き場に作った物を消して終わる (ライブラリの `remove()` と `cleanup()`)。`--keep` を付けると消さずに終わる (置き場に残る物を自分で見たい時)
- `connect` は、そのパスで listen しているソケットに stream で connect し、結果を表示して閉じる。相手が居なければ失敗として表示する (`ECONNREFUSED`・`ENOENT`)
- 相対パスの扱いはライブラリと同じ (`bind` は絶対パスにしてから、`connect` は相対のまま)

### `--route` に渡す名前

| 名前 | 中身 |
|---|---|
| 経路の名前 | SPEC の経路の名前 (`standard`・`link-dir`・`link-file`・`thread-cwd`・`at`・`proc-direct`・`relative`・`widened`・`at-direct`・`thread-cwd-direct`)。並べた順に試す |
| `default` | その操作の既定の順 (preset)。`--route` を付けないのと同じ |

- 名指しした手法が、その操作かその OS に無い時 (`bind` に `relative`、Linux に `at` 等) は、何も試さずに終了コード 2 のエラーにし、その操作とその OS で使える名前を並べる
- 名指しした手法が、そのパスでは使えない時 (綴りが収まらない等) は、飛ばして次の名前に進む。全部使えなければ終了コード 1
- `resolve` に渡せるのは、綴りを出せる `standard`・`link-dir`・`link-file` と `default` だけ
- `link-dir` の置き場を `/proc` を通す綴りにするか実パスにするかは、名前では分けない。`--base` を指定すればその置き場を、`--base-fd` と `--base-pid` を指定すれば `/proc` を通す綴りを使う

### 出力

標準出力に、項目を 1 行ずつ `名前: 値` で出す。

```console
$ sockat bind /very/long/…/app.sock
route: link-dir
base: tmp
kernel-path: /tmp/sockat-1000/1f3a/0/app.sock
spelling: Linked (removable, until cleanup, usable cross uid, usable with private tmp)
skipped: standard (too long)
left: /tmp/sockat-1000/1f3a/0 -> /very/long/…
```

`--json` の時は、JSON のオブジェクトを 1 つ出す。項目の名前と値は、適合試験の CLI の出力 ([conformance.md](conformance.md)) と同じにし、CLI だけの項目を足す。

```json
{
  "ok": true,
  "error": null,
  "route": "link-dir",
  "base": "tmp",
  "spelling": { "kind": "Linked", "removable": true, "until": "Cleanup", "usable_cross_uid": true, "usable_with_private_tmp": true },
  "skipped": [{ "name": "standard", "reason": "too long" }],
  "kernel_path": "/tmp/sockat-1000/1f3a/0/app.sock",
  "left": ["/tmp/sockat-1000/1f3a/0"]
}
```

| 項目 | 中身 |
|---|---|
| `ok`・`error`・`route`・`base`・`spelling` | 適合試験の CLI と同じ |
| `skipped` | 飛ばした手法と理由の並び (試した順)。理由の文は約束しない |
| `kernel_path` | `bind` は `getsockname`、`connect` は `getpeername` が返したパス。取れなければ `null` |
| `left` | 置き場に作って、表示の時点で残っている物のパスの並び。`--keep` が無ければ、表示の後に消す |

### 終了コード

| 終了コード | 場面 |
|---|---|
| 0 | bind / connect が通った |
| 1 | 通らなかった (どの手法も使えない、bind / connect が失敗した)。`--json` の時は `ok` が `false` の JSON を標準出力に出す |
| 2 | 引数の誤り (無い名前、その操作・その OS に無い手法) |
