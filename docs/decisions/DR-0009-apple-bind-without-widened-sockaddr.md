# DR-0009: Apple の OS の bind は広げた sockaddr を使わない

- Status: Active
- Date: 2026-11-18

## Context

- 広げた sockaddr で bind したソケットのアドレスは途中で切れ、`sun_path` に入らない
- それが読む側を壊す

| 読む側 | 壊れ方 |
|---|---|
| CPython | `getsockname` が NUL まで読み過ぎて後ろに無関係なバイトを付ける。asyncio の後始末 (`sock.getsockname()` を `os.stat`) が `ENOTDIR` で確率で落ちる |
| Go | `net.FileConn` は相手が広げた形で bind していると `RemoteAddr` が nil で、`.String()` が panic する |

- connect は自分のソケットを bind しないので、広げた sockaddr で connect しても自分のアドレスは切れない

## Decision

| 操作 | Apple の OS の順番 |
|---|---|
| bind | 相対パス → symlink → スレッド cwd → fork |
| connect 系 | 相対パス → 広げた sockaddr → symlink → スレッド cwd → fork (今のまま) |

- bind のスレッド cwd・fork・symlink の綴りの条件は sockaddr に入る長さ (103 バイト)。253 バイトは connect 系だけ

理由:

- bind は fork しても相手から見える副作用が無い (DR-0010) ので、広げた sockaddr を使う理由が無い

悪い面:

- Apple の OS の bind はファイル名 103 バイトまでになる (253 から下がる)

## Alternatives Considered

- 案 A: 今のまま (bind も広げた sockaddr を使う)
  - 不採用理由: できたソケットのアドレスが CPython / Go の標準を壊す
- 案 B: bind で広げた sockaddr を fork の後に回す
  - 不採用理由: fork が副作用なく届くので要らない

## Consequences

- 試験: macOS の connect 系で 253 バイトのパスが広げた sockaddr で通り、bind は広げた sockaddr を使わない

## 関連

- [docs/SPEC-ja.md](../SPEC-ja.md) の「長いパスの経路と試す順番」「各経路」「どこから届かなくなるか」
- 裁定: kawaz (2026-11-18)
- [DR-0010](DR-0010-fork-bind-listen-by-parent.md)
- [DR-0011](DR-0011-bind-spelling-with-random-part.md) (bind の順番から相対パスを外す)
