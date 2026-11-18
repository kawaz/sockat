# 裁定・確認待ち一覧 (ユーザ用)

## 運用規約

<details>
<summary>ゼロコンテキストエージェント向け（本セクションは消さない）</summary>

- 裁定/確認待ち項目を 1項目=1ラベル=1セクション で記載
- ラベル形式: XX-Q1（XX は 2-3 文字、バッチやセッション内で一意、Qn単独の使い回し禁止、長期一意性は不要)
- 依頼形式: 「👺XX-Q1 の裁定お願いします」（参照用途ではラベルに👺を付けない。誤陽性がユーザのハイライト/アラームを汚す）
- チャット提示と同一ターンで本ファイルに記録 + path 指定 commit
- 裁定が下りたら該当セクションを即削除し、内容は正規の記録先 (DR / issue / journal) へ反映。本ファイルは常に「現在待ち」だけを持つ
- 参照は[]()で提示（リポ内は相対、リポ外はフルパス）
- 選択肢・確認項目は `- [ ] a: …` 形式（チェックボックス + ラベル）で書く

</details>

## 裁定待ち

### D12-Q1: D をどこにも作れない時の bind で、fork の前にスレッド cwd と /proc 版を試すか

[DR-0012](decisions/DR-0012-own-directory-and-thread-cwd.md) の「D の置き場」は、D をどこにも作れない時の bind を D 無しの fork (ソケットのディレクトリに R `.sockat.XXXXXXXXXX` を作り、子がそこへ `fchdir`) にし、「スレッド cwd と /proc 版は D 無しの形を試さない」と書いている。

- 承認の時の想定は「ソケットのディレクトリにも R を作れない」場面だった
- 実際には、D を作れない (確認に落ちる、名前を使い切る等) が R は作れる場面がある。その R は fork の子でなくてもスレッド cwd (`fchdir(ソケットのディレクトリの fd)` → `.sockat.XXXXXXXXXX/<ファイル名>`) と /proc 版 (`/proc/self/fd/<fd>/.sockat.XXXXXXXXXX/<ファイル名>`) で同じように使える
- 綴りは R を通すので、片付けの後は何にも当たらない (中心の経路と同じ安全)

統括推し: a。fork は最終手段なので、副作用の無い手段で届くなら先に使う。悪い面は D 無しの形の分だけ試験の組み合わせが増えること。

- [ ] a: 試す。D 無しでも「スレッド cwd → /proc 版 → fork」の順にする
- [ ] b: 試さない。今の DR-0012 のまま (D 無しは fork だけ)

### D12-Q2: `connect_any` 系の fork と FreeBSD の connect の予備の経路は D を通さなくてよいか

[DR-0012](decisions/DR-0012-own-directory-and-thread-cwd.md) の「未確定」。どちらもソケットのディレクトリの fd とファイル名で connect する (fork の子は `fchdir(ソケットのディレクトリの fd)` → `connect(<ファイル名>)`、FreeBSD は `connectat(fd, <ファイル名>)`)。

- connect した側のソケットは bind されないので、connect に渡した綴りはどこにも残らない (サーバの `getpeername` は空、クライアントの `getpeername` はサーバが bind した綴り)
- そのため綴りにランダムな部品 (R) を挟む理由が無い。D を通すと綴りが 11 バイト伸び、届くファイル名が短くなるだけ

統括推し: a。

- [ ] a: D を通さない (SPEC の今の書き方で確定し、「未確定」から外す)
- [ ] b: D を通す (中心の経路と同じ `R/<ファイル名>`)

### D12-Q3: fork を作れない言語 (Python、Go) の bind で、中心の経路が使えない時に何をするか

DR-0012 の bind は「スレッド cwd → /proc 版 → fork → `ENAMETOOLONG`」で、相対パスと置き場の symlink を外した。Python と Go は fork が無いので、次の所で長いパスの bind が `ENAMETOOLONG` になる (今の版は相対パス / symlink で届いている。sockat-py と sockat-go が指摘)。

| 環境 | 今の版 | DR-0012 のまま |
|---|---|---|
| NetBSD / OpenBSD / illumos | 相対パス → symlink で届く | 長いパスは全部 `ENAMETOOLONG` |
| Linux で seccomp の filter あり、`/proc` 無し | 相対パス → symlink | `ENAMETOOLONG` |
| Linux で seccomp の filter あり、`/proc` あり | /proc (ファイル名およそ 90 まで) | /proc 版 (およそ 79 まで) |
| macOS で `pthread_fchdir_np` が使えない | 相対パス → symlink | `ENAMETOOLONG` |
| D をどこにも作れない | (該当なし) | `ENAMETOOLONG` |

置き場の symlink (`<置き場>/sockat.XXXXXXXXXX` → ソケットのディレクトリ、綴り `<置き場>/sockat.XXXXXXXXXX/<ファイル名>`) を戻すと、片付けの後は symlink が無いので普段は何にも当たらない。ただし置き場が `/tmp` のような共有の場所だと、他の利用者がその綴りを (Linux の `/proc/net/unix` 等で見て) 作り直せ、上のライブラリが綴りで unlink した時に別のディレクトリのファイルを消させうる。

統括推し: a。届かない環境は少数で、b は安全でない綴りを残し、c は DR-0012 が外した置き場の安全の確認を bind に戻す。c は需要が出たら改めて決める。

- [ ] a: DR-0012 のまま。fork を作れない言語は、中心の経路が使えない所で bind が `ENAMETOOLONG`。README の OS × 経路の表で目立たせる (sockat-go の推し)
- [ ] b: fork を作れない言語の bind に限り、fork の場所 (順 4) に置き場の symlink を置く (sockat-py の提案)
- [ ] c: b を「持ち主が実効 uid で group / other が書けない置き場」(`$XDG_RUNTIME_DIR`、macOS の `$TMPDIR` 等) に限る。作り直せるのは自分だけなので綴りは何にも当たらない。BSD の `/tmp` では使えない

### D12-Q4: 後始末つきの bind (`_ex`) の形

各言語のセッションの案。どれも listener は標準の型のまま返し、型は増やさない (Rust だけ消す口の型が 1 つ)。

| 言語 | 形 |
|---|---|
| Rust | `bind_ex(path) -> io::Result<(UnixListener, SocketFile)>`、`SocketFile::discard(self) -> io::Result<()>`。Drop では消さない |
| Python | `listener, discard = sockat.bind_ex(path)`。`discard` は引数なしの関数 |
| Go | `ListenEx(path) (*net.UnixListener, func() error, error)` (`context.WithCancel` と同じ形)。短いパスでも消すのは discard だけにする (`SetUnlinkOnClose(false)`) |

論点は discard が listener を閉じるか。SPEC は「`discard()` で listener を閉じ、消す」と書いたが、Rust は listener を tokio 等へ move するので、消す口が閉じる対象を持てない。

統括推し: α は a (3 言語でそろい、listener を asyncio / `http.Serve` / tokio に渡した後の二重の close も起きない)、β は表のとおり (名前は仮のまま)。

- [ ] α-a: discard はファイルを消すだけ。listener を閉じるのは利用者。SPEC をこの形に直す
- [ ] α-b: Go と Python は閉じてから消す、Rust は消すだけ (言語ごとに違う)
- [ ] β: 表の形で良いか (違えば言語と形を指定)
