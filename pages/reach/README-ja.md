# 届く範囲

> [English](./README.md) | 日本語

sockat で長いパスに届くか、どの経路で届くか、届かなければなぜかを、条件の組み合わせごとに並べた表。[DR-0017](../../docs/decisions/DR-0017-resolve-through-persistent-base.md) の設計 (置き場 B を使い回し resolve の綴りを先に、fork なし) と [SPEC](../../docs/SPEC-ja.md) に対して作る。数字は綴りの長さからの見積もり。

- 選んで絞り込むページ: [index.html](index.html?lang=ja) (JS の無い環境ではこの README を読む)
- 正本: [model.json](model.json)。この README (日本語版と英語版) と `data/` は [gen.py](gen.py) が生成する (`just reach`)。手で直さない。ずれは `just reach-check` が拾う
- fork-cwd の手法と、それなら届く場面: [fork-cwd](../fork-cwd-ja.md)

## 畳み方

- 表は操作ごと、OS ごとに分ける。行は条件の組み合わせ、列は条件と結果
- 全部の組み合わせを計算し、結果 (届くか・経路・綴り・理由・根拠) が同じで 1 つの条件の値だけが違う行を 1 行にまとめる。まとまらなくなるまで繰り返す
- ファイル名と、元のパスと相対パスの短い方の長さは、どれかの経路の綴りが収まるか収まらないかが変わる境目で帯に分ける。帯の中では結果が変わらない (gen.py が帯の両端で確かめる)
- 表の中のどの行でも「全部」になる条件は列に出さず、表の上に「効かない条件」として書く
- 置き場の長さは代表値で計算する (「条件」の置き場の表)。パス全体の長さは、ディレクトリが標準に渡す長さを超えるほど深い前提で、PATH_MAX まで効かない
- 言語は、作れない経路 (lacks) で結果が変わる所だけ分かれる

## 見積もりと実測

- 根拠の列が「見積もり」のセルは、model.json の綴りの式と代表値から計算しただけ
- 「実測」のセルは、DR-0017 の前の実装を適合試験 ([conformance/cases.json](../../conformance/cases.json)) に流した結果が、計算と同じ経路だった場面の名前。当てるのは DR-0017 で変わらない connect の経路 (at-direct・proc-direct・relative・widened) の行だけで、条件が全部分かる場面だけを当てる
- 入力のうち実測したもの: bind が symlink を辿る OS ([findings](../../docs/findings/2026-11-19-bind-through-file-symlink.md))、0700 の親の下の 0711 は別の uid が辿れないこと (DR-0017 の Context の実測)、docker の seccomp で `unshare` が断られること ([conformance.md](../../docs/design/conformance.md))

見積もりの前提:

| 値 | バイト | 中身 |
|---|---|---|
| `D` | 10 | D の名前 (乱数、英数 10 文字。DR-0017) |
| `E` | 2 | resolve の E の名前。プロセスの中の 36 進のカウンタ (DR-0017)。36 個までは 1 文字、1296 個まで 2 文字で、2 文字として見積もる |
| `Er` | 10 | 呼び出しごとの E (thread-cwd・at と既定の connect の link-file) の名前 (乱数、英数 10 文字。DR-0017) |
| `Bname` | 11 | B の名前 sockat-<uid> の長さ。uid を 4 桁 (例 1000) で見積もる (macOS の 501 は 1 短く、大きな uid はその分長い) |
| `Bname_runtime` | 6 | $XDG_RUNTIME_DIR の下の B の名前 sockat の長さ |
| `pid` | 7 | procB の <pid> の桁。Linux の pid_max 4194304 で 7 桁 (小さい pid ではその分届くファイル名が延びる) |
| `fd` | 2 | fd の番号の桁 (2 桁) |
| `name_max` | 255 | ファイル名の上限 (NAME_MAX)。表のファイル名の帯はここまで |
| `widened` | 253 | Apple の OS の広げた sockaddr に入るパスの長さ (SPEC の widened) |

## 条件

| 条件 | 効く操作 | 中身 |
|---|---|---|
| OS | 全部 |  |
| 言語 | 全部 |  |
| ファイル名 (バイト) | 全部 | 境目は各経路の綴りの長さの式から計算する |
| 元のパスと相対パスの短い方 (バイト) | 既定の connect | relative・widened の綴り。相対パスは cwd から作る (SPEC-routes の「相対パスの作り方」) |
| スレッドの cwd を使える | 既定の bind<br>bind_ex<br>既定の connect | Linux は seccomp の filter が掛かっていない・unshare が通る、Apple の OS は pthread_fchdir_np がある |
| /proc を使える | 全部 |  |
| bind が symlink を辿る | 既定の bind<br>bind_ex | 辿るかを実測していない OS だけの条件 (既定の bind と bind_ex は実行時に見分ける)。実測した OS は OS で決まる。resolve_for_bind は実測した OS (macOS・NetBSD) だけで link-file を使う |
| /tmp | 既定の bind<br>bind_ex<br>resolve_for_bind<br>既定の connect<br>resolve_for_connect | B の置き場の 1 番目 |
| $XDG_RUNTIME_DIR | 既定の bind<br>bind_ex<br>resolve_for_bind<br>既定の connect<br>resolve_for_connect | B の置き場の 2 番目 |
| $TMPDIR | 既定の bind<br>bind_ex<br>resolve_for_bind<br>既定の connect<br>resolve_for_connect | B の置き場の 3 番目 |
| ソケットのディレクトリに書ける | 既定の connect<br>resolve_for_connect | B の置き場の 4 番目。bind はソケットのファイルを作るので書ける前提 |
| Options.base | bind_ex<br>resolve_for_bind<br>resolve_for_connect | B そのもののパス。指定すると自動の置き場を使わない。usable_cross_uid と一緒で途中と base 自身が other に x を持たなければ EPERM。途中が無い等の確かめのエラーは表に入れない |
| PrivateTmp (自分か相手が /tmp を隔離) | 既定の bind<br>bind_ex<br>resolve_for_bind | systemd の PrivateTmp 等。綴りを相手が辿れるかにだけ効く |
| Options.usable_cross_uid (別の uid の相手) | bind_ex<br>resolve_for_bind | 指定して別の uid の相手と通信する。B の選び方 (途中と B 自身が other に x の所だけ)、procB を使わないこと、綴りを相手が辿れるかに効く |

