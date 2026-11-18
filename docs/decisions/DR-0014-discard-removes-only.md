# DR-0014: 後始末つきの bind の discard はファイルを消すだけで、listener を閉じない

- Status: Active
- Date: 2026-11-19

## Context

- 長いパスでは、カーネルが覚えている綴りが元のパスでないので、標準が listener を閉じる時にソケットのファイルを消す言語 (Go) でも消えない。元のパスで、自分が作ったファイルだけを消す口が要る
- listener は利用者が asyncio / `http.Serve` / tokio 等に渡す。Rust は所有権で listener を move するので、消す口が閉じる対象を持てない

## Decision

- 後始末つきの bind (`_ex`) は、標準の listener と、ファイルを消す口 `discard` を返す
- `discard` はファイルを消すだけで、listener を閉じない。listener を閉じるのは利用者
- 名前は `discard` (閉じる意味を含むなら `dispose` 等にするところ。消すだけなので `discard`)

| 言語 | 形 |
|---|---|
| Rust | `bind_ex(path) -> io::Result<(UnixListener, SocketFile)>`、`SocketFile::discard(self) -> io::Result<()>`。Drop では消さない |
| Python | `listener, discard = sockat.bind_ex(path)`。`discard` は引数なしの関数 |
| Go | `ListenEx(path) (*net.UnixListener, func() error, error)`。短いパスでも消すのは discard だけにする (`SetUnlinkOnClose(false)`) |

- `discard` の確かめ方・成功と失敗の条件は SPEC の「公開する操作」

理由:

- 3 言語でそろう
- listener を他のライブラリに渡した後で、二重に閉じることが起きない

## Alternatives Considered

- 案 A: `discard` が listener を閉じてから消す
  - 不採用理由: Rust は listener を move するので作れず、言語ごとに形が割れる。渡した先のライブラリが閉じた後の二重の close も起きる

## Consequences

- SPEC の「公開する操作」の `_ex` の文を「消すだけ」に直す

## 関連

- 裁定: kawaz (2026-11-19)
- [DR-0012](DR-0012-own-directory-and-thread-cwd.md)
