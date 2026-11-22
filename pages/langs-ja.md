# 言語ごとの注意

> [English](./langs.md) | 日本語

各言語の実装に固有の注意 (標準ライブラリや runtime の不具合・制約) の一覧。詳しくは各リポにある。言語によらない注意は [SPEC](../docs/SPEC-ja.md) の「長いパスで標準ライブラリと違う点」「使ってはいけない書き方」「置き場に残る物」「sweep」。

| 言語 | 注意 | 詳しく |
|---|---|---|
| Rust | OpenBSD で Rust 1.99 以前の std の `local_addr`・`peer_addr`・`recv_from` はパスの最後の 1 バイトを落とす (1.100 で直った)。`recv_from` のアドレスへの DGRAM の返信には 1.100 以上が要る | [sockat-rs](https://github.com/kawaz/sockat-rs/blob/main/docs/REFERENCE-ja.md#rust-に固有の注意) |
| Rust | Rust の std はパスで渡した abstract の名前 (`"\0name"`) を拒むので、`bind_ex` もその std のエラーを返す (abstract は `SocketAddr::from_abstract_name` で std に渡す。`resolve_for_bind` は `Original` を返す) | [sockat-rs](https://github.com/kawaz/sockat-rs/blob/main/docs/REFERENCE-ja.md#rust-に固有の注意) |
| Go | macOS の広げた sockaddr の経路が無い (取り込んだ接続の `RemoteAddr` が nil になるため) | [sockat-go](https://github.com/kawaz/sockat-go/blob/main/docs/REFERENCE-ja.md#spec-から外れる経路) |
| Go | 標準ライブラリの `UnixListener.Close` は綴りで unlink する。既定の `Listen` が link-file の綴りの時は E だけが消えてソケットのファイルが残る (link-dir は実体が消える)。`ListenEx` の listener は閉じても消さない (`SetUnlinkOnClose(false)`) | [sockat-go](https://github.com/kawaz/sockat-go/blob/main/docs/REFERENCE-ja.md#go-に固有の注意) |
| Go | `ForBind.Path` を自分で `net.ListenUnix` に渡した listener は、`SetUnlinkOnClose(false)` にして `SocketFile.Remove` で消す | [sockat-go](https://github.com/kawaz/sockat-go/blob/main/docs/REFERENCE-ja.md#go-に固有の注意) |
| Go | illumos では標準ライブラリが先頭の `@` を abstract に書き換えるので、相対のまま標準ライブラリに渡す時 (connect と、どの形でも届かない時の bind) は `./` を付けて渡す | [sockat-go](https://github.com/kawaz/sockat-go/blob/main/docs/REFERENCE-ja.md#go-に固有の注意) |
| Go | 標準ライブラリはパスを NUL で黙って切り詰めるので、NUL を含むパスは長さによらず `EINVAL` | [sockat-go](https://github.com/kawaz/sockat-go/blob/main/docs/REFERENCE-ja.md#go-に固有の注意) |
| Python | 長いパスで返すソケット (と `datagram.unbound()`) は `socket.socket` の subclass で、`getsockname()` / `getpeername()` が元のパスを返す。`type(x) is socket.socket` は偽、`socket.fromfd` で作り直すとカーネルの綴りに戻る | [sockat-py](https://github.com/kawaz/sockat-py/blob/main/docs/REFERENCE-ja.md#python-に固有の注意) |
| Python | asyncio の `start_unix_server(sock=)` は、3.13 以上なら閉じる時に元のパスのソケットファイルを消す (3.11 / 3.12 は消さない) | [sockat-py](https://github.com/kawaz/sockat-py/blob/main/docs/REFERENCE-ja.md#asyncio) |
| Python | `_ex` は `sockat.ex` に置く (`socket.socket.connect_ex` と紛れるため)。`import sockat` では読み込まない | [sockat-py](https://github.com/kawaz/sockat-py/blob/main/docs/REFERENCE-ja.md#python-に固有の注意) |
| Python | `os.path.abspath`・`normpath`・`relpath` は `..` を字句で畳む。相対パスを絶対にする時は `os.path.join(os.getcwd(), path)` | [sockat-py](https://github.com/kawaz/sockat-py/blob/main/docs/REFERENCE-ja.md#python-に固有の注意) |
| Python | 標準ライブラリの `socket` はパスを NUL で黙って切り詰める (`bind("/tmp/a\0b")` が `/tmp/a` に bind する)。sockat は先頭以外の NUL をどの長さでも `ValueError` にする | [sockat-py](https://github.com/kawaz/sockat-py/blob/main/docs/REFERENCE-ja.md#python-に固有の注意) |
| TypeScript | native 抜きなので、スレッドの cwd・`bindat` / `connectat`・広げた sockaddr の経路が無い。`usableCrossUid` を満たせない時は `ENAMETOOLONG` | [sockat-ts](https://github.com/kawaz/sockat-ts/blob/main/docs/REFERENCE-ja.md#長いパスへの届き方) |
| TypeScript | Linux で `flock(1)` (util-linux / busybox) が無いと、長いパスの bind と resolve は `ENAMETOOLONG` (既定の connect は届く)。illumos はロックの手段が無く同じ | [sockat-ts](https://github.com/kawaz/sockat-ts/blob/main/docs/REFERENCE-ja.md#長いパスへの届き方) |
| TypeScript | Linux で `/proc` が見えないと Bun 自体が起動しない (Node は動く) | [sockat-ts](https://github.com/kawaz/sockat-ts/blob/main/docs/REFERENCE-ja.md#どこから届かなくなるか) |
| TypeScript | `bindEx` の listener は、閉じると標準ライブラリと同じく綴りで unlink する (Node も Bun も止める口が無い)。相対のまま標準ライブラリに渡した時 (どの形でも届かない時) だけは、閉じた時点の cwd で同じ名前を unlink する | [sockat-ts](https://github.com/kawaz/sockat-ts/blob/main/docs/REFERENCE-ja.md#spec-から外れる点) |
| TypeScript | DGRAM・SEQPACKET が無い (Node と Bun の標準ライブラリに無い) | [sockat-ts](https://github.com/kawaz/sockat-ts/blob/main/docs/REFERENCE-ja.md#spec-から外れる点) |
| TypeScript | node:net は数値に読める文字列を TCP のポートと読むので、相対のまま標準ライブラリに渡す時 (connect と、どの形でも届かない時の bind) は `./` を付けて渡す | [sockat-ts](https://github.com/kawaz/sockat-ts/blob/main/docs/REFERENCE-ja.md#標準との対応) |