B の選び方 ([SPEC-routes の「B の作り方」](../../docs/SPEC-routes-ja.md#b-の作り方)):

- B は、`Options.base` を指定しなければ、`/tmp` → `$XDG_RUNTIME_DIR` → `$TMPDIR` → ソケットのディレクトリの順に見る。作らずに分かる外れ (置き場が無い。`usable_cross_uid` では other に x が無い) を飛ばし、残った最初の置き場で綴りの長さを見積もる。収まらなければそこで止まり次の置き場に移らない。見積もりに通った後に作れなければ (書けない等) 次の置き場で同じことをする。`Options.base` も作る前に見積もる。`/tmp`・`$XDG_RUNTIME_DIR`・`$TMPDIR` の B はプロセスごとに 1 つ、ソケットのディレクトリの B はディレクトリごと。表は B をまだ持っていないプロセスの 1 回目の呼び出しで計算する
- 綴りは procB (`/proc` を使えて収まる時) → B の実パス。B がソケットのディレクトリにある時は実パスの綴りが元のパスより長いので procB だけ
- `usable_cross_uid` の時は、同じ順のうち途中と B 自身が other に x の所だけを B に使い、procB を使わない。この B は普段の B と別の枠で、同じディレクトリなら共有する。無いか収まらなければ thread-cwd / at
- thread-cwd・at の E は普段の B (最初に作れた置き場) の D の中に作る。綴りに B が出ないので見積もりによらない。bind ではソケットのディレクトリに書けるので、いつも B を作れる

置き場 (代表値。長さは実パスのバイト数、B の実パスは置き場 + `/` + B の名前。`Options.base` は指定した所が B。書けない置き場も、作る前の見積もりに使うので長さを持つ):

| 置き場 | OS | 値 | 長さ | B の実パスの長さ | 別の uid が辿れる | /tmp・/var/tmp の下 |
|---|---|---|---|---|---|---|
| /tmp | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS<br>FreeBSD<br>NetBSD<br>OpenBSD<br>illumos<br>その他の Unix | 書ける (1777) | 4、12 | 16、24 | ○ | ○ |
| /tmp | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS<br>FreeBSD<br>NetBSD<br>OpenBSD<br>illumos<br>その他の Unix | 書けない (作る前の見積もりには使う) | 4、12 | 16、24 | ○ | ○ |
| $XDG_RUNTIME_DIR | Linux / Android | /run/user/<uid> (14、0700) | 14 | 21 | × | × |
| $XDG_RUNTIME_DIR | Linux / Android | /run/user/<uid> に書けない (14。作る前の見積もりには使う) | 14 | 21 | × | × |
| $TMPDIR | Linux / Android<br>FreeBSD<br>NetBSD<br>OpenBSD<br>illumos<br>その他の Unix | /var/tmp (8、1777) | 8 | 20 | ○ | ○ |
| $TMPDIR | Linux / Android<br>FreeBSD<br>NetBSD<br>OpenBSD<br>illumos<br>その他の Unix | 深い所 (113、0700 の下) | 113 | 125 | × | × |
| $TMPDIR | macOS<br>iOS 等の他の Apple の OS | 既定 (/private/var/folders/…/T、56、0700) | 56 | 68 | × | × |
| $TMPDIR | macOS<br>iOS 等の他の Apple の OS | 深い所 (113、0700 の下) | 113 | 125 | × | × |
| ソケットのディレクトリ | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS<br>FreeBSD<br>NetBSD<br>OpenBSD<br>illumos<br>その他の Unix | 書ける | — | — | — | — |
| Options.base | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS<br>FreeBSD<br>NetBSD<br>OpenBSD<br>illumos<br>その他の Unix | /tmp/app-<uid>/sockat (20、0700 の下) | 20 | 20 | × | ○ |
| Options.base | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS<br>FreeBSD<br>NetBSD<br>OpenBSD<br>illumos<br>その他の Unix | 深い所 (113、0700 の下) | 113 | 113 | × | × |

## 経路

| 操作 | 順 | 経路 | 綴り | 届くファイル名 | OS | 要る物 | 綴りの性質 (bind) |
|---|---|---|---|---|---|---|---|
| 既定の bind | 1 | link-dir (procB) | `/proc/<pid>/fd/<fd>/<D>/<E>/<F>` | sockaddr − 34 | Linux / Android | /proc<br>usable_cross_uid の指定で飛ばす<br>B を作れる (D をその中に) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true |
| 既定の bind | 2 | link-dir (B の実パス) | `<B>/<D>/<E>/<F>` | sockaddr − 15 − B の実パス | 全部 | B の実パスの綴り (usable_cross_uid の指定では途中と B 自身が other に x の B。B がソケットのディレクトリにあれば使えない) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: B までの途中と B 自身が other に x なら true<br>usable_with_private_tmp: B が /tmp・/var/tmp の下でなければ true |
| 既定の bind | 3 | link-file (B の実パス) | `<B>/<D>/<E>` | よらない (B の実パス ≤ sockaddr − 14) | 全部 | bind が symlink を辿る (実測した OS は OS で、他は実行時に見分ける)<br>B の実パスの綴り (usable_cross_uid の指定では途中と B 自身が other に x の B。B がソケットのディレクトリにあれば使えない) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: B までの途中と B 自身が other に x なら true<br>usable_with_private_tmp: B が /tmp・/var/tmp の下でなければ true |
| 既定の bind | 4 | thread-cwd | `<Er>/<F>` | sockaddr − 11 | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS | スレッドの cwd<br>B を作れる (D をその中に) | Dangling |
| 既定の bind | 5 | at | `<Er>/<F>` | sockaddr − 11 | FreeBSD | B を作れる (D をその中に) | Dangling |
| bind_ex | 1 | link-dir (procB) | `/proc/<pid>/fd/<fd>/<D>/<E>/<F>` | sockaddr − 34 | Linux / Android | /proc<br>usable_cross_uid の指定で飛ばす<br>B を作れる (D をその中に) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true |
| bind_ex | 2 | link-dir (B の実パス) | `<B>/<D>/<E>/<F>` | sockaddr − 15 − B の実パス | 全部 | B の実パスの綴り (usable_cross_uid の指定では途中と B 自身が other に x の B。B がソケットのディレクトリにあれば使えない) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: B までの途中と B 自身が other に x なら true<br>usable_with_private_tmp: B が /tmp・/var/tmp の下でなければ true |
| bind_ex | 3 | link-file (B の実パス) | `<B>/<D>/<E>` | よらない (B の実パス ≤ sockaddr − 14) | 全部 | bind が symlink を辿る (実測した OS は OS で、他は実行時に見分ける)<br>B の実パスの綴り (usable_cross_uid の指定では途中と B 自身が other に x の B。B がソケットのディレクトリにあれば使えない) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: B までの途中と B 自身が other に x なら true<br>usable_with_private_tmp: B が /tmp・/var/tmp の下でなければ true |
| bind_ex | 4 | thread-cwd | `<Er>/<F>` | sockaddr − 11 | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS | スレッドの cwd<br>B を作れる (D をその中に) | Dangling |
| bind_ex | 5 | at | `<Er>/<F>` | sockaddr − 11 | FreeBSD | B を作れる (D をその中に) | Dangling |
| resolve_for_bind | 1 | link-dir (procB) | `/proc/<pid>/fd/<fd>/<D>/<E>/<F>` | sockaddr − 34 | Linux / Android | /proc<br>usable_cross_uid の指定で飛ばす<br>B を作れる (D をその中に) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true |
| resolve_for_bind | 2 | link-dir (B の実パス) | `<B>/<D>/<E>/<F>` | sockaddr − 15 − B の実パス | 全部 | B の実パスの綴り (usable_cross_uid の指定では途中と B 自身が other に x の B。B がソケットのディレクトリにあれば使えない) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: B までの途中と B 自身が other に x なら true<br>usable_with_private_tmp: B が /tmp・/var/tmp の下でなければ true |
| resolve_for_bind | 3 | link-file (B の実パス) | `<B>/<D>/<E>` | よらない (B の実パス ≤ sockaddr − 14) | 全部 | bind が symlink を辿ると実測した OS (macOS・NetBSD)<br>B の実パスの綴り (usable_cross_uid の指定では途中と B 自身が other に x の B。B がソケットのディレクトリにあれば使えない) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: B までの途中と B 自身が other に x なら true<br>usable_with_private_tmp: B が /tmp・/var/tmp の下でなければ true |
| 既定の connect | 1 | proc-direct | `/proc/self/fd/<fd>/<F>` | sockaddr − 17 | Linux / Android | /proc を使える時だけ |  |
| 既定の connect | 2 | relative | `<rel>` | よらない (相対パス ≤ sockaddr) | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS<br>NetBSD<br>OpenBSD<br>illumos<br>その他の Unix | /proc を使えない時だけ |  |
| 既定の connect | 3 | widened | `<rel>` | よらない (相対パス ≤ 253) | macOS<br>iOS 等の他の Apple の OS | — |  |
| 既定の connect | 4 | at-direct | `<F>` | sockaddr | FreeBSD | — |  |
| 既定の connect | 5 | thread-cwd-direct | `<F>` | sockaddr | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS | スレッドの cwd |  |
| 既定の connect | 6 | link-file (B の実パス) | `<B>/<Er>` | よらない (B の実パス ≤ sockaddr − 11) | 全部 | B の実パスの綴り (usable_cross_uid の指定では途中と B 自身が other に x の B。B がソケットのディレクトリにあれば使えない) |  |
| resolve_for_connect | 1 | link-file (procB) | `/proc/<pid>/fd/<fd>/<D>/<E>` | よらない | Linux / Android | /proc<br>B を作れる (D をその中に) |  |
| resolve_for_connect | 2 | link-file (B の実パス) | `<B>/<D>/<E>` | よらない (B の実パス ≤ sockaddr − 14) | 全部 | B の実パスの綴り (usable_cross_uid の指定では途中と B 自身が other に x の B。B がソケットのディレクトリにあれば使えない) |  |

綴りの記号: `<F>` はファイル名、`<rel>` は元のパスと相対パスの短い方、`<B>` は B の実パス、それ以外は「見積もりの前提」の値。sockaddr は sockaddr に入る長さ (Linux / illumos 107、他 103)。表の経路の列の `(B: …)` はどの B を通ったかで、名前は診断の `base` の値 (`Options.base` の B は `given`)

## まとめ: ファイル名の長さごとに届くか

表の全部の条件の組み合わせを、ファイル名の帯ごとにまとめた物。「条件しだい」はスレッドの cwd・`/proc`・置き場・Options・相対パスの長さ等で届いたり届かなかったりする帯。「普段の環境で届く」の条件: まとめの表の「普段の環境」。スレッドの cwd と /proc を使え、置き場は OS の既定のまま書け、Options は指定せず、PrivateTmp とも関わらない。相対パスの長さと、bind が symlink を辿るかを実測していない OS の辿るかは、どの値でも届く時だけ届くとする

| 操作 | OS | 言語 | 普段の環境で届く | どの条件でも届く | 条件しだい | どの条件でも届かない |
|---|---|---|---|---|---|---|
| 既定の bind | Linux / Android | rs<br>py<br>go | 1–96 | — | 1–96 | 97–255 |
| 既定の bind | Linux / Android | ts-node<br>ts-bun | 1–76 | — | 1–76 | 77–255 |
| 既定の bind | macOS | 全部 | 1–255 | — | 1–255 | — |
| 既定の bind | iOS 等の他の Apple の OS | rs<br>py<br>go | 1–92 | — | 1–255 | — |
| 既定の bind | iOS 等の他の Apple の OS | ts-node<br>ts-bun | 1–64 | — | 1–255 | — |
| 既定の bind | FreeBSD | rs<br>py<br>go | 1–92 | 1–92 | — | 93–255 |
| 既定の bind | FreeBSD | ts-node<br>ts-bun | 1–72 | — | 1–72 | 73–255 |
| 既定の bind | NetBSD | 全部 | 1–255 | — | 1–255 | — |
| 既定の bind | OpenBSD | 全部 | 1–72 | — | 1–72 | 73–255 |
| 既定の bind | illumos | 全部 | 1–76 | — | 1–76 | 77–255 |
| 既定の bind | その他の Unix | 全部 | 1–72 | — | 1–255 | — |
| bind_ex | Linux / Android | rs<br>py<br>go | 1–96 | — | 1–96 | 97–255 |
| bind_ex | Linux / Android | ts-node<br>ts-bun | 1–76 | — | 1–76 | 77–255 |
| bind_ex | macOS | 全部 | 1–255 | — | 1–255 | — |
| bind_ex | iOS 等の他の Apple の OS | rs<br>py<br>go | 1–92 | — | 1–255 | — |
| bind_ex | iOS 等の他の Apple の OS | ts-node<br>ts-bun | 1–64 | — | 1–255 | — |
| bind_ex | FreeBSD | rs<br>py<br>go | 1–92 | — | 1–92 | 93–255 |
| bind_ex | FreeBSD | ts-node<br>ts-bun | 1–72 | — | 1–72 | 73–255 |
| bind_ex | NetBSD | 全部 | 1–255 | — | 1–255 | — |
| bind_ex | OpenBSD | 全部 | 1–72 | — | 1–72 | 73–255 |
| bind_ex | illumos | 全部 | 1–76 | — | 1–76 | 77–255 |
| bind_ex | その他の Unix | 全部 | 1–72 | — | 1–255 | — |
| resolve_for_bind | Linux / Android | 全部 | 1–76 | — | 1–76 | 77–255 |
| resolve_for_bind | macOS | 全部 | 1–255 | — | 1–255 | — |
| resolve_for_bind | iOS 等の他の Apple の OS | 全部 | 1–64 | — | 1–68 | 69–255 |
| resolve_for_bind | FreeBSD | 全部 | 1–72 | — | 1–72 | 73–255 |
| resolve_for_bind | NetBSD | 全部 | 1–255 | — | 1–255 | — |
| resolve_for_bind | OpenBSD | 全部 | 1–72 | — | 1–72 | 73–255 |
| resolve_for_bind | illumos | 全部 | 1–76 | — | 1–76 | 77–255 |
| resolve_for_bind | その他の Unix | 全部 | 1–72 | — | 1–72 | 73–255 |
| 既定の connect | Linux / Android | 全部 | 1–255 | — | 1–255 | — |
| 既定の connect | macOS | 全部 | 1–255 | — | 1–255 | — |
| 既定の connect | iOS 等の他の Apple の OS | 全部 | 1–255 | — | 1–255 | — |
| 既定の connect | FreeBSD | rs<br>py<br>go | 1–255 | 1–103 | 104–255 | — |
| 既定の connect | FreeBSD | ts-node<br>ts-bun | 1–255 | — | 1–255 | — |
| 既定の connect | NetBSD | 全部 | 1–255 | — | 1–255 | — |
| 既定の connect | OpenBSD | 全部 | 1–255 | — | 1–255 | — |
| 既定の connect | illumos | 全部 | 1–255 | — | 1–255 | — |
| 既定の connect | その他の Unix | 全部 | 1–255 | — | 1–255 | — |
| resolve_for_connect | Linux / Android | 全部 | 1–255 | — | 1–255 | — |
| resolve_for_connect | macOS | 全部 | 1–255 | — | 1–255 | — |
| resolve_for_connect | iOS 等の他の Apple の OS | 全部 | 1–255 | — | 1–255 | — |
| resolve_for_connect | FreeBSD | 全部 | 1–255 | — | 1–255 | — |
| resolve_for_connect | NetBSD | 全部 | 1–255 | — | 1–255 | — |
| resolve_for_connect | OpenBSD | 全部 | 1–255 | — | 1–255 | — |
| resolve_for_connect | illumos | 全部 | 1–255 | — | 1–255 | — |
| resolve_for_connect | その他の Unix | 全部 | 1–255 | — | 1–255 | — |

## 環境によらず届く長さ (下限)

上の表は典型の桁 (uid 4 桁・pid 7 桁・fd 2 桁・E 2 文字) で見積もっている。ここは各桁を最悪にした時のファイル名の長さ (バイト)。この長さ以下なら環境によらず届く。試験や案内で長さを決め打ちするならこの下限を使う (典型の桁の表の値はこれより長い)

| 値 | 最悪の桁 | 中身 |
|---|---|---|
| `pid` | 7 | procB の pid の桁。Linux の pid_max の上限 4194304 (最大の pid は 4194303) |
| `fd` | 7 | B の fd の桁。Linux の fs.nr_open の既定 1048576 (最大の fd は 1048575) |
| `uid` | 10 | B の名前の uid の桁。uid_t は 32 ビットで最大の有効な uid は 4294967294 |
| `E` | 2 | resolve の E の名前の文字数。1 プロセスの resolve の E が 1296 個まで |

前提: B が既定の名前 `sockat-<uid>` で `/tmp` にある。Linux は経路の式 (`<B>/<D>/<E>/<F>` など、経路の表の綴り) に最悪の桁を入れて出す。

| OS | 操作 | 条件 | 下限 |
|---|---|---|---|
| Linux | bind | スレッドの cwd を使えない (docker の既定 seccomp 等) | 70 |
| Linux | bind | スレッドの cwd を使える | 96 |
| Linux | connect | B を `/tmp` に作れる (link-file) | ファイル名によらず届く |
| Linux | connect | B を作れず proc-direct だけ | 85 |
| macOS | bind | B が `/tmp` にある (link-file) | 255 (NAME_MAX) |
| macOS | connect | B が `/tmp` にある (link-file) | 255 (NAME_MAX) |
| macOS | bind | `/tmp` に B を作れず `$TMPDIR` が深い (thread-cwd) | 92 |
| macOS | connect | `/tmp` に B を作れず `$TMPDIR` が深い (thread-cwd-direct) | 103 |

- Linux の bind でスレッドの cwd を使えない時、実パスの B を通る綴りの下限は、B が `sockat-<uid>.<乱数 10 文字>` に落ちた時 11 バイト短い 59 バイト、`$XDG_RUNTIME_DIR` の B の時 65 バイト (E 2 文字)。`/proc` を使えれば procB の綴りも試すので、届く長さはどちらか長い方 (procB は上の最悪の桁で 68)。procB を使わない時 (`/proc` が無い、`usable_cross_uid`) はこの値が下限

## 表

### 既定の bind

bind_ex と同じ順で、Options を取らない。綴りは残す (E はプロセスが終わるまで、D と一緒に OS の掃除で消える)

#### 既定の bind / Linux / Android

| 言語 | ファイル名 (バイト) | スレッドの cwd を使える | /proc を使える | $XDG_RUNTIME_DIR | $TMPDIR | /tmp | PrivateTmp (自分か相手が /tmp を隔離) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 1–73 | 全部 | ○ | 全部 | 全部 | 書ける (1777) | 全部 | ○ | link-dir (B: proc) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 全部 | 1–73 | 全部 | ○ | 全部 | /var/tmp (8、1777)<br>深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-dir (B: proc) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 全部 | 1–73 | 全部 | ○ | /run/user/<uid> (14、0700) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-dir (B: proc) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 全部 | 1–73 | 全部 | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-dir (B: sockdir) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 全部 | 1–73 | 全部 | × | 全部 | 全部 | 書ける (1777) | ○ | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 全部 | 1–73 | 全部 | × | 全部 | 全部 | 書ける (1777) | × | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 全部 | 1–71 | 全部 | × | /run/user/<uid> (14、0700) | 全部 | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-dir (B: runtime) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 全部 | 1–71 | 全部 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | ○ | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 全部 | 1–71 | 全部 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | × | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| rs<br>py<br>go | 1–71 | ○ | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 全部 | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 1–71 | × | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–71 | × | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–71 | 全部 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–71 | 全部 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 全部 | 72 | 全部 | × | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | ○ | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 全部 | 72 | 全部 | × | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | × | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| rs<br>py<br>go | 72 | ○ | × | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 全部 | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 72 | ○ | × | /run/user/<uid> (14、0700)<br>/run/user/<uid> に書けない (14。作る前の見積もりには使う) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 72–76 | × | × | /run/user/<uid> (14、0700)<br>/run/user/<uid> に書けない (14。作る前の見積もりには使う) | 全部 | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 72–76 | × | × | 無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 72–76 | × | × | 無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 72–76 | 全部 | × | /run/user/<uid> (14、0700)<br>/run/user/<uid> に書けない (14。作る前の見積もりには使う) | 全部 | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 71<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 72–76 | 全部 | × | 無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 72–76 | 全部 | × | 無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 73 | ○ | × | 全部 | 全部 | 書けない (作る前の見積もりには使う) | 全部 | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 73–76 | × | × | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 73–76 | 全部 | × | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 全部 | 74–76 | 全部 | 全部 | 全部 | 全部 | 書ける (1777) | ○ | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 全部 | 74–76 | 全部 | 全部 | 全部 | 全部 | 書ける (1777) | × | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| rs<br>py<br>go | 74–76 | ○ | 全部 | 全部 | 全部 | 書けない (作る前の見積もりには使う) | 全部 | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 74–76 | × | ○ | /run/user/<uid> (14、0700)<br>/run/user/<uid> に書けない (14。作る前の見積もりには使う) | 全部 | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 74–76 | × | ○ | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 74–76 | × | ○ | 無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 74–76 | × | ○ | 無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 74–76 | 全部 | ○ | /run/user/<uid> (14、0700)<br>/run/user/<uid> に書けない (14。作る前の見積もりには使う) | 全部 | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 71<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 74–76 | 全部 | ○ | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 74–76 | 全部 | ○ | 無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 74–76 | 全部 | ○ | 無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 全部 | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 77–96 | ○ | 全部 | 全部 | 全部 | 全部 | 全部 | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 77–96 | × | ○ | 全部 | 全部 | 全部 | 全部 | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 77–96 | × | × | 全部 | 全部 | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 77–96 | 全部 | ○ | 全部 | 全部 | 全部 | 全部 | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 77–96 | 全部 | × | 全部 | 全部 | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 97–255 | ○ | ○ | 全部 | 全部 | 全部 | 全部 | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| rs<br>py<br>go | 97–255 | ○ | × | 全部 | 全部 | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| rs<br>py<br>go | 97–255 | × | ○ | 全部 | 全部 | 全部 | 全部 | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 97–255 | × | × | 全部 | 全部 | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| ts-node<br>ts-bun | 97–255 | 全部 | ○ | 全部 | 全部 | 全部 | 全部 | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 97–255 | 全部 | × | 全部 | 全部 | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: この言語に無い | — | 見積もり |

#### 既定の bind / macOS

| 言語 | ファイル名 (バイト) | スレッドの cwd を使える | $TMPDIR | /tmp | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 1–64 | 全部 | 全部 | 書ける (1777) | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 全部 | 1–20 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| rs<br>py<br>go | 1–92 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 1–64 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–64 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 全部 | 21–255 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | ○ | link-file (B: tmpdir) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 全部 | 65–255 | 全部 | 全部 | 書ける (1777) | ○ | link-file (B: tmp) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| rs<br>py<br>go | 65–92 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 65–92 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 65–92 | 全部 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 65–92 | 全部 | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | — | 見積もり |

#### 既定の bind / iOS 等の他の Apple の OS

| 言語 | ファイル名 (バイト) | スレッドの cwd を使える | bind が symlink を辿る | $TMPDIR | /tmp | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 1–64 | 全部 | 全部 | 全部 | 書ける (1777) | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 全部 | 1–20 | 全部 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| rs<br>py<br>go | 1–92 | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 1–64 | × | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–64 | × | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–64 | × | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–64 | × | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 全部 | 21–255 | 全部 | ○ | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | ○ | link-file (B: tmpdir) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| rs<br>py<br>go | 21–92 | ○ | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 21–64 | × | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 20<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 21–64 | 全部 | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 20<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 全部 | 65–255 | 全部 | ○ | 全部 | 書ける (1777) | ○ | link-file (B: tmp) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| rs<br>py<br>go | 65–92 | ○ | × | 全部 | 書ける (1777) | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 65–92 | × | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 65–92 | × | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 65–92 | × | × | 全部 | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 65–92 | 全部 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 65–92 | 全部 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 65–92 | 全部 | × | 全部 | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | × | 全部 | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | × | 全部 | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | × | 全部 | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | — | 見積もり |

#### 既定の bind / FreeBSD

| 言語 | ファイル名 (バイト) | $TMPDIR | /tmp | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 1–72 | 全部 | 書ける (1777) | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 全部 | 1–68 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| rs<br>py<br>go | 1–68 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | ○ | at | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| ts-node<br>ts-bun | 1–72 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>at: この言語に無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| ts-node<br>ts-bun | 1–72 | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>at: この言語に無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| rs<br>py<br>go | 69–72 | 全部 | 書けない (作る前の見積もりには使う) | ○ | at | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| ts-node<br>ts-bun | 69–72 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 68<br>at: この言語に無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| rs<br>py<br>go | 73–92 | 全部 | 全部 | ○ | at | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| ts-node<br>ts-bun | 73–92 | 全部 | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>at: この言語に無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| rs<br>py<br>go | 93–255 | 全部 | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>at: ファイル名 > 92 | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>at: この言語に無い | — | 見積もり |

#### 既定の bind / NetBSD

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|
| 1–72 | 全部 | 書ける (1777) | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 1–68 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 1–72 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–255 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | ○ | link-file (B: tmpdir) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 73–255 | 全部 | 書ける (1777) | ○ | link-file (B: tmp) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 73–92 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | — | 見積もり |
| 93–255 | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |

#### 既定の bind / OpenBSD

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|
| 1–72 | 全部 | 書ける (1777) | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 1–68 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 1–72 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–72 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | 全部 | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | 全部 | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | — | 見積もり |

#### 既定の bind / illumos

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|
| 1–76 | 全部 | 書ける (1777) | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 1–72 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 1–76 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–76 | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–76 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 77–96 | 全部 | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 76 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 97–255 | 全部 | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 76 | — | 見積もり |

#### 既定の bind / その他の Unix

効かない条件: 言語

| ファイル名 (バイト) | bind が symlink を辿る | $TMPDIR | /tmp | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1–72 | 全部 | 全部 | 書ける (1777) | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 1–68 | 全部 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 1–72 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): bind が symlink を辿らない | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): bind が symlink を辿らない | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–255 | ○ | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | ○ | link-file (B: tmpdir) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 69–72 | × | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 68<br>link-file (B の実パス): bind が symlink を辿らない | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–255 | ○ | 全部 | 書ける (1777) | ○ | link-file (B: tmp) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (D と一緒に OS の掃除で消えるまで) | — | — | 見積もり |
| 73–92 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | × | 全部 | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): bind が symlink を辿らない | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | — | 見積もり |
| 93–255 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| 93–255 | × | 全部 | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): bind が symlink を辿らない | — | 見積もり |

