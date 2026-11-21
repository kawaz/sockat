# 言語ごとの注意

> [English](./langs.md) | 日本語

各言語の実装に固有の注意 (標準ライブラリや runtime の不具合・制約) の一覧。詳しくは各リポにある。言語によらない注意は [SPEC](../docs/SPEC-ja.md) の「長いパスで標準と違う点」「使ってはいけない書き方」「置き場に残る物」。

| 言語 | 注意 | 詳しく |
|---|---|---|
| Rust | OpenBSD で Rust 1.99 以前の std の `local_addr`・`peer_addr`・`recv_from` はパスの最後の 1 バイトを落とす (1.100 で直った)。`recv_from` のアドレスへの DGRAM の返信には 1.100 以上が要る | [sockat-rs](https://github.com/kawaz/sockat-rs) |
| Go | macOS の広げた sockaddr の経路が無い | [sockat-go](https://github.com/kawaz/sockat-go) |
| Go | 標準の `UnixListener.Close` は綴りで unlink する。`ListenEx` の listener は閉じても消さない (`SetUnlinkOnClose(false)`) | [sockat-go](https://github.com/kawaz/sockat-go) |
| TypeScript | native 抜きなので、スレッドの cwd・`bindat` / `connectat`・広げた sockaddr の経路が無い | [sockat-ts](https://github.com/kawaz/sockat-ts) |
| TypeScript | Linux で `/proc` が見えないと Bun 自体が起動しない (Node は動く) | [sockat-ts](https://github.com/kawaz/sockat-ts) |
| TypeScript | `bindEx` の listener は、閉じると標準と同じく綴りで unlink する (Node も Bun も止める口が無い) | [sockat-ts](https://github.com/kawaz/sockat-ts) |
