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

### D12-Q3: fork を作れない言語 (Python、Go) の bind で、中心の経路が使えない時に何をするか

既定の bind は a で確定 (kawaz 2026-11-19)。kawaz の案「b を any に入れる (何が何でも bind したい人向け。失うものは any の説明に列挙。any は fork の意味でなく『何が何でも』の意図)」を議論中。決めること:

- β: `bind_any` の置き場の symlink をどこに作るか (b の共有の置き場まで / c の持ち主だけが書ける置き場だけ / c → b の順)
- γ: 何を失ったかを戻り値で知らせるか (`connect_any` の `forked` と同じ形)
- δ: fork のある Rust にも `bind_any` を置くか (届く範囲はほぼ増えない)

以下は元の問い。

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

### D12-Q5: 作った直後の D を開けない時、名前で確かめて消してよいか

umask が持ち主の権限を削ると (`mkdirat` の 0700 が 0000 / 0600 / 0300 等になる)、作った直後の D を開けない。Apple の OS の `O_SEARCH` は持ち主の検索権限が無いと `EACCES` (sockat-py が実測、umask 0777 / 0177)。`O_RDONLY` で開く OS (Linux と Apple の OS 以外) は持ち主の読み取りが無いと同じ。Linux は `O_PATH` で開けるので当たらない。

今の DR-0012 は「確認 (fd の `fstat`) が通った D だけを消す」なので、開けない D は確かめられず、呼ぶたびに置き場に `sockat.XXXXXXXXXX` が積もる。

- 名前で確かめる案: `fstatat(置き場の fd, 名前, AT_SYMLINK_NOFOLLOW)` が「ディレクトリ・持ち主が実効 uid・group と other に権限が無い」なら `unlinkat(置き場の fd, 名前, AT_REMOVEDIR)`
- 名前で確かめてから消すまでの間にすり替えられうるが、すり替えるには置き場に書けて、名前を当てる必要がある。`AT_REMOVEDIR` は空のディレクトリしか消さないので、当たっても他人の空のディレクトリが 1 つ消えるだけ (sticky の `/tmp` では他人が自分の D を差し替えられない)
- 名前で `chmod` してから開く案は symlink を辿る (`fchmodat` の `AT_SYMLINK_NOFOLLOW` は Linux で効かない) ので採らない

統括推し: a。こういう umask は稀だが、当たると呼ぶたびに残骸が増える。名前で確かめる場合の最悪は「他人の空のディレクトリが 1 つ消える」で、ファイルの中身に届かない。

- [ ] a: 開けない時だけ、名前で確かめて空なら消す
- [ ] b: 消さずに残す (今の DR-0012。SPEC の「残骸」に書く)