### bind_ex

resolve の綴り (link-dir・link-file) を先に試し、収まらなければ thread-cwd (FreeBSD は at)

#### bind_ex / Linux / Android

| 言語 | ファイル名 (バイト) | スレッドの cwd を使える | /proc を使える | $XDG_RUNTIME_DIR | $TMPDIR | /tmp | Options.base | PrivateTmp (自分か相手が /tmp を隔離) | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | 全部 | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | 全部 | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 全部 | 1–76 | 全部 | 全部 | 全部 | 全部 | 書ける (1777) | 指定しない | ○ | ○ | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 全部 | 1–76 | 全部 | 全部 | 全部 | 全部 | 書ける (1777) | 指定しない | × | ○ | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 全部 | 1–72 | 全部 | 全部 | 全部 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | ○ | ○ | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 全部 | 1–72 | 全部 | 全部 | 全部 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | × | ○ | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 全部 | 1–73 | 全部 | ○ | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | 全部 | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 全部 | 1–73 | 全部 | ○ | /run/user/<uid> (14、0700) | 全部 | 全部 | 指定しない | 全部 | × | ○ | link-dir (B: proc) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 全部 | 1–73 | 全部 | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | /var/tmp (8、1777)<br>深い所 (113、0700 の下) | 全部 | 指定しない | 全部 | × | ○ | link-dir (B: proc) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 全部 | 1–73 | 全部 | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書ける (1777) | 指定しない | 全部 | × | ○ | link-dir (B: proc) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 全部 | 1–73 | 全部 | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | ○ | link-dir (B: sockdir) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 全部 | 1–72 | 全部 | × | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | ○ | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 全部 | 1–72 | 全部 | × | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 全部 | 1–76 | 全部 | × | 全部 | 全部 | 書ける (1777) | 指定しない | ○ | × | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 全部 | 1–76 | 全部 | × | 全部 | 全部 | 書ける (1777) | 指定しない | × | × | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 全部 | 1–71 | 全部 | × | /run/user/<uid> (14、0700) | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | ○ | link-dir (B: runtime) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 全部 | 1–71 | 全部 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 全部 | 1–71 | 全部 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 全部 | 1–72 | 全部 | × | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 全部 | 1–72 | 全部 | × | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| rs<br>py<br>go | 1–96 | ○ | 全部 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 1–96 | ○ | × | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 1–96 | ○ | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 1–76 | × | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): usable_cross_uid の指定で使わない<br>link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–96 | × | × | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–76 | × | × | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–71 | × | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–71 | × | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–76 | × | × | 無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–76 | × | × | 無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–76 | 全部 | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): usable_cross_uid の指定で使わない<br>link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–96 | 全部 | × | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–76 | 全部 | × | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–71 | 全部 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–71 | 全部 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–76 | 全部 | × | 無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–76 | 全部 | × | 無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 72–96 | ○ | × | /run/user/<uid> (14、0700) | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 72–96 | ○ | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 72–76 | × | × | /run/user/<uid> (14、0700)<br>/run/user/<uid> に書けない (14。作る前の見積もりには使う) | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 72–76 | 全部 | × | /run/user/<uid> (14、0700)<br>/run/user/<uid> に書けない (14。作る前の見積もりには使う) | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 71<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 73–96 | ○ | 全部 | 全部 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 73–96 | ○ | × | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 73–96 | ○ | × | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 73–76 | × | ○ | 全部 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): usable_cross_uid の指定で使わない<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 73–96 | × | × | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 73–76 | × | × | 全部 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 73–76 | × | × | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 73–76 | 全部 | ○ | 全部 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): usable_cross_uid の指定で使わない<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 73–96 | 全部 | × | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 73–76 | 全部 | × | 全部 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 73–76 | 全部 | × | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 全部 | 74–76 | 全部 | ○ | 全部 | 全部 | 書ける (1777) | 指定しない | ○ | × | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 全部 | 74–76 | 全部 | ○ | 全部 | 全部 | 書ける (1777) | 指定しない | × | × | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| rs<br>py<br>go | 74–96 | ○ | ○ | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | 全部 | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 74–96 | ○ | ○ | 全部 | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 74–96 | × | ○ | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 74–96 | × | ○ | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 74–76 | × | ○ | /run/user/<uid> (14、0700)<br>/run/user/<uid> に書けない (14。作る前の見積もりには使う) | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 74–76 | × | ○ | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 74–76 | × | ○ | 無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 74–76 | × | ○ | 無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 74–96 | 全部 | ○ | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 74–96 | 全部 | ○ | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 74–76 | 全部 | ○ | /run/user/<uid> (14、0700)<br>/run/user/<uid> に書けない (14。作る前の見積もりには使う) | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 71<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 74–76 | 全部 | ○ | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 74–76 | 全部 | ○ | 無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 74–76 | 全部 | ○ | 無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 77–96 | ○ | 全部 | 全部 | 全部 | 書ける (1777) | 指定しない | 全部 | 全部 | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 77–96 | × | ○ | 全部 | 全部 | 全部 | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): usable_cross_uid の指定で使わない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 77–96 | × | ○ | 全部 | 全部 | 全部 | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 77–96 | × | × | 全部 | 全部 | 全部 | 指定しない | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 77–96 | 全部 | ○ | 全部 | 全部 | 全部 | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): usable_cross_uid の指定で使わない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 77–96 | 全部 | ○ | 全部 | 全部 | 全部 | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 77–96 | 全部 | × | 全部 | 全部 | 全部 | 指定しない | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 97–255 | ○ | ○ | 全部 | 全部 | 全部 | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): usable_cross_uid の指定で使わない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| rs<br>py<br>go | 97–255 | ○ | ○ | 全部 | 全部 | 全部 | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| rs<br>py<br>go | 97–255 | ○ | ○ | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| rs<br>py<br>go | 97–255 | ○ | ○ | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107)<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| rs<br>py<br>go | 97–255 | ○ | × | 全部 | 全部 | 全部 | 指定しない | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| rs<br>py<br>go | 97–255 | ○ | × | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| rs<br>py<br>go | 97–255 | ○ | × | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107)<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| rs<br>py<br>go | 97–255 | × | ○ | 全部 | 全部 | 全部 | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): usable_cross_uid の指定で使わない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 97–255 | × | ○ | 全部 | 全部 | 全部 | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 97–255 | × | ○ | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 97–255 | × | ○ | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107)<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 97–255 | × | × | 全部 | 全部 | 全部 | 指定しない | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 97–255 | × | × | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 97–255 | × | × | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107)<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| ts-node<br>ts-bun | 97–255 | 全部 | ○ | 全部 | 全部 | 全部 | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): usable_cross_uid の指定で使わない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 97–255 | 全部 | ○ | 全部 | 全部 | 全部 | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 97–255 | 全部 | ○ | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 97–255 | 全部 | ○ | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107)<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 97–255 | 全部 | × | 全部 | 全部 | 全部 | 指定しない | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 76<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 97–255 | 全部 | × | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 97–255 | 全部 | × | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107)<br>thread-cwd: この言語に無い | — | 見積もり |

