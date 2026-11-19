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

### DG-Q1: SOCK_DGRAM の長いパスへの宛先つき送信の形

調査と実測は [research](research/2026-11-19-datagram-and-seqpacket.md)。DGRAM と SEQPACKET の bind、DGRAM の connect は stream の経路がそのまま使えた (macOS・Linux で実測)。DGRAM だけが送るたびに宛先 (`sendto`) を渡せるので、そこをどうするか。

統括の推し: a。標準の型を返す約束にそのまま乗り、SPEC に足す経路が無く、connect 後の `send` / `sendmsg` / 非同期ランタイムは標準のまま使える。見つけた需要 (sd_notify の中継、コンテナの NOTIFY_SOCKET) は宛先が固定。

- [ ] a: connect して宛先を固定した標準の DGRAM を返す (`connect_datagram(path)` 等)。1 つのソケットで宛先は変えられない。受け手が作り直されたら `ECONNREFUSED` / `ECONNRESET` で、利用者が connect し直す
- [ ] b: 送るたびに経路を当てる関数を足す (`send_to(sock, buf, path)` 等)。relative は cwd の競合で別のソケットに届き取り消せないので外す必要があり、FreeBSD 等で届く所が狭い。`sendmsg` と非同期の版を言語ごとに足すことになる。宛先を変えながら長いパスへ送る需要は見つかっていない
- [ ] c: a と b を両方

### DG-Q2: 長いパスに bind した DGRAM の失うもの

長いパスに bind した DGRAM の送り元には返信が届かない。受け手の `recvfrom` が返す綴り (`R/<名前>` 等) は片付け済みで `ENOENT`。綴りを他人が作り直せる場所だと、返信が他人のソケットに届いた (thread-cwd の綴りは受け手の cwd に、symlink-file の綴りは `/tmp` に作り直して、実測)。stream の `respelled` の危険は「綴りで消す・stat する」だったが、DGRAM では「綴りへ送る」が加わる。

統括の推し: α は a、β は yes。α: `respelled` は DGRAM の bind では常に返信不可を意味し、新しい名前は情報を増やさない。β: 危険が実際に symlink-dir と同じになるので、失うものの名前は型ではなく実際の危険に合わせる (`losses` は呼び出しごとの結果なので型で割れて構わない)。

- α (返信が届かないこと): 
  - [ ] a: `respelled` の説明 (起きること・注意すること) と「長いパスで標準と違う点」に DGRAM の場合を足す
  - [ ] b: DGRAM の bind にだけ付く新しい名前 (仮に `unrepliable`) を足す
- β (共有の置き場の symlink-file): DGRAM の bind が共有の置き場 (`/tmp` 等) の symlink-file を通った時に `recreatable-spelling` も付けるか
  - [ ] yes: 付ける (stream の symlink-file は付けない ([DR-0016](decisions/DR-0016-bind-through-file-symlink.md)) ので型で扱いが割れる)
  - [ ] no: 付けず、説明に書くだけ

API の形 (型ごとに関数を分けるか、`_ex` の数、返信を受けたい送り元の bind + connect、Rust の SEQPACKET の返す型) は DG-Q1 の後に案をまとめて出す。

### CF-Q1: 適合試験で経路を強制する口をどこに作るか

[適合試験](design/conformance.md) は今、強制なしで作れる場面だけを流している。「thread-cwd を使えない」「D をどこにも作れない」「`/proc` が無い」等の場面を全言語で比べるには、経路を使えなくする口が要る。今の各言語の試験用 CLI は公開 API (`_ex`) だけで作っていて、強制の口は無い (SPEC は「経路は公開 API に出さない」)。

統括の推し: b。ライブラリに隠れた口を足さずに済み、利用者が実際に当たる条件 (seccomp、`/proc` の無いコンテナ、書けない `/tmp`) そのものを試せる。macOS の強制は各言語の自前の試験に残す。

- [ ] a: 各言語のライブラリに、試験の時だけ効く隠れた口を足す (Rust は feature、Python・Go は環境変数等)。CLI が入力の `"disable": ["thread-cwd", "proc", "d", ...]` を受けてそれを使う。どの OS でも強制できるが、公開しない口を 3 言語 (今後 5 言語) に持たせ、口が本番で効かないことも保証する必要がある
- [ ] b: 口は作らず、run.py が Linux のコンテナの環境で強制する (seccomp の filter を掛けて thread-cwd を使えなくする、`/proc` を見せない、`/tmp`・`TMPDIR`・ソケットのディレクトリ以外に書けなくして D を作れなくする)。ライブラリは変えないが、強制できるのは Linux だけで、docker が要る。環境では作れない場面もある (bind はソケットのディレクトリに書けるので、そこに D を作れてしまい、D 無しの形 (`-sockdir`) に進ませられない)
- [ ] c: 強制の場面は適合試験に入れず、各言語の自前の試験に任せたまま (今の形)
