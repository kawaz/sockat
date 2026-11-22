# sockat コマンド

> [English](./cli.md) | 日本語

長すぎる Unix domain socket のパスを、同じソケットを指し、OS の上限に収まるパスにして出すコマンドです。sockat を組み込めないプログラムに長いパスを渡す時や、アプリに組み込む前のお試しに使えます。

## 入れる

```sh
brew install kawaz/tap/sockat
```

または:

```sh
cargo install sockat-cli
```

[リリースのページ](https://github.com/kawaz/sockat-rs/releases) に、OS ごとの実行ファイルもあります。コマンドの名前は `sockat` です。

## 他のコマンドに渡す

```sh
curl --unix-socket "$(sockat /very/long/…/app.sock)" http://localhost/
```

標準出力には、パスだけが 1 行で出ます。同じパスには、いつも同じパスが返ります。出たパスは bind にも connect にも使えて、片付けは要りません。

## どんなパスになるか見る

```console
$ sockat /very/long/…/app.sock
/private/tmp/sockat-501/f21ddd85c65f/app.sock

$ sockat --json /very/long/…/app.sock
{
  "path": "/private/tmp/sockat-501/f21ddd85c65f/app.sock",
  "bytes": 45,
  "limit": 103,
  "original": "/very/long/…/app.sock",
  "original_bytes": 145,
  "route": "link-dir",
  "link": "/private/tmp/sockat-501/f21ddd85c65f",
  "target": "/very/long/…",
  "for": ["bind", "connect"],
  "warnings": []
}
```

sockat は短くする道具ではなく、上限 (`limit`) に収まるパスを出す道具です。出るパスが短く見えなくても、必ず上限に収まっています。上限に収まっているパスは、そのまま出ます。

## 相対パスを渡す

```console
$ cd /very/long/…
$ sockat ./app.sock
/private/tmp/sockat-501/f21ddd85c65f/app.sock
```

相対パスは、絶対パスにして出します。出たパスを、別のプロセスが別の場所から使っても、同じソケットを指します。

## ファイル名がとても長い時

```console
$ sockat /very/long/…/nnnn…nnnn.sock
/private/tmp/sockat-501/7e6cc6be310a
sockat: warning: this path is for connect; not recommended for bind (unlinking this path removes only the symlink, not the socket file)
```

ファイル名そのものが長い時は、connect 用のパスを出します。bind には勧めません (警告に理由が出ます)。

- connect に使うなら `--for connect` を付けると、警告が出ません
- bind に使うなら `--for bind` を付けます。その OS で bind に使えるパスを作れない時は、エラーになります

## 置き場を変える

```sh
sockat --base /tmp/my-app-1000/sockat /very/long/…/app.sock
```

sockat は `/tmp/sockat-<uid>/` の中に小さな symlink を置いて、そこを通るパスを出します。`--base` で、その置き場を自分のディレクトリに変えられます。

## 残った物を片付ける

```sh
sockat sweep
```

sockat を組み込んだプログラムが一時ディレクトリに残した物のうち、使われていない物を消します。`sockat` コマンドが置いた symlink は使い回す物なので、消しません。

## シェルの補完

```sh
sockat completion zsh
```

補完の定義を標準出力に出します。

## 環境変数

| 変数 | 使い道 |
|---|---|
| `XDG_RUNTIME_DIR` | `/tmp` に置き場を作れない時の、次の置き場 |
| `TMPDIR` | その次の置き場 |

## 終了コード

| 終了コード | 場面 |
|---|---|
| 0 | パスを出した |
| 1 | パスを作れなかった (ディレクトリが無い、上限に収まらない等)。理由は標準エラーに出る |
| 2 | 引数の誤り |