#### bind_ex / macOS

| 言語 | ファイル名 (バイト) | スレッドの cwd を使える | $TMPDIR | /tmp | Options.base | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 全部 | 1–68 | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 全部 | 1–64 | 全部 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 全部 | 1–20 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 指定しない | × | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| rs<br>py<br>go | 1–92 | ○ | 全部 | 全部 | 深い所 (113、0700 の下) | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 1–92 | ○ | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 指定しない | ○ | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 1–92 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 1–92 | × | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–64 | × | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–64 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–64 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–92 | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 全部 | 21–255 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 指定しない | × | ○ | link-file (B: tmpdir) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 全部 | 65–255 | 全部 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-file (B: tmp) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| rs<br>py<br>go | 65–92 | × | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 65–92 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 65–92 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 65–92 | 全部 | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 65–92 | 全部 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 65–92 | 全部 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 全部 | 69–255 | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-file (B: given) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103)<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103)<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103)<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | — | 見積もり |

#### bind_ex / iOS 等の他の Apple の OS

| 言語 | ファイル名 (バイト) | スレッドの cwd を使える | bind が symlink を辿る | $TMPDIR | /tmp | Options.base | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 全部 | 1–68 | 全部 | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 全部 | 1–64 | 全部 | 全部 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 全部 | 1–20 | 全部 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 指定しない | × | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| rs<br>py<br>go | 1–92 | ○ | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 1–92 | ○ | 全部 | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 1–92 | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 1–92 | × | ○ | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–64 | × | ○ | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–64 | × | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–64 | × | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–92 | × | × | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–64 | × | × | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–64 | × | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–64 | × | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–92 | 全部 | ○ | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | ○ | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–92 | 全部 | × | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | × | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–64 | 全部 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 全部 | 21–255 | 全部 | ○ | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 指定しない | × | ○ | link-file (B: tmpdir) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| rs<br>py<br>go | 21–92 | ○ | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 指定しない | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 21–64 | × | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 20<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 21–64 | 全部 | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 20<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 全部 | 65–255 | 全部 | ○ | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-file (B: tmp) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| rs<br>py<br>go | 65–92 | ○ | × | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 65–92 | × | ○ | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 65–92 | × | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 65–92 | × | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 65–92 | × | × | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 65–92 | 全部 | ○ | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 65–92 | 全部 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 65–92 | 全部 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 65–92 | 全部 | × | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 全部 | 69–255 | 全部 | ○ | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-file (B: given) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| rs<br>py<br>go | 69–92 | ○ | × | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 69–92 | × | × | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 69–92 | 全部 | × | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | ○ | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103)<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | ○ | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | × | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | × | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | ○ | × | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | ○ | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103)<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | ○ | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | × | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | × | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| rs<br>py<br>go | 93–255 | × | × | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | ○ | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103)<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | ○ | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103)<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | × | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | × | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | × | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): bind が symlink を辿らない<br>thread-cwd: この言語に無い | — | 見積もり |

