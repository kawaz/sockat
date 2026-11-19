# DR-0015: any 系を作らず、既定の操作ごとに後始末・診断つきの `_ex` を置き、最終手段を使うかを引数 1 つで選ぶ

- Status: Active
- Date: 2026-11-19

## Context

- 既定の bind / connect は、標準と同じに振る舞い、安全でない綴りを残さない経路だけを使う ([DR-0012](DR-0012-own-directory-and-thread-cwd.md))。そのため届かない環境が残る
  - fork の無い言語 (Python、Go) の bind: NetBSD / OpenBSD / illumos の長いパス全部、スレッド cwd も `/proc` も使えない Linux、`pthread_fchdir_np` が無い Apple の OS
  - connect: fork でしか届かない所
- 届かせる手はあるが、どれも何かを失う (fork の副作用、他の利用者が作り直せる綴り)。失ってでも届かせたい人と、失いたくない人がいる
- 長いパスでは、カーネルが覚えている綴りが元のパスでないので、標準が listener を閉じる時にソケットのファイルを消す言語 (Go) でも消えない。元のパスで、自分が作ったファイルだけを消す口が要る
- listener は利用者が asyncio / `http.Serve` / tokio 等に渡す。Rust は所有権で listener を move するので、消す口が閉じる対象を持てない

## Decision

### `_ex` の操作

- any 系 (`bind_any`、`connect_any`、`connect_any_nonblocking`、Rust の feature `any`、Python の `sockat.any`、Go の `atanycost`) は作らない
- 代わりに、後始末つき・診断つきの `_ex` を、既定の操作ごとに 1 つずつ置く

| 既定の操作 | `_ex` | Go |
|---|---|---|
| `bind` | `bind_ex` | `ListenEx` |
| `connect` | `connect_ex` | `DialEx` |
| `connect_nonblocking` | `connect_nonblocking_ex` | なし |

- 名前は仮。各言語の慣習で決める
- 既定の操作 (`bind`、`connect`、`connect_nonblocking`) は変えない。最終手段は使わず、診断も返さない

### 最終手段

- `_ex` の引数で選べるのは「最終手段を使うか」の 1 つだけ。既定は使わない。経路を自由に組み合わせる口は作らない (kawaz「素人が下手な組み合わせで微妙な使い方をする意味は無い」)
- 最終手段は「何かを失ってでも届かせる」経路。何を失うかは `_ex` の説明に並べる

| 操作 | 最終手段 |
|---|---|
| `connect_ex`、`connect_nonblocking_ex` | 既定の connect の順が全部使えない時に fork-cwd-direct (ソケットのディレクトリの fd とファイル名)。fork のある言語だけ。無い言語は fork-cwd-direct を `skipped` に理由付きで入れて次へ進む |
| `bind_ex` | 既定の bind の順が全部使えない時に symlink-dir (置き場のソケットのディレクトリを指す symlink) |

- bind の fork-cwd は今まで通り既定の経路で、最終手段ではない
- Apple の OS の広げた sockaddr の bind は最終手段に入れない ([iOS 等で長いパスを bind する経路の issue](../issue/2026-11-19-ios-long-path-bind.md) に残してある)

### `bind_ex` の symlink-dir

- 置き場に、ソケットのディレクトリを指す乱数の名前の symlink を作り、`<置き場>/sockat.XXXXXXXXXX/<ファイル名>` で bind して、すぐ消す
- 置き場は、持ち主だけが書ける置き場を先に、共有の置き場を最後に試す
  - 持ち主だけが書ける: 持ち主が実効 uid で group と other が書けない (`$XDG_RUNTIME_DIR`、macOS の `$TMPDIR` 等)。綴りを作り直せるのは自分だけなので、片付けた後の綴りは何にも当たらない
  - 共有: sticky が立ち、持ち主が root か実効 uid (`/tmp` 等)。他の利用者がその綴りを (Linux の `/proc/net/unix` 等で見て) 作り直せ、上のライブラリや利用者が綴りで unlink した時に、相手の選んだディレクトリの同じ名前のファイルを消させうる

### 何を失ったかを返す

