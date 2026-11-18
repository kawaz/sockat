# DR-0005: スレッドだけ cwd を移す経路を fork の手前に足す

- Status: Active
- Date: 2026-11-18

## Context

- fork の経路は副作用がある (peer の pid が子になる、子が全 fd の複製を持つ) ので、`connect` / `connect_nonblocking` は試さない
- そのため symlink も使えない時、`connect` は `bind` より手前で `ENAMETOOLONG` になる
- Linux と Apple の OS には、プロセスの cwd を変えずにスレッドだけ cwd を移す手段がある

## Decision

| OS | やり方 |
|---|---|
| Linux / Android | 使い捨てのスレッドで `unshare(CLONE_FS)` → `fchdir(dirfd)` → ファイル名で bind / connect。スレッドは捨てる |
| Apple の OS | `pthread_fchdir_np(dirfd)` → bind / connect → `pthread_fchdir_np(-1)` で戻すか、スレッドを捨てる |
| NetBSD / OpenBSD / illumos 等 | 無い |

- 順番: 相対パス → (Apple) 広げた sockaddr → symlink → スレッド cwd → fork (bind と `connect_any` 系だけ)
- `bind` / `connect` / `connect_nonblocking` / `connect_any` 系のどれも試す
- 使えないとみなして次へ: `unshare` が断られた、`pthread_fchdir_np` が無い・失敗した、その言語でスレッドを作れない・固定できない

理由:

- 副作用が無い (sockat-go の実測: peer の pid は呼び出し元のまま、fd の複製も無い、並行する `getcwd` は変わらない)
- `connect` の届く範囲が Linux / Apple の OS で `connect_any` と同じ所まで広がる
- bind も fork の副作用 (子が一瞬全 fd を持つ) を避けられる

悪い面:

- seccomp で `unshare` を断る環境がある (docker の既定は `EPERM`)。その時は次へ進む
- `pthread_fchdir_np` は libSystem の非公開 API で、将来消えうる。消えたら次へ進む

## Alternatives Considered

- 案 A: Linux だけ足す
  - 不採用理由: Apple の OS でも同じ副作用の無さが得られる。消えた時は次へ進むだけで壊れない
- 案 B: 足さない
  - 不採用理由: `connect` が fork の経路でしか届かない範囲が残る

## Consequences

- 実装はスレッドを作って固定できる必要がある。できない言語は経路を飛ばす
- 試験: 経路を強制して、プロセスの cwd が変わらない、peer の pid が呼び出し元、ソケットが元のパスにできる、使えない時に次へ進むことを確かめる

## 関連

- [docs/SPEC-ja.md](../SPEC-ja.md) の「スレッド cwd の経路」「どこから届かなくなるか」
- 裁定: kawaz (HB-Q4、2026-11-18)