#### bind_ex / FreeBSD

| 言語 | ファイル名 (バイト) | $TMPDIR | /tmp | Options.base | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 全部 | 1–68 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 全部 | 1–72 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 全部 | 1–68 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| rs<br>py<br>go | 1–68 | 全部 | 全部 | 深い所 (113、0700 の下) | × | ○ | at | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 1–68 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | at | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| ts-node<br>ts-bun | 1–92 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>at: この言語に無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| ts-node<br>ts-bun | 1–72 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>at: この言語に無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| ts-node<br>ts-bun | 1–72 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>at: この言語に無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| ts-node<br>ts-bun | 1–72 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>at: この言語に無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| rs<br>py<br>go | 69–92 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | × | ○ | at | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| rs<br>py<br>go | 69–72 | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | at | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| ts-node<br>ts-bun | 69–92 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68<br>at: この言語に無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| ts-node<br>ts-bun | 69–72 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 68<br>at: この言語に無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| rs<br>py<br>go | 73–92 | 全部 | 全部 | 指定しない | 全部 | ○ | at | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| ts-node<br>ts-bun | 73–92 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>at: この言語に無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| rs<br>py<br>go | 93–255 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>at: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68<br>at: ファイル名 > 92 | — | 見積もり |
| rs<br>py<br>go | 93–255 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>at: ファイル名 > 92 | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>at: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68<br>at: この言語に無い | — | 見積もり |
| ts-node<br>ts-bun | 93–255 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>at: この言語に無い | — | 見積もり |

#### bind_ex / NetBSD

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | Options.base | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 1–68 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–68 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–72 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–255 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-file (B: given) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 69–255 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | link-file (B: tmpdir) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 73–255 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-file (B: tmp) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 73–92 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103) | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | — | 見積もり |
| 93–255 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |

#### bind_ex / OpenBSD

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | Options.base | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 1–68 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–68 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–72 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–92 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–72 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | — | 見積もり |
| 93–255 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | — | 見積もり |
| 93–255 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103) | — | 見積もり |

#### bind_ex / illumos

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | Options.base | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 1–72 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–96 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–76 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–72 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–76 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–76 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–76 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–96 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–76 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 77–96 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 76 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 97–255 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 76 | — | 見積もり |
| 97–255 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | — | 見積もり |
| 97–255 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107) | — | 見積もり |

#### bind_ex / その他の Unix

効かない条件: 言語

| ファイル名 (バイト) | bind が symlink を辿る | $TMPDIR | /tmp | Options.base | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 1–68 | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–72 | 全部 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–68 | 全部 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | ○ | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | × | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): bind が symlink を辿らない | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | × | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>link-file (B の実パス): bind が symlink を辿らない | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): bind が symlink を辿らない | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): bind が symlink を辿らない | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–255 | ○ | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-file (B: given) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 69–255 | ○ | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | link-file (B: tmpdir) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 69–92 | × | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68<br>link-file (B の実パス): bind が symlink を辿らない | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–72 | × | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 68<br>link-file (B の実パス): bind が symlink を辿らない | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–255 | ○ | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-file (B: tmp) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 73–92 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | × | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): bind が symlink を辿らない | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | ○ | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103) | — | 見積もり |
| 93–255 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い | — | 見積もり |
| 93–255 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | — | 見積もり |
| 93–255 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| 93–255 | × | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68<br>link-file (B の実パス): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): bind が symlink を辿らない | — | 見積もり |

### resolve_for_bind

bind_ex と同じ順で、パスを返すだけなので thread-cwd・at を持たない

#### resolve_for_bind / Linux / Android

効かない条件: 言語