`_ex` は、標準の型 (listener / stream) と一緒に、次の 3 つを返す。`bind_ex` は加えて `discard` を返す (「[`bind_ex` の discard](#bind_ex-の-discard)」)。戻り値の型と項目の名前は各言語の慣習で決める。

| 項目 | 中身 |
|---|---|
| `losses` | 失ったものの名前の並び (下の表の名前。何も失っていなければ空)。分岐に使う |
| `route` | 通った経路の名前 |
| `skipped` | 試して使えなかった経路の並び (試した順)。各要素は `{ name: 経路の名前, reason: 使えなかった理由 }` |

| 失ったものの名前 | 失ったもの | 付く時 |
|---|---|---|
| `respelled` | カーネルが返すアドレスが元のパスでない。標準が listener を閉じる時に消す言語でも消えず、元のパスで消す必要がある (`bind_ex` の `discard()` 等) | bind が標準以外の経路を通った |
| `cwd-relative` | カーネルが覚えた綴りが cwd からの相対パス (渡したパスがそのまま標準に渡った)。cwd を変えた後にその綴りで unlink / stat すると別の場所に当たる。sockat が経路で失わせたものでなく標準が元から持つ危険だが、`_ex` を選んだ利用者は何を失ったかを知りたいので知らせる (kawaz 裁定 2026-11-19) | 相対パス (abstract の名前は除く) で bind が standard を通った |
| `forked` | fork の副作用 (子が fd の複製を持つ、`SIGCHLD`、`pthread_atfork` 等) | fork-cwd・fork-cwd-sockdir・fork-cwd-direct を通った |
| `recreatable-spelling` | カーネルが返す綴りが共有の置き場 (`/tmp` 等) を通る。名前は乱数なので事前には当てられないが、bind の後は他の利用者に見えうる (Linux の `/proc/net/unix`)。他の利用者がそれを作り直した後にその綴りで unlink すると、相手の選んだディレクトリの同じ名前のファイルを消しうる。元のパス (`discard()` 等) で消せば当たらない。名前の長さは防御でない (名前は bind の後に見える) | `bind_ex` が最終手段で共有の置き場の symlink-dir を通った |

- 名前は約束で、変えずに足すだけ。知らない名前は「何かを失った」とだけ読むと説明に書く。各言語は enum 等で表してよいが、文字列にした時は SPEC の名前と同じにする
- connect の綴りは相手に残らないので、connect で付くのは `forked` だけ
- 持ち主だけが書ける置き場の symlink-dir は `respelled` だけ
- 成功した時、`route` より前に試した経路はすべて「使えなかった」もの (実際に bind / connect して失敗したら、そこでエラーを返して次を試さない)。そのため「使えたか」の真偽値は持たず、通った経路と飛ばした経路を分ける
- `route`・`skipped` の名前と `reason` は診断用で、中身を約束しない。飛ばした経路と理由は、なぜその経路に落ちたかを利用者の手元で調べ、OS や使える手段ごとの整理に使える

### `bind_ex` の discard

- `bind_ex` は、ファイルを消す口 `discard` を返す
- `discard` はファイルを消すだけで、listener を閉じない。listener を閉じるのは利用者
- 名前は `discard` (閉じる意味を含むなら `dispose` 等にするところ。消すだけなので `discard`)

| 言語 | 形 |
|---|---|
| Rust | `bind_ex` の戻り値に、`discard(self) -> io::Result<()>` を持つ `SocketFile` を含める。Drop では消さない |
| Python | `bind_ex` の戻り値に、引数なしの関数 `discard` を含める |
| Go | `ListenEx` の戻り値に `discard func() error` を含める。短いパスでも消すのは discard だけにする (`SetUnlinkOnClose(false)`) |

- `discard` の確かめ方・成功と失敗の条件は SPEC の「公開する操作」
- 置き換えの見分けは `(st_dev, st_ino)` だけで行い、約束するのは listener を開いている間の置き換えまで。閉じた後に消して作り直された物は、番号をすぐ使い回すファイルシステム (ext4、BSD の UFS / FFS) で見分けられない。`discard()` は listener を閉じる前に呼ぶよう勧める (kawaz 裁定 2026-11-19。実測は [findings](../findings/2026-11-19-inode-reuse-after-close.md))

### 失敗した時

- `_ex` が失敗した時も、エラーに `skipped` を付ける。実際に bind / connect して失敗した経路があれば、その名前 (`route`) も付ける (全部が使えなかった `ENAMETOOLONG` では無い)
- 付け方は各言語の慣習に従う。OS のエラーの errno はこれまでどおり取り出せる形を保つ (Rust は errno を持つエラー型に `skipped` を持たせる、Go は `Unwrap` で errno に届くエラー型、Python は例外の属性 等)

理由:

- 最終手段を使う引数を渡す手間が「失うものを受け入れる」という意思表示になる
- 別の関数・別のパッケージにすると API が増え、推奨コードと結び付けにくい (案 A)
- 経路の名前を契約にすると、経路の追加・変更が破壊的変更になる。利用者が知りたいのは経路でなく失ったもの
- 失うものには大小が無く (fork と共有の置き場の symlink-dir は互いを含まない)、標準の経路でも失うものが出うる。名前の並びなら、包含や順を考えずに足せる (kawaz 裁定 2026-11-19)
- 失敗した時こそ、なぜ届かなかったかを知りたい (kawaz 裁定 2026-11-19)
- `discard` が消すだけなら 3 言語でそろい、listener を他のライブラリに渡した後で二重に閉じることが起きない
- `discard` が無ければ利用者は元のパスで消す。閉じた後の置き換えを見分けられなくても、それより悪くならない。閉じた後まで見分けるために fd を持ち続けると、`discard` を使わない利用者にも fd と umount の妨げを背負わせる (kawaz 2026-11-19)

- 相対パスの時は、パスを何も引く前と、bind と覚えるための realpath の両方の後でプロセスの cwd の `(st_dev, st_ino)` を比べ、違えば覚えられない時と同じに扱う (間の cwd の変更で、元の cwd の無関係なファイルを覚えて消さないため。sockat-go の指摘 2026-11-19。入口で絶対パスにする案は、短い相対パスが標準と違う経路に回り振る舞いが変わるので採らない)

## Alternatives Considered

- 案 A: any 系を別の関数・別のパッケージで置く (`bind_any`、`connect_any` 系、Rust の feature `any`、Python の `sockat.any`、Go の `atanycost`)
  - 不採用理由: API が増える。Go のパッケージ名の問題がある。feature の後ろに隠すと推奨コードと結び付けにくい
- 案 B: 経路を自由に選べる引数を `_ex` に持たせる
  - 不採用理由: 素人が下手な組み合わせで微妙な使い方をする意味は無い (kawaz)
- 案 C: fork の無い言語の既定の bind に symlink-dir を戻す
  - 不採用理由: 選んでいない利用者にも安全でない綴りを残す
- 案 D: 最終手段の symlink-dir の置き場を持ち主だけが書ける置き場に限る
  - 不採用理由: BSD 等で `/tmp` しか無いと届かない。「何かを失ってでも届かせる」の意図に合わない (共有の置き場は最後で、`recreatable-spelling` で知らせる)
- 案 E: 失ったものを真偽値 (標準か、fork か、共有の置き場の symlink-dir か) で返す
  - 不採用理由: 失うものが増えるたびに型が変わる
- 案 F: 失ったものを段階 (標準 / 綴り替え / fork / 共有の置き場の symlink-dir) の 1 つの値で返す
  - 不採用理由: 失うものに大小が無いのに並びを作ることになり、新しい失うものを隙間に入れたくなる。標準の経路で通った時の注意も表せない
- 案 G: 経路の名前を契約として返す
  - 不採用理由: 経路の追加・変更が破壊的変更になる
- 案 H: 試した経路を `{名前, 使えたか, 理由?}` の 1 つの並びで返す
  - 不採用理由: 成功時は最後の 1 つだけが使えたものになるので、真偽値と省略できる理由が起きない組み合わせを許す
- 案 I: `discard` が listener を閉じてから消す
  - 不採用理由: Rust は listener を move するので作れず、言語ごとに形が割れる。渡した先のライブラリが閉じた後の二重の close も起きる
- 案 J: `bind_ex` が `O_PATH` (のある OS) でソケットのファイルを開いて持ち、閉じた後も番号を使い回させない
  - 不採用理由: `discard` を呼ばない利用者も fd を持ち続け (Python・Go は GC まで)、閉じた後もファイルシステムを umount できない。`O_PATH` の無い OS (NetBSD・OpenBSD・illumos・Apple の OS) では効かず、OS で約束が割れる
- 案 K: birth time か ctime も比べる
  - 不採用理由: birth time は取れない OS・ファイルシステム・言語の版があり、時刻の粒度が粗いカーネルでは同じ tick の作り直しを見分けられない。ctime は利用者の chmod / chown で変わり、自分のファイルを消さなくなる

## Consequences

- 各言語の実装の any 系 (Rust の feature `any` と `bind_any`・`connect_any` 系等) を `_ex` に置き換える
- fork の無い言語 (Python、Go) も `connect_ex` 系を出す。最終手段を使っても fork-cwd-direct は `skipped` に入り、届く所は既定の connect と同じ
- SPEC の「公開する操作」と、any 系を書いていた所を `_ex` に直す

## 関連

- 裁定: kawaz (2026-11-19。any 系を作らず `_ex` に統合する、`_ex` の引数は最終手段を使うかの 1 つだけ、置き場の順、失ったものは名前の並び、経路は通った経路と飛ばした経路 (理由つき) で診断用、失敗した時も飛ばした経路を返す、`discard` は消すだけ)
- [DR-0012](DR-0012-own-directory-and-thread-cwd.md)
