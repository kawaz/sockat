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