| ファイル名 (バイト) | /proc を使える | $XDG_RUNTIME_DIR | $TMPDIR | /tmp | Options.base | PrivateTmp (自分か相手が /tmp を隔離) | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | 全部 | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 1–76 | 全部 | 全部 | 全部 | 書ける (1777) | 指定しない | ○ | ○ | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 1–76 | 全部 | 全部 | 全部 | 書ける (1777) | 指定しない | × | ○ | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–72 | 全部 | 全部 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | ○ | ○ | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 1–72 | 全部 | 全部 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | × | ○ | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–73 | ○ | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | 全部 | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 1–76 | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): usable_cross_uid の指定で使わない<br>link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 1–73 | ○ | /run/user/<uid> (14、0700) | 全部 | 全部 | 指定しない | 全部 | × | ○ | link-dir (B: proc) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 1–73 | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | /var/tmp (8、1777)<br>深い所 (113、0700 の下) | 全部 | 指定しない | 全部 | × | ○ | link-dir (B: proc) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 1–73 | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書ける (1777) | 指定しない | 全部 | × | ○ | link-dir (B: proc) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 1–73 | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | ○ | link-dir (B: sockdir) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 1–72 | × | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | ○ | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 1–72 | × | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–96 | × | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107) | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 1–76 | × | 全部 | 全部 | 書ける (1777) | 指定しない | ○ | × | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 1–76 | × | 全部 | 全部 | 書ける (1777) | 指定しない | × | × | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–76 | × | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 1–71 | × | /run/user/<uid> (14、0700) | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | ○ | link-dir (B: runtime) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–71 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 1–71 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–71 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107) | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 1–71 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 1–72 | × | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 1–72 | × | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–76 | × | 無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107) | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 1–76 | × | 無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–76 | × | /run/user/<uid> (14、0700)<br>/run/user/<uid> に書けない (14。作る前の見積もりには使う) | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 71 | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 73–76 | ○ | 全部 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): usable_cross_uid の指定で使わない<br>link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 73–96 | × | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 73–76 | × | 全部 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 73–76 | × | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 74–96 | ○ | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 74–96 | ○ | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107) | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 74–76 | ○ | 全部 | 全部 | 書ける (1777) | 指定しない | ○ | × | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 74–76 | ○ | 全部 | 全部 | 書ける (1777) | 指定しない | × | × | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 74–76 | ○ | /run/user/<uid> (14、0700)<br>/run/user/<uid> に書けない (14。作る前の見積もりには使う) | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 71 | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 74–76 | ○ | 無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 74–76 | ○ | 無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107) | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 74–76 | ○ | 無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 77–96 | ○ | 全部 | 全部 | 全部 | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): usable_cross_uid の指定で使わない<br>link-dir (B の実パス): ファイル名 > 76 | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 77–96 | ○ | 全部 | 全部 | 全部 | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 76 | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 77–96 | × | 全部 | 全部 | 全部 | 指定しない | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 76 | [届く](../fork-cwd-ja.md#bind-linux-without-thread-cwd) | 見積もり |
| 97–255 | ○ | 全部 | 全部 | 全部 | 指定しない | 全部 | ○ | × | — | — | — | link-dir (procB): usable_cross_uid の指定で使わない<br>link-dir (B の実パス): ファイル名 > 76 | — | 見積もり |
| 97–255 | ○ | 全部 | 全部 | 全部 | 指定しない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 76 | — | 見積もり |
| 97–255 | ○ | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): ファイル名 > 72 | — | 見積もり |
| 97–255 | ○ | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 73<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107) | — | 見積もり |
| 97–255 | × | 全部 | 全部 | 全部 | 指定しない | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 76 | — | 見積もり |
| 97–255 | × | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): ファイル名 > 72 | — | 見積もり |
| 97–255 | × | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107) | — | 見積もり |

#### resolve_for_bind / macOS

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | Options.base | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 1–68 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103) | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–64 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–64 | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–20 | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 指定しない | × | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–64 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–64 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 21–255 | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 指定しない | × | ○ | link-file (B: tmpdir) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 65–255 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-file (B: tmp) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 65–92 | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 65–92 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 65–92 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 69–255 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-file (B: given) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 93–255 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103) | — | 見積もり |
| 93–255 | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | — | 見積もり |
| 93–255 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 64<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |

#### resolve_for_bind / iOS 等の他の Apple の OS

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | Options.base | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 1–68 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103) | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–64 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–64 | 全部 | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–20 | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 指定しない | × | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–64 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103) | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–64 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 21–64 | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 20 | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 65–92 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 64 | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 69–92 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | [届く](../fork-cwd-ja.md#bind-apple-without-thread-cwd) | 見積もり |
| 93–255 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 64 | — | 見積もり |
| 93–255 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | — | 見積もり |
| 93–255 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103) | — | 見積もり |

#### resolve_for_bind / FreeBSD

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | Options.base | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 1–68 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–68 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–72 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–92 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–72 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | — | 見積もり |
| 93–255 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | — | 見積もり |
| 93–255 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103) | — | 見積もり |

#### resolve_for_bind / NetBSD

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | Options.base | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 1–68 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–68 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–72 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–255 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-file (B: given) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 69–255 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | link-file (B: tmpdir) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 73–255 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-file (B: tmp) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 73–92 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103)<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 103) | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): 別の uid が辿れる B を作れる置き場が無い | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | — | 見積もり |
| 93–255 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |

#### resolve_for_bind / OpenBSD

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | Options.base | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 1–68 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–68 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–72 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–92 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–72 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | — | 見積もり |
| 93–255 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | — | 見積もり |
| 93–255 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103) | — | 見積もり |

#### resolve_for_bind / illumos

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | Options.base | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 1–72 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–96 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–76 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–72 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–76 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–76 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 107) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–76 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–96 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–76 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 77–96 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 76 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 97–255 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 76 | — | 見積もり |
| 97–255 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | — | 見積もり |
| 97–255 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 107) | — | 見積もり |

#### resolve_for_bind / その他の Unix

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | Options.base | Options.usable_cross_uid (別の uid の相手) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | × | — | — | — | EPERM (usable_cross_uid と Options.base で、base までの途中か base 自身が other に x を持たない) | — | 見積もり |
| 1–68 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | ○ | link-dir (B: given) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 全部 | 書ける (1777) | 指定しない | 全部 | ○ | link-dir (B: tmp) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–68 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | ○ | link-dir (B: tmpdir) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–72 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | ○ | × | — | — | — | link-dir (B の実パス): 別の uid が辿れる B を作れる置き場が無い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 140 > 103) | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 1–72 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 指定しない | × | × | — | — | — | link-dir (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–92 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 69–72 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 73–92 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | [届く](../fork-cwd-ja.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | 全部 | 全部 | 指定しない | 全部 | × | — | — | — | link-dir (B の実パス): ファイル名 > 72 | — | 見積もり |
| 93–255 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | × | × | — | — | — | link-dir (B の実パス): ファイル名 > 68 | — | 見積もり |
| 93–255 | 全部 | 全部 | 深い所 (113、0700 の下) | × | × | — | — | — | link-dir (B の実パス): B の綴りが長い (ファイル名の他で 128 > 103) | — | 見積もり |

### 既定の connect

connect・connect_nonblocking と、Options.base を指定しない connect_ex 系。D を作らず、link-file は B の直下の E を通す B/E で、connect の後すぐ E を消す。DGRAM の connect・send_to も同じ経路 (send_to が relative を使わないかは SPEC の「未確定」)

#### 既定の connect / Linux / Android

| 言語 | ファイル名 (バイト) | 元のパスと相対パスの短い方 (バイト) | スレッドの cwd を使える | /proc を使える | $XDG_RUNTIME_DIR | $TMPDIR | /tmp | ソケットのディレクトリに書ける | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 108 以上 | × | × | 全部 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| 全部 | 全部 | 108 以上 | × | × | /run/user/<uid> (14、0700) | 全部 | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: runtime) | — | — | 見積もり |
| 全部 | 全部 | 108 以上 | × | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| ts-node<br>ts-bun | 全部 | 108 以上 | ○ | × | 全部 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| ts-node<br>ts-bun | 全部 | 108 以上 | ○ | × | /run/user/<uid> (14、0700) | 全部 | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: runtime) | — | — | 見積もり |
| ts-node<br>ts-bun | 全部 | 108 以上 | ○ | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 全部 | 1–90 | 全部 | 全部 | ○ | 全部 | 全部 | 全部 | 全部 | ○ | proc-direct | — | — | 実測: linux-long-connect |
| 全部 | 1–107 | 1–107 | 全部 | × | 全部 | 全部 | 全部 | 全部 | ○ | relative | — | — | 実測: no-proc-connect-near-cwd (rs・py・go・ts-node) |
| rs<br>py<br>go | 1–107 | 108 以上 | ○ | × | 全部 | 全部 | 全部 | 全部 | ○ | thread-cwd-direct | — | — | 見積もり |
| rs<br>py<br>go | 1–107 | 108 以上 | × | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 107<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 107) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–107 | 108 以上 | × | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 107<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py<br>go | 1–107 | 108 以上 | × | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 107<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–107 | 108 以上 | 全部 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 107<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 107) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–107 | 108 以上 | 全部 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 107<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–107 | 108 以上 | 全部 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 107<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| 全部 | 91–107 | 全部 | × | ○ | 全部 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| 全部 | 91–107 | 全部 | × | ○ | /run/user/<uid> (14、0700) | 全部 | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: runtime) | — | — | 見積もり |
| 全部 | 91–107 | 全部 | × | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| rs<br>py<br>go | 91–107 | 全部 | ○ | ○ | 全部 | 全部 | 全部 | 全部 | ○ | thread-cwd-direct | — | — | 見積もり |
| rs<br>py<br>go | 91–107 | 全部 | × | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 107) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py<br>go | 91–107 | 全部 | × | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py<br>go | 91–107 | 全部 | × | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 91–107 | 全部 | 全部 | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 107) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 91–107 | 全部 | 全部 | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 91–107 | 全部 | 全部 | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 91–107 | 全部 | ○ | ○ | 全部 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| ts-node<br>ts-bun | 91–107 | 全部 | ○ | ○ | /run/user/<uid> (14、0700) | 全部 | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: runtime) | — | — | 見積もり |
| ts-node<br>ts-bun | 91–107 | 全部 | ○ | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 全部 | 108–255 | 108 以上 | 全部 | ○ | 全部 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| 全部 | 108–255 | 108 以上 | 全部 | ○ | /run/user/<uid> (14、0700) | 全部 | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: runtime) | — | — | 見積もり |
| 全部 | 108–255 | 108 以上 | 全部 | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | ○ | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: ファイル名 > 107<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 107) | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | ○ | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: ファイル名 > 107<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | ○ | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: ファイル名 > 107<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | ○ | × | 全部 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | ○ | × | /run/user/<uid> (14、0700) | 全部 | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: runtime) | — | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | ○ | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | ○ | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 107<br>thread-cwd-direct: ファイル名 > 107<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 107) | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | ○ | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 107<br>thread-cwd-direct: ファイル名 > 107<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | ○ | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 107<br>thread-cwd-direct: ファイル名 > 107<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | × | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 107) | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | × | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | × | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | × | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 107<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 107) | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | × | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 107<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| rs<br>py<br>go | 108–255 | 108 以上 | × | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 107<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| ts-node<br>ts-bun | 108–255 | 108 以上 | 全部 | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 107) | — | 見積もり |
| ts-node<br>ts-bun | 108–255 | 108 以上 | 全部 | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| ts-node<br>ts-bun | 108–255 | 108 以上 | 全部 | ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| ts-node<br>ts-bun | 108–255 | 108 以上 | 全部 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 107<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 107) | — | 見積もり |
| ts-node<br>ts-bun | 108–255 | 108 以上 | 全部 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 107<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| ts-node<br>ts-bun | 108–255 | 108 以上 | 全部 | × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 107<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

