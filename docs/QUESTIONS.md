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

### TS-Q1: sockat-ts の対象の runtime と native の部品の持ち方

調査 ([research](research/2026-11-21-typescript-port.md)): 長いパスの bind は D を守る flock が要り、Node にも Bun にも標準で無い。flock とスレッドの cwd の経路は FFI (bun:ffi、Node 26.1 以上の node:ffi。どちらも experimental) か N-API の addon で作れる。connect は proc-direct・relative・link-file が JS だけで作れる。依頼元 (claude-ccmsg) は Bun。

- [ ] a: Bun だけ (bun:ffi)。配布は軽く、Bun で全部の経路に届く。Node の利用者は使えない
- [ ] b: Bun と Node、実行時に bun:ffi / node:ffi を選ぶ。Bun と Node 26.1 以上で全部届く。FFI の無い Node 22・24 は connect の全部と FFI の要らない bind だけ (他は `ENAMETOOLONG`)。pure JS で配布は軽い
- [ ] c: Bun と Node、N-API の addon 1 つを両方から読む。全部の版で全部届くが、OS × CPU × glibc / musl の prebuilt の配布と保守が重い

- [ ] d: ネイティブ抜き (JS だけ)。connect は全部、bind は link-dir・link-file。thread-cwd 等は作れない経路として飛ばす。D のロックの代わり (D の中に listen しているソケットを置く等) が要る

経過 (2026-11-21): kawaz「ネイティブ要素抜きにできんの？」「最低限のガワが出来たら publish して良い」。sockat-ts はまず d で最低限を作って公開する (統括の読み)。FFI / addon を足すかは、d で足りない所が見えてから決める。

統括推し (d の前): **b**。理由: 依頼元の Bun で全部届き、Node も LTS (26) で同じコードが全部届き、prebuilt が要らない。FFI を呼ぶ層を 1 か所に閉じるので、FFI が使えなくなっても addon (c) へその層だけ差し替えて移れる。悪い面: bun:ffi は Bun 自身の文書が本番で頼るなと書き、node:ffi は使うと `ExperimentalWarning` を出す。スレッドの cwd の経路は Worker を立てるので 1 回およそ 9ms。
