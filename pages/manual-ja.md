# sockat 利用マニュアル

> [English](./manual.md) | 日本語

標準の bind / connect を sockat に置き換えれば、長いパスでもそのまま動きます ([README](../README-ja.md))。入れ方と、その言語での詳しい使い方は、言語ごとのマニュアルにあります。

| 言語 | マニュアル |
|---|---|
| Rust | [sockat-rs](https://github.com/kawaz/sockat-rs/blob/main/docs/MANUAL-ja.md) |
| Python | [sockat-py](https://github.com/kawaz/sockat-py/blob/main/docs/MANUAL-ja.md) |
| Go | [sockat-go](https://github.com/kawaz/sockat-go/blob/main/README-ja.md) |
| JavaScript / TypeScript | [sockat-ts](https://github.com/kawaz/sockat-ts/blob/main/README-ja.md) |

この下では、どの言語でも共通の「できること」を紹介します。関数の名前は Rust の物で書きます。他の言語も同じ形で、名前はその言語の慣習に合わせてあります。

## DGRAM も使えます

stream の他に、DGRAM のソケットも長いパスで bind / connect できます。

```rust
let server = sockat::datagram::bind(&path)?;

let client = sockat::datagram::unbound()?;
sockat::datagram::connect(&client, &path)?;
```

深い場所で bind した送り手にも、受け手からの返信が届きます。絶対パスを渡して bind すれば、受け手に見える送り手のアドレスが、上限に収まる絶対パスになるためです (標準だけでは、絶対パスは長すぎて bind できず、相対パスで bind すると受け手は返信できません)。

TypeScript には DGRAM がありません (Node.js と Bun の標準に無いため)。

## 短いパスだけを作る

一番簡単なのは sockat の bind / connect に置き換えることですが、短いパスだけを作る関数もあります。パスを他のライブラリや標準の関数に自分で渡したい時に使います。

```rust
let to = sockat::resolve_for_connect(&long_path, Default::default())?;
let stream = std::os::unix::net::UnixStream::connect(&to.path)?; // 何度使ってもよい
to.cleanup()?; // 使い終わったら
```

bind に渡す短いパスは `resolve_for_bind` で作ります。返ってくる短いパスは、元のパスと同じ場所を指します。

## ソケットのファイルの片付けまで任せる

`bind_ex` は、listener と一緒に、bind したソケットのファイルを消す口を返します。

```rust
let bound = sockat::bind_ex(&path, Default::default())?;
// ... bound.socket で accept する ...
bound.file.remove()?; // listener を閉じる前に
drop(bound.socket);
```

bind したファイルを覚えているので、別のファイルに置き換わっていたら消しません。

## どこまで深いパスでも届きます

ディレクトリは、いくら深くても届きます。ファイル名も、`daemon.sock` のような普通の長さなら、どの環境でも届きます。OS ごとの細かい上限は [届く範囲の表](./reach/README-ja.md) にあります。

## 裏で作られる物は気にしなくて構いません

長いパスで bind する時、sockat は `/tmp/sockat-<uid>/` の中に小さなディレクトリと symlink を作り、そこを通る短い道でつなぎます。

- 容量はほぼ 0 で、使い終わった物は大抵 OS が片付けます
- connect は何も残しません
- 片付けたい時は `sweep()` を呼べば、使われていない物だけを消します。試験を何度も回す環境では、最後に 1 回呼べば溜まりません
- 置き場所を自分で決めたい時は、`bind_ex` 等のオプション `base` に、sockat 専用にするディレクトリのパス (例 `/tmp/my-app-1000/sockat`) を渡します

## 関数の一覧

[リファレンス](./reference-ja.md) にあります。

## sockat が短い道をどう作っているか

[技術説明](./technical-ja.md) にあります。