#### 既定の connect / macOS

| 言語 | ファイル名 (バイト) | 元のパスと相対パスの短い方 (バイト) | スレッドの cwd を使える | $TMPDIR | /tmp | ソケットのディレクトリに書ける | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 1–103 | 1–103 | 全部 | 全部 | 全部 | 全部 | ○ | relative | — | — | 実測: long-connect |
| 全部 | 1–103 | 254 以上 | × | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| 全部 | 1–103 | 254 以上 | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| rs<br>py | 1–253 | 104–253 | 全部 | 全部 | 全部 | 全部 | ○ | widened | — | — | 実測: long-filename-connect |
| rs<br>py<br>go | 1–103 | 254 以上 | ○ | 全部 | 全部 | 全部 | ○ | thread-cwd-direct | — | — | 見積もり |
| rs<br>py | 1–253 | 254 以上 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 1–253 | 254 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 1–253 | 254 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 1–103 | 104–253 | ○ | 全部 | 全部 | 全部 | ○ | thread-cwd-direct | — | — | 見積もり |
| go<br>ts-node<br>ts-bun | 1–103 | 104–253 | × | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| go<br>ts-node<br>ts-bun | 1–103 | 104–253 | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| go | 1–253 | 104 以上 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 1–253 | 104 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 1–253 | 104 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–253 | 104 以上 | 全部 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–253 | 104 以上 | 全部 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–253 | 104 以上 | 全部 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–103 | 104 以上 | ○ | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| ts-node<br>ts-bun | 1–103 | 104 以上 | ○ | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 全部 | 104–255 | 254 以上 | 全部 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| 全部 | 104–255 | 254 以上 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| rs<br>py | 104–253 | 254 以上 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 104–253 | 254 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 104–253 | 254 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| go<br>ts-node<br>ts-bun | 104–253 | 104–253 | 全部 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| go<br>ts-node<br>ts-bun | 104–253 | 104–253 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| go | 104–253 | 104 以上 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 104–253 | 104 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 104–253 | 104 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 254–255 | 254 以上 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| go | 254–255 | 254 以上 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| go | 254–255 | 254 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| go | 254–255 | 254 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| go | 254–255 | 254 以上 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| go | 254–255 | 254 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| go | 254–255 | 254 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| ts-node<br>ts-bun | 254–255 | 254 以上 | 全部 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| ts-node<br>ts-bun | 254–255 | 254 以上 | 全部 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| ts-node<br>ts-bun | 254–255 | 254 以上 | 全部 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

#### 既定の connect / iOS 等の他の Apple の OS

| 言語 | ファイル名 (バイト) | 元のパスと相対パスの短い方 (バイト) | スレッドの cwd を使える | $TMPDIR | /tmp | ソケットのディレクトリに書ける | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 1–103 | 1–103 | 全部 | 全部 | 全部 | 全部 | ○ | relative | — | — | 見積もり |
| 全部 | 1–103 | 254 以上 | × | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| 全部 | 1–103 | 254 以上 | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| rs<br>py | 1–253 | 104–253 | 全部 | 全部 | 全部 | 全部 | ○ | widened | — | — | 見積もり |
| rs<br>py<br>go | 1–103 | 254 以上 | ○ | 全部 | 全部 | 全部 | ○ | thread-cwd-direct | — | — | 見積もり |
| rs<br>py | 1–253 | 254 以上 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 1–253 | 254 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 1–253 | 254 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 1–103 | 104–253 | ○ | 全部 | 全部 | 全部 | ○ | thread-cwd-direct | — | — | 見積もり |
| go<br>ts-node<br>ts-bun | 1–103 | 104–253 | × | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| go<br>ts-node<br>ts-bun | 1–103 | 104–253 | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| go | 1–253 | 104 以上 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 1–253 | 104 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 1–253 | 104 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–253 | 104 以上 | 全部 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–253 | 104 以上 | 全部 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–253 | 104 以上 | 全部 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–103 | 104 以上 | ○ | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| ts-node<br>ts-bun | 1–103 | 104 以上 | ○ | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 全部 | 104–255 | 254 以上 | 全部 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| 全部 | 104–255 | 254 以上 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| rs<br>py | 104–253 | 254 以上 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 104–253 | 254 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 104–253 | 254 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| go<br>ts-node<br>ts-bun | 104–253 | 104–253 | 全部 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| go<br>ts-node<br>ts-bun | 104–253 | 104–253 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| go | 104–253 | 104 以上 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 104–253 | 104 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 104–253 | 104 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 254–255 | 254 以上 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| go | 254–255 | 254 以上 | ○ | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| go | 254–255 | 254 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| go | 254–255 | 254 以上 | ○ | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| go | 254–255 | 254 以上 | × | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| go | 254–255 | 254 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| go | 254–255 | 254 以上 | × | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| ts-node<br>ts-bun | 254–255 | 254 以上 | 全部 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| ts-node<br>ts-bun | 254–255 | 254 以上 | 全部 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| ts-node<br>ts-bun | 254–255 | 254 以上 | 全部 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: この言語に無い<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

#### 既定の connect / FreeBSD

| 言語 | ファイル名 (バイト) | $TMPDIR | /tmp | ソケットのディレクトリに書ける | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|
| rs<br>py<br>go | 1–103 | 全部 | 全部 | 全部 | ○ | at-direct | — | — | 見積もり |
| ts-node<br>ts-bun | 1–103 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| ts-node<br>ts-bun | 1–103 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| ts-node<br>ts-bun | 1–103 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | at-direct: この言語に無い<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–103 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | at-direct: この言語に無い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| ts-node<br>ts-bun | 1–103 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | at-direct: この言語に無い<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| 全部 | 104–255 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| 全部 | 104–255 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| rs<br>py<br>go | 104–255 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | at-direct: ファイル名 > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| rs<br>py<br>go | 104–255 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | at-direct: ファイル名 > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| rs<br>py<br>go | 104–255 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | at-direct: ファイル名 > 103<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| ts-node<br>ts-bun | 104–255 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | at-direct: この言語に無い<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| ts-node<br>ts-bun | 104–255 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | at-direct: この言語に無い<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| ts-node<br>ts-bun | 104–255 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | at-direct: この言語に無い<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

#### 既定の connect / NetBSD

効かない条件: 言語

| ファイル名 (バイト) | 元のパスと相対パスの短い方 (バイト) | $TMPDIR | /tmp | ソケットのディレクトリに書ける | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|
| 全部 | 104 以上 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| 全部 | 104 以上 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 1–103 | 1–103 | 全部 | 全部 | 全部 | ○ | relative | — | — | 見積もり |
| 1–103 | 104 以上 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| 1–103 | 104 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| 1–103 | 104 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| 104–255 | 104 以上 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| 104–255 | 104 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| 104–255 | 104 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

#### 既定の connect / OpenBSD

効かない条件: 言語

