# 退避した Decision Records

後続の DR に置き換えられた DR。各ファイルの `Status: Superseded by DR-NNNN` が正本で、現役の文書からはここも各ファイルも名指ししない (置き換え先を指す)。

| DR | 説明 | 置き換え先 |
|---|---|---|
| [DR-0005](DR-0005-thread-cwd-route.md) | スレッドだけ cwd を移す経路を fork の手前に足す | [DR-0012](../DR-0012-own-directory-and-thread-cwd.md) |
| [DR-0007](DR-0007-connect-any-is-opt-in.md) | connect_any 系は既定の API に出さず、使う人が選んで有効にする | [DR-0013](DR-0013-any-means-reach-at-any-cost.md) |
| [DR-0008](DR-0008-unsafe-base-held-by-fd.md) | 安全でない置き場は自分専用のディレクトリを fd で掴んで symlink の経路に使う | [DR-0012](../DR-0012-own-directory-and-thread-cwd.md) |
| [DR-0009](DR-0009-apple-bind-without-widened-sockaddr.md) | Apple の OS の bind は広げた sockaddr を使わない | [DR-0012](../DR-0012-own-directory-and-thread-cwd.md) |
| [DR-0011](DR-0011-bind-spelling-with-random-part.md) | bind に渡す綴りにランダムな部品を挟み、安全な綴りの経路だけを短くなる順に試す | [DR-0012](../DR-0012-own-directory-and-thread-cwd.md) |
| [DR-0013](DR-0013-any-means-reach-at-any-cost.md) | any 系は「何かを失ってでも届かせる」opt-in の API で、何を失ったかを返す | [DR-0015](../DR-0015-ex-with-last-resort-and-diagnostics.md) |
| [DR-0014](DR-0014-discard-removes-only.md) | 後始末つきの bind の discard はファイルを消すだけで、listener を閉じない | [DR-0015](../DR-0015-ex-with-last-resort-and-diagnostics.md) |
