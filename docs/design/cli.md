# CLI `sockat` の決まり

長いパスを、同じ場所を指す短い綴りにして出すコマンド。判断と理由は [DR-0018](../decisions/DR-0018-cli-resolve-with-reused-hashed-link.md)。実装は sockat-rs のリポに置く。この文書は、サブコマンド・オプション・出力・終了コードを決める。

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
| `--for <bind\|connect>` | 短い綴りの使い道。要るのは、ファイル名が長くてソケットのファイルを指す綴りに回る時だけ。sendto は `connect`、返信を受けるために bind する送り手は `bind` |
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

- 項目は足すことがある。読む側は知らない項目を無視する

### 終了コードとエラー

| 終了コード | 場面 |
|---|---|
| 0 | 綴りを出した |
| 1 | 綴りを作れなかった (ディレクトリが無い、収まらない、置き場を作れない、使い道の指定が要る等) |
| 2 | 引数の誤り |

- エラーは標準エラーに、原因と次にすることを 1〜2 行で出す。標準出力には何も出さない (`$(sockat …)` に半端な文字列が入らないように)
- 満たせない時に、満たさない綴りを出さない

```console
$ sockat /very/long/…/nnnnnnnn…nnnn.sock
sockat: the file name is too long for a path that works for both bind and connect (89 bytes; up to 77 here)
  pass --for connect or --for bind to get a path for that use
```

## `sweep`

ライブラリの `sweep()` と同じことをする (置き場 1〜3 の既定の名前の B の中の、死んだ D を消す)。`resolve` が B の直下に置いた E には触らない。何も出さず、終了コード 0。

## `completion`

`sockat completion <シェル>` は、そのシェルの補完の定義を標準出力に出す。

## 手法を試すサブコマンド (`--help-all`)

`bind <パス>` と `connect <パス>` は、`--route` で名指しした手法 (無ければ既定の順) で実際に bind / connect し、結果 (カーネルが覚えた綴り、綴りの性質、通った手法、飛ばした手法と理由、置き場に残った物) を表示する。出力の形は、主な客向けの `resolve` を出した後に決める。