| ファイル名 (バイト) | 元のパスと相対パスの短い方 (バイト) | $TMPDIR | /tmp | ソケットのディレクトリに書ける | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|
| 全部 | 104 以上 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| 全部 | 104 以上 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 1–103 | 1–103 | 全部 | 全部 | 全部 | ○ | relative | — | — | 見積もり |
| 1–103 | 104 以上 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| 1–103 | 104 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| 1–103 | 104 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| 104–255 | 104 以上 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| 104–255 | 104 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| 104–255 | 104 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

#### 既定の connect / illumos

効かない条件: 言語

| ファイル名 (バイト) | 元のパスと相対パスの短い方 (バイト) | $TMPDIR | /tmp | ソケットのディレクトリに書ける | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|
| 全部 | 108 以上 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| 全部 | 108 以上 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 1–107 | 1–107 | 全部 | 全部 | 全部 | ○ | relative | — | — | 見積もり |
| 1–107 | 108 以上 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 107<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 107) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| 1–107 | 108 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 107<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| 1–107 | 108 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 107<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| 108–255 | 108 以上 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 107<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 107) | — | 見積もり |
| 108–255 | 108 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 107<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| 108–255 | 108 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 107<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

#### 既定の connect / その他の Unix

効かない条件: 言語

| ファイル名 (バイト) | 元のパスと相対パスの短い方 (バイト) | $TMPDIR | /tmp | ソケットのディレクトリに書ける | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|
| 全部 | 104 以上 | 全部 | 書ける (1777) | 全部 | ○ | link-file (B: tmp) | — | — | 見積もり |
| 全部 | 104 以上 | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 1–103 | 1–103 | 全部 | 全部 | 全部 | ○ | relative | — | — | 見積もり |
| 1–103 | 104 以上 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| 1–103 | 104 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| 1–103 | 104 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B を作れる置き場が無い | [届く](../fork-cwd-ja.md#connect-without-place-or-thread-cwd) | 見積もり |
| 104–255 | 104 以上 | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B の綴りが長い (綴り 136 > 103) | — | 見積もり |
| 104–255 | 104 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| 104–255 | 104 以上 | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | × | — | relative: 相対パス > 103<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

### resolve_for_connect

綴り B/D/E (link-file) を返す。cleanup まで残し、同じパスへの connect に何度も使う

#### resolve_for_connect / Linux / Android

効かない条件: 言語、ファイル名 (バイト)

| /proc を使える | $XDG_RUNTIME_DIR | $TMPDIR | /tmp | ソケットのディレクトリに書ける | Options.base | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| ○ | 全部 | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下)<br>深い所 (113、0700 の下) | ○ | link-file (B: given) | — | — | 見積もり |
| ○ | 全部 | 全部 | 書ける (1777) | 全部 | 指定しない | ○ | link-file (B: proc) | — | — | 見積もり |
| ○ | 全部 | /var/tmp (8、1777)<br>深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | ○ | link-file (B: proc) | — | — | 見積もり |
| ○ | /run/user/<uid> (14、0700) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | ○ | link-file (B: proc) | — | — | 見積もり |
| ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | 指定しない | ○ | link-file (B: sockdir) | — | — | 見積もり |
| ○ | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | 指定しない | × | — | link-file (procB): B を作れる置き場が無い<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |
| × | 全部 | 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | ○ | link-file (B: given) | — | — | 見積もり |
| × | 全部 | 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | × | — | link-file (procB): /proc を使えない<br>link-file (B の実パス): B の綴りが長い (綴り 127 > 107) | — | 見積もり |
| × | 全部 | 全部 | 書ける (1777) | 全部 | 指定しない | ○ | link-file (B: tmp) | — | — | 見積もり |
| × | /run/user/<uid> (14、0700) | 全部 | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | ○ | link-file (B: runtime) | — | — | 見積もり |
| × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | × | — | link-file (procB): /proc を使えない<br>link-file (B の実パス): B の綴りが長い (綴り 139 > 107) | — | 見積もり |
| × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | 指定しない | × | — | link-file (procB): /proc を使えない<br>link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| × | /run/user/<uid> に書けない (14。作る前の見積もりには使う)<br>無い (空・相対パスを含む) | 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | 指定しない | × | — | link-file (procB): /proc を使えない<br>link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

#### resolve_for_connect / macOS

効かない条件: 言語、ファイル名 (バイト)

| $TMPDIR | /tmp | ソケットのディレクトリに書ける | Options.base | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | ○ | link-file (B: given) | — | — | 見積もり |
| 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | × | — | link-file (B の実パス): B の綴りが長い (綴り 127 > 103) | — | 見積もり |
| 全部 | 書ける (1777) | 全部 | 指定しない | ○ | link-file (B: tmp) | — | — | 見積もり |
| 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | × | — | link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | — | 見積もり |
| 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | 指定しない | × | — | link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | 指定しない | × | — | link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

#### resolve_for_connect / iOS 等の他の Apple の OS

効かない条件: 言語、ファイル名 (バイト)

| $TMPDIR | /tmp | ソケットのディレクトリに書ける | Options.base | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | ○ | link-file (B: given) | — | — | 見積もり |
| 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | × | — | link-file (B の実パス): B の綴りが長い (綴り 127 > 103) | — | 見積もり |
| 全部 | 書ける (1777) | 全部 | 指定しない | ○ | link-file (B: tmp) | — | — | 見積もり |
| 既定 (/private/var/folders/…/T、56、0700) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | × | — | link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | — | 見積もり |
| 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | 指定しない | × | — | link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | 指定しない | × | — | link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

#### resolve_for_connect / FreeBSD

効かない条件: 言語、ファイル名 (バイト)

| $TMPDIR | /tmp | ソケットのディレクトリに書ける | Options.base | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | ○ | link-file (B: given) | — | — | 見積もり |
| 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | × | — | link-file (B の実パス): B の綴りが長い (綴り 127 > 103) | — | 見積もり |
| 全部 | 書ける (1777) | 全部 | 指定しない | ○ | link-file (B: tmp) | — | — | 見積もり |
| /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | × | — | link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | — | 見積もり |
| 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | 指定しない | × | — | link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | 指定しない | × | — | link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

#### resolve_for_connect / NetBSD

効かない条件: 言語、ファイル名 (バイト)

| $TMPDIR | /tmp | ソケットのディレクトリに書ける | Options.base | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | ○ | link-file (B: given) | — | — | 見積もり |
| 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | × | — | link-file (B の実パス): B の綴りが長い (綴り 127 > 103) | — | 見積もり |
| 全部 | 書ける (1777) | 全部 | 指定しない | ○ | link-file (B: tmp) | — | — | 見積もり |
| /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | × | — | link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | — | 見積もり |
| 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | 指定しない | × | — | link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | 指定しない | × | — | link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

#### resolve_for_connect / OpenBSD

効かない条件: 言語、ファイル名 (バイト)

| $TMPDIR | /tmp | ソケットのディレクトリに書ける | Options.base | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | ○ | link-file (B: given) | — | — | 見積もり |
| 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | × | — | link-file (B の実パス): B の綴りが長い (綴り 127 > 103) | — | 見積もり |
| 全部 | 書ける (1777) | 全部 | 指定しない | ○ | link-file (B: tmp) | — | — | 見積もり |
| /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | × | — | link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | — | 見積もり |
| 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | 指定しない | × | — | link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | 指定しない | × | — | link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

#### resolve_for_connect / illumos

効かない条件: 言語、ファイル名 (バイト)

| $TMPDIR | /tmp | ソケットのディレクトリに書ける | Options.base | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | ○ | link-file (B: given) | — | — | 見積もり |
| 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | × | — | link-file (B の実パス): B の綴りが長い (綴り 127 > 107) | — | 見積もり |
| 全部 | 書ける (1777) | 全部 | 指定しない | ○ | link-file (B: tmp) | — | — | 見積もり |
| /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | × | — | link-file (B の実パス): B の綴りが長い (綴り 139 > 107) | — | 見積もり |
| 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | 指定しない | × | — | link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | 指定しない | × | — | link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

#### resolve_for_connect / その他の Unix

効かない条件: 言語、ファイル名 (バイト)

| $TMPDIR | /tmp | ソケットのディレクトリに書ける | Options.base | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | /tmp/app-<uid>/sockat (20、0700 の下) | ○ | link-file (B: given) | — | — | 見積もり |
| 全部 | 全部 | 全部 | 深い所 (113、0700 の下) | × | — | link-file (B の実パス): B の綴りが長い (綴り 127 > 103) | — | 見積もり |
| 全部 | 書ける (1777) | 全部 | 指定しない | ○ | link-file (B: tmp) | — | — | 見積もり |
| /var/tmp (8、1777) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | ○ | link-file (B: tmpdir) | — | — | 見積もり |
| 深い所 (113、0700 の下) | 書けない (作る前の見積もりには使う) | 全部 | 指定しない | × | — | link-file (B の実パス): B の綴りが長い (綴り 139 > 103) | — | 見積もり |
| 未設定・書けない | 書けない (作る前の見積もりには使う) | 書ける | 指定しない | × | — | link-file (B の実パス): B がソケットのディレクトリにあり、実パスの綴りは元のパスより長い | — | 見積もり |
| 未設定・書けない | 書けない (作る前の見積もりには使う) | 書けない | 指定しない | × | — | link-file (B の実パス): B を作れる置き場が無い | — | 見積もり |

