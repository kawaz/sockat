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

経路を resolve と消さない置き場 B で組み直す案 ([issue](issue/2026-11-20-resolve-and-persistent-base.md) の「整理案」) の判断。

### RS-Q3: 関数の形

統括の推し: F1。std の形 (型ごとに別の型と関数) に合わせ、各言語で std の置き換えとして説明できる。

- [ ] F1: 型ごとに std の形で置く (stream は crate の直下、`datagram::`、`seqpacket::`)。操作ごとに `_ex(…, Options)`。resolve は用途ごとに 2 つ (`resolve_for_bind` / `resolve_for_connect`)
- [ ] F2: 型を引数で渡す (`bind(path, Type)`)。std の形から外れる
- [ ] F3: builder (`Options::new().usable_cross_uid(true).bind(path)`)。`_ex` の数は減るが、型ごとの操作が builder に集まる

### RS-Q4: 既定の `bind` も消さない綴りを使うか

既定の `bind` も resolve の綴り (消さない D) を使う方向で合意していたが、hyoui の統括から異論 ([issue](issue/2026-11-20-resolve-and-persistent-base.md) の「利用者の回答」)。既定の `bind` は std の型しか返さないので、利用者に片付けの手がかりが無く、長命の daemon・試験・exec をまたぐプロセスで D と B が溜まる。

統括の推し: b。消さない綴りの利点 (綴りで消す上のライブラリ、DGRAM の返信、運用の道具) を使う利用者は、片付けの口を受け取る `_ex` / resolve を選べば足りる。Python は `getsockname` を差し替えて元のパスを返すので、上のライブラリの問題は既定でも起きない。既定の操作が呼び出しの外に状態を残さないのは、std の置き換えとして自然。2 人の利用者 (llm-gateway、hyoui) はどちらも綴りを使わない。

届く範囲の表 ([pages/reach](../pages/reach/README.md)) を作って分かったこと: b では fork が無くなる分、OpenBSD・illumos (スレッドの cwd も symlink-file も無い) と、Linux で seccomp が掛かり `/proc` も無い環境で、既定の `bind` が長いパスに全く届かない (sockat-py・sockat-go は今もそう)。a や `bind_ex` なら、書ける置き場があれば link-dir でファイル名 67〜71 バイトまで届く。b の中間として、既定の `bind` も呼び出しごとのディレクトリで link-dir を使い、bind の後に消す形 (綴りは `Dangling`) もありうる (置き場が共有の `/tmp` の時は、消した後の綴りを他人が作り直せる)。

- [ ] a: 既定の `bind` も消さない綴りを使う。既定の利用者にも綴りの利点が届くが、片付け損ねた B・D の掃除が必須になる (exec をまたぐプロセスにも効く掃除の作り方が要る)
- [ ] b: 既定の `bind` は今の形で呼び出しの中で片付ける (呼び出しごとの一時ディレクトリを作って消す。綴りは `Dangling`。プロセスごとの B も作らないので、落ちても exec しても何も残らない)。消さない綴りは `_ex` / resolve を選んだ人だけ

