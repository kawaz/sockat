# 退避した Decision Records

後続の DR に置き換えられた DR。各ファイルの `Status: Superseded by DR-NNNN` が正本で、現役の文書からはここも各ファイルも名指ししない (置き換え先を指す)。

| DR | 説明 | 置き換え先 |
|---|---|---|
| [DR-0002](DR-0002-no-connect-any-without-fork.md) | fork の経路を作れない言語は connect_any 系を出さない | [DR-0015](DR-0015-ex-with-last-resort-and-diagnostics.md) |
| [DR-0005](DR-0005-thread-cwd-route.md) | スレッドだけ cwd を移す経路を fork の手前に足す | [DR-0012](DR-0012-own-directory-and-thread-cwd.md) |
| [DR-0007](DR-0007-connect-any-is-opt-in.md) | connect_any 系は既定の API に出さず、使う人が選んで有効にする | [DR-0013](DR-0013-any-means-reach-at-any-cost.md) |
| [DR-0008](DR-0008-unsafe-base-held-by-fd.md) | 安全でない置き場は自分専用のディレクトリを fd で掴んで symlink の経路に使う | [DR-0012](DR-0012-own-directory-and-thread-cwd.md) |
| [DR-0009](DR-0009-apple-bind-without-widened-sockaddr.md) | Apple の OS の bind は広げた sockaddr を使わない | [DR-0012](DR-0012-own-directory-and-thread-cwd.md) |
| [DR-0010](DR-0010-fork-bind-listen-by-parent.md) | fork の経路の bind は listen を必ず親がする | [DR-0017](../DR-0017-resolve-through-persistent-base.md) |
| [DR-0011](DR-0011-bind-spelling-with-random-part.md) | bind に渡す綴りにランダムな部品を挟み、安全な綴りの経路だけを短くなる順に試す | [DR-0012](DR-0012-own-directory-and-thread-cwd.md) |
| [DR-0012](DR-0012-own-directory-and-thread-cwd.md) | 長いパスは自分専用のディレクトリ D を fd で掴み、その中の乱数の symlink R を通して bind / connect し、呼び出しの中で片付ける (thread-cwd・at → proc → fork-cwd) | [DR-0017](../DR-0017-resolve-through-persistent-base.md) |
| [DR-0013](DR-0013-any-means-reach-at-any-cost.md) | any 系は「何かを失ってでも届かせる」opt-in の API で、何を失ったかを返す | [DR-0015](DR-0015-ex-with-last-resort-and-diagnostics.md) |
| [DR-0014](DR-0014-discard-removes-only.md) | 後始末つきの bind の discard はファイルを消すだけで、listener を閉じない | [DR-0015](DR-0015-ex-with-last-resort-and-diagnostics.md) |
| [DR-0015](DR-0015-ex-with-last-resort-and-diagnostics.md) | 既定の操作ごとに `_ex` を置き、最終手段を使うかを引数 1 つで選び、失ったものの名前の並び (`losses`) と診断を返す | [DR-0017](../DR-0017-resolve-through-persistent-base.md) |
| [DR-0016](DR-0016-bind-through-file-symlink.md) | bind が symlink を辿る OS では、ソケットのファイルを指す symlink を通して bind する (symlink-file) | [DR-0017](../DR-0017-resolve-through-persistent-base.md) |
