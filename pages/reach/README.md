# 届く範囲 (作り直しの案)

sockat で長いパスに届くか、どの経路で届くか、届かなければなぜかを、条件の組み合わせごとに並べた表。[resolve と置き場 B で経路を組み直す案](../../docs/issue/2026-11-20-resolve-and-persistent-base.md) (fork なし、最終手段なし) に対して作る。未実装の設計なので、数字は綴りの長さからの見積もり。

- 選んで絞り込むページ: [index.html](index.html) (JS の無い環境ではこの README を読む)
- 正本: [model.json](model.json)。このファイルと `data/` は [gen.py](gen.py) が生成する (`just reach`)。手で直さない。ずれは `just reach-check` が拾う
- fork-cwd の手法と、それなら届く場面: [fork-cwd.md](../fork-cwd.md)

## 畳み方

- 表は操作ごと、OS ごとに分ける。行は条件の組み合わせ、列は条件と結果
- 全部の組み合わせを計算し、結果 (届くか・経路・綴り・理由・根拠) が同じで 1 つの条件の値だけが違う行を 1 行にまとめる。まとまらなくなるまで繰り返す
- ファイル名と、元のパスと相対パスの短い方の長さは、どれかの経路の綴りが収まるか収まらないかが変わる境目で帯に分ける。帯の中では結果が変わらない (gen.py が帯の両端で確かめる)
- 表の中のどの行でも「全部」になる条件は列に出さず、表の上に「効かない条件」として書く
- 置き場の長さは代表値で計算する (「条件」の置き場の表)。パス全体の長さは、ディレクトリが標準に渡す長さを超えるほど深い前提で、PATH_MAX まで効かない
- 言語は、作れない経路 (lacks) で結果が変わる所だけ分かれる

## 見積もりと実測

- 根拠の列が「見積もり」のセルは、model.json の綴りの式と代表値から計算しただけ
- 「実測」のセルは、今の実装を適合試験 ([conformance/cases.json](../../conformance/cases.json)) に流した結果が、計算と同じ経路・同じ結果だった場面の名前。当てるのは作り直しで変わらない経路 (at・at-direct・proc・proc-direct・relative・symlink-file・thread-cwd・widened) と、fork を持たない言語 (py・go) の既定の bind の届かない行だけ。条件が全部分かる場面だけを当てる
- 入力のうち実測したもの: bind が symlink を辿る OS ([findings](../../docs/findings/2026-11-19-bind-through-file-symlink.md))、0700 の親の下の 0711 は別の uid が辿れないこと (issue の「実測」)、docker の seccomp で `unshare` が断られること ([conformance.md](../../docs/design/conformance.md))

見積もりの前提:

| 値 | バイト | 中身 |
|---|---|---|
| `rand` | 10 | D・R の乱数の名前 (英数 10 文字) |
| `B` | 17 | B の名前の長さ。名前は未決 (issue の「案がまだ無い」)。今の名前 sockat.XXXXXXXXXX と同じ 17 バイトで見積もる |
| `pid` | 7 | procB の <pid> の桁。Linux の pid_max 4194304 で 7 桁 (小さい pid ではその分届くファイル名が延びる) |
| `fd` | 2 | fd の番号の桁。SPEC の proc の「およそ 79」と同じ 2 桁 |
| `name_max` | 255 | ファイル名の上限 (NAME_MAX)。表のファイル名の帯はここまで |
| `widened` | 253 | Apple の OS の広げた sockaddr に入るパスの長さ (SPEC の widened) |

## 条件

| 条件 | 効く操作 | 中身 |
|---|---|---|
| OS | 全部 |  |
| 言語 | 全部 |  |
| ファイル名 (バイト) | 全部 | 境目は各経路の綴りの長さの式から計算する |
| 元のパスと相対パスの短い方 (バイト) | connect | relative・widened の綴り。相対パスは cwd から作る (SPEC の「相対パスの作り方」) |
| スレッドの cwd を使える | 全部 | Linux は seccomp の filter が掛かっていない・unshare が通る、Apple の OS は pthread_fchdir_np がある |
| /proc を使える | 全部 |  |
| bind が symlink を辿る | 既定の bind<br>bind_ex<br>resolve_for_bind | 辿るかを実測していない OS だけの条件。実測した OS は OS で決まる |
| $XDG_RUNTIME_DIR | bind_ex<br>resolve_for_bind<br>connect |  |
| $TMPDIR | 既定の bind<br>bind_ex<br>resolve_for_bind<br>connect |  |
| /tmp | 既定の bind<br>bind_ex<br>resolve_for_bind<br>connect |  |
| ソケットのディレクトリに書ける | connect | bind はソケットのファイルを作るので書ける前提 |
| PrivateTmp (自分か相手が /tmp を隔離) | bind_ex<br>resolve_for_bind | systemd の PrivateTmp 等。綴りを相手が辿れるかにだけ効く |
| 別の uid の相手と通信する | bind_ex<br>resolve_for_bind | Options.usable_cross_uid を指定する前提。B の選び方と、綴りを相手が辿れるかに効く |

置き場 (代表値。長さは実パスのバイト数、symlink-file は `$TMPDIR`・`/tmp` をそのままの綴りで使う):

| 置き場 | OS | 値 | 長さ | 別の uid が辿れる | /tmp・/var/tmp の下 |
|---|---|---|---|---|---|
| $XDG_RUNTIME_DIR | Linux / Android | /run/user/<uid> (14、0700) | 14 | × | × |
| $TMPDIR | Linux / Android<br>FreeBSD<br>NetBSD<br>OpenBSD<br>illumos<br>その他の Unix | /var/tmp (8、1777) | 8 | ○ | ○ |
| $TMPDIR | Linux / Android<br>FreeBSD<br>NetBSD<br>OpenBSD<br>illumos<br>その他の Unix | 深い所 (113、0700 の下) | 113 | × | × |
| $TMPDIR | macOS<br>iOS 等の他の Apple の OS | 既定 (/private/var/folders/…/T、56、0700) | 56 | × | × |
| $TMPDIR | macOS<br>iOS 等の他の Apple の OS | 深い所 (113、0700 の下) | 113 | × | × |
| /tmp | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS<br>FreeBSD<br>NetBSD<br>OpenBSD<br>illumos<br>その他の Unix | 書ける (1777) | 4、12 | ○ | ○ |
| ソケットのディレクトリ | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS<br>FreeBSD<br>NetBSD<br>OpenBSD<br>illumos<br>その他の Unix | 書ける | — | — | — |

## 経路

| 操作 | 順 | 経路 | 綴り | 届くファイル名 | OS | 要る物 | 綴りの性質 (bind) |
|---|---|---|---|---|---|---|---|
| 既定の bind | 1 | symlink-file | `<place>/sockat.<rand>` | よらない (置き場 ≤ sockaddr − 18) | 全部 | bind が symlink を辿る (connect はいつも辿る)<br>置き場: $TMPDIR → /tmp の綴りが収まる最初の物 | Dangling |
| 既定の bind | 2 | thread-cwd | `<rand>/<F>` | sockaddr − 11 | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS | スレッドの cwd<br>置き場: $TMPDIR → /tmp → ソケットのディレクトリ の書ける最初の物 | Dangling |
| 既定の bind | 3 | at | `<rand>/<F>` | sockaddr − 11 | FreeBSD | 置き場: $TMPDIR → /tmp → ソケットのディレクトリ の書ける最初の物 | Dangling |
| 既定の bind | 4 | proc | `/proc/self/fd/<fd>/<rand>/<F>` | sockaddr − 28 | Linux / Android | /proc<br>置き場: $TMPDIR → /tmp → ソケットのディレクトリ の書ける最初の物 | Dangling |
| bind_ex | 1 | link-dir (procB) | `/proc/<pid>/fd/<fd>/<rand>/d/<F>` | sockaddr − 33 | Linux / Android | /proc<br>置き場: $XDG_RUNTIME_DIR → $TMPDIR → /tmp → ソケットのディレクトリ の書ける最初の物<br>別の uid の指定で飛ばす | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true |
| bind_ex | 2 | link-dir (dirB) | `<place>/<B>/<rand>/d/<F>` | sockaddr − 32 − 置き場 | 全部 | 置き場: $XDG_RUNTIME_DIR → $TMPDIR の書ける物のうち実パスの短い方<br>別の uid の指定では、途中が other に x の置き場だけ | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: 置き場までの途中が other に x なら true<br>usable_with_private_tmp: 置き場が /tmp・/var/tmp の下でなければ true |
| bind_ex | 3 | link-file (dirB) | `<place>/<B>/<rand>/s` | よらない (置き場 ≤ sockaddr − 31) | 全部 | bind が symlink を辿る (connect はいつも辿る)<br>置き場: $XDG_RUNTIME_DIR → $TMPDIR の書ける物のうち実パスの短い方<br>別の uid の指定では、途中が other に x の置き場だけ | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: 置き場までの途中が other に x なら true<br>usable_with_private_tmp: 置き場が /tmp・/var/tmp の下でなければ true |
| bind_ex | 4 | link-dir (tmpB) | `<place>/<B>/<rand>/d/<F>` | sockaddr − 32 − 置き場 | 全部 | 置き場: /tmp の書ける最初の物 | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false |
| bind_ex | 5 | link-file (tmpB) | `<place>/<B>/<rand>/s` | よらない (置き場 ≤ sockaddr − 31) | 全部 | bind が symlink を辿る (connect はいつも辿る)<br>置き場: /tmp の書ける最初の物 | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false |
| bind_ex | 6 | thread-cwd | `<rand>/<F>` | sockaddr − 11 | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS | スレッドの cwd<br>置き場: $TMPDIR → /tmp → ソケットのディレクトリ の書ける最初の物 | Dangling |
| bind_ex | 7 | at | `<rand>/<F>` | sockaddr − 11 | FreeBSD | 置き場: $TMPDIR → /tmp → ソケットのディレクトリ の書ける最初の物 | Dangling |
| resolve_for_bind | 1 | link-dir (procB) | `/proc/<pid>/fd/<fd>/<rand>/d/<F>` | sockaddr − 33 | Linux / Android | /proc<br>置き場: $XDG_RUNTIME_DIR → $TMPDIR → /tmp → ソケットのディレクトリ の書ける最初の物<br>別の uid の指定で飛ばす | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true |
| resolve_for_bind | 2 | link-dir (dirB) | `<place>/<B>/<rand>/d/<F>` | sockaddr − 32 − 置き場 | 全部 | 置き場: $XDG_RUNTIME_DIR → $TMPDIR の書ける物のうち実パスの短い方<br>別の uid の指定では、途中が other に x の置き場だけ | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: 置き場までの途中が other に x なら true<br>usable_with_private_tmp: 置き場が /tmp・/var/tmp の下でなければ true |
| resolve_for_bind | 3 | link-file (dirB) | `<place>/<B>/<rand>/s` | よらない (置き場 ≤ sockaddr − 31) | 全部 | bind が symlink を辿る (connect はいつも辿る)<br>置き場: $XDG_RUNTIME_DIR → $TMPDIR の書ける物のうち実パスの短い方<br>別の uid の指定では、途中が other に x の置き場だけ | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: 置き場までの途中が other に x なら true<br>usable_with_private_tmp: 置き場が /tmp・/var/tmp の下でなければ true |
| resolve_for_bind | 4 | link-dir (tmpB) | `<place>/<B>/<rand>/d/<F>` | sockaddr − 32 − 置き場 | 全部 | 置き場: /tmp の書ける最初の物 | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false |
| resolve_for_bind | 5 | link-file (tmpB) | `<place>/<B>/<rand>/s` | よらない (置き場 ≤ sockaddr − 31) | 全部 | bind が symlink を辿る (connect はいつも辿る)<br>置き場: /tmp の書ける最初の物 | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false |
| connect | 1 | proc-direct | `/proc/self/fd/<fd>/<F>` | sockaddr − 17 | Linux / Android | /proc |  |
| connect | 2 | relative | `<rel>` | よらない (相対パス ≤ sockaddr) | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS<br>NetBSD<br>OpenBSD<br>illumos<br>その他の Unix | /proc を使えない時だけ |  |
| connect | 3 | widened | `<rel>` | よらない (相対パス ≤ 253) | macOS<br>iOS 等の他の Apple の OS | — |  |
| connect | 4 | at-direct | `<F>` | sockaddr | FreeBSD | — |  |
| connect | 5 | thread-cwd-direct | `<F>` | sockaddr | Linux / Android<br>macOS<br>iOS 等の他の Apple の OS | スレッドの cwd |  |
| connect | 6 | link-file (procB) | `/proc/<pid>/fd/<fd>/<rand>/s` | よらない | Linux / Android | /proc<br>置き場: $XDG_RUNTIME_DIR → $TMPDIR → /tmp → ソケットのディレクトリ の書ける最初の物 |  |
| connect | 7 | link-file (dirB) | `<place>/<B>/<rand>/s` | よらない (置き場 ≤ sockaddr − 31) | 全部 | 置き場: $XDG_RUNTIME_DIR → $TMPDIR の書ける物のうち実パスの短い方 |  |
| connect | 8 | link-file (tmpB) | `<place>/<B>/<rand>/s` | よらない (置き場 ≤ sockaddr − 31) | 全部 | 置き場: /tmp の書ける最初の物 |  |

綴りの記号: `<F>` はファイル名、`<rel>` は元のパスと相対パスの短い方、`<place>` は置き場の実パス (symlink-file はそのままの綴り)、それ以外は「見積もりの前提」の値。sockaddr は sockaddr に入る長さ (Linux / illumos 107、他 103)

## まとめ: ファイル名の長さごとに届くか

表の全部の条件の組み合わせを、ファイル名の帯ごとにまとめた物。「条件しだい」はスレッドの cwd・`/proc`・置き場・別の uid・相対パスの長さ等で届いたり届かなかったりする帯。「普段の環境で届く」の条件: まとめの表の「普段の環境」。スレッドの cwd と /proc を使え、置き場は OS の既定のまま書け、別の uid とも PrivateTmp とも関わらない。相対パスの長さと、bind が symlink を辿るかを実測していない OS の辿るかは、どの値でも届く時だけ届くとする

| 操作 | OS | 言語 | 普段の環境で届く | どの条件でも届く | 条件しだい | どの条件でも届かない |
|---|---|---|---|---|---|---|
| 既定の bind | Linux / Android | 全部 | 1–96 | — | 1–96 | 97–255 |
| 既定の bind | macOS | 全部 | 1–255 | — | 1–255 | — |
| 既定の bind | iOS 等の他の Apple の OS | 全部 | 1–92 | — | 1–255 | — |
| 既定の bind | FreeBSD | 全部 | 1–92 | 1–92 | — | 93–255 |
| 既定の bind | NetBSD | 全部 | 1–255 | — | 1–255 | — |
| 既定の bind | OpenBSD | 全部 | — | — | — | 1–255 |
| 既定の bind | illumos | 全部 | — | — | — | 1–255 |
| 既定の bind | その他の Unix | 全部 | — | — | 1–255 | — |
| bind_ex | Linux / Android | 全部 | 1–96 | — | 1–96 | 97–255 |
| bind_ex | macOS | 全部 | 1–255 | — | 1–255 | — |
| bind_ex | iOS 等の他の Apple の OS | 全部 | 1–92 | — | 1–255 | — |
| bind_ex | FreeBSD | 全部 | 1–92 | 1–92 | — | 93–255 |
| bind_ex | NetBSD | 全部 | 1–255 | — | 1–255 | — |
| bind_ex | OpenBSD | 全部 | 1–67 | — | 1–67 | 68–255 |
| bind_ex | illumos | 全部 | 1–71 | — | 1–71 | 72–255 |
| bind_ex | その他の Unix | 全部 | 1–67 | — | 1–255 | — |
| resolve_for_bind | Linux / Android | 全部 | 1–74 | — | 1–74 | 75–255 |
| resolve_for_bind | macOS | 全部 | 1–255 | — | 1–255 | — |
| resolve_for_bind | iOS 等の他の Apple の OS | 全部 | 1–59 | — | 1–255 | — |
| resolve_for_bind | FreeBSD | 全部 | 1–67 | — | 1–67 | 68–255 |
| resolve_for_bind | NetBSD | 全部 | 1–255 | — | 1–255 | — |
| resolve_for_bind | OpenBSD | 全部 | 1–67 | — | 1–67 | 68–255 |
| resolve_for_bind | illumos | 全部 | 1–71 | — | 1–71 | 72–255 |
| resolve_for_bind | その他の Unix | 全部 | 1–67 | — | 1–255 | — |
| connect | Linux / Android | 全部 | 1–255 | — | 1–255 | — |
| connect | macOS | 全部 | 1–255 | — | 1–255 | — |
| connect | iOS 等の他の Apple の OS | 全部 | 1–255 | — | 1–255 | — |
| connect | FreeBSD | 全部 | 1–255 | 1–103 | 104–255 | — |
| connect | NetBSD | 全部 | 1–255 | — | 1–255 | — |
| connect | OpenBSD | 全部 | 1–255 | — | 1–255 | — |
| connect | illumos | 全部 | 1–255 | — | 1–255 | — |
| connect | その他の Unix | 全部 | 1–255 | — | 1–255 | — |

## 表

### 既定の bind

RS-Q4 の推し b: 呼び出しごとの一時ディレクトリ D を作って消す今の形から fork を除いた物。B は作らない。綴りは Dangling

#### 既定の bind / Linux / Android

効かない条件: 言語、$TMPDIR、/tmp

| ファイル名 (バイト) | スレッドの cwd を使える | /proc を使える | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|
| 1–96 | ○ | 全部 | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 実測: linux-long-bind、no-proc-bind、no-tmpdir-bind、no-tmpdir-no-tmp-bind |
| 1–79 | × | ○ | ○ | proc | Dangling | 辿れない (片付け済み) | — | — | 実測: no-thread-cwd-bind、no-thread-cwd-bind-kill-unshare |
| 1–96 | × | × | × | — | — | — | thread-cwd: スレッドの cwd を使えない<br>proc: /proc を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 実測: no-thread-cwd-no-proc-bind (py・go)、no-tmp-no-thread-cwd-no-proc-bind (py・go) |
| 80–96 | × | ○ | × | — | — | — | thread-cwd: スレッドの cwd を使えない<br>proc: ファイル名 > 79 | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 97–255 | ○ | ○ | × | — | — | — | thread-cwd: ファイル名 > 96<br>proc: ファイル名 > 79 | — | 見積もり |
| 97–255 | ○ | × | × | — | — | — | thread-cwd: ファイル名 > 96<br>proc: /proc を使えない | — | 実測: no-proc-long-filename-bind |
| 97–255 | × | ○ | × | — | — | — | thread-cwd: スレッドの cwd を使えない<br>proc: ファイル名 > 79 | — | 見積もり |
| 97–255 | × | × | × | — | — | — | thread-cwd: スレッドの cwd を使えない<br>proc: /proc を使えない | — | 見積もり |

#### 既定の bind / macOS

効かない条件: 言語

| ファイル名 (バイト) | スレッドの cwd を使える | $TMPDIR | /tmp | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 全部 | 書ける (1777) | ○ | symlink-file | Dangling | 辿れない (片付け済み) | — | — | 実測: long-absolute-bind、long-filename-bind |
| 全部 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 書けない | ○ | symlink-file | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 1–92 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 1–92 | × | 深い所 (113、0700 の下) | 書けない | × | — | — | — | symlink-file: 置き場が長い (綴り 131 > 103)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | × | 未設定・書けない | 書けない | × | — | — | — | symlink-file: 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 93–255 | ○ | 深い所 (113、0700 の下) | 書けない | × | — | — | — | symlink-file: 置き場が長い (綴り 131 > 103)<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | 未設定・書けない | 書けない | × | — | — | — | symlink-file: 書ける置き場が無い<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | × | 深い所 (113、0700 の下) | 書けない | × | — | — | — | symlink-file: 置き場が長い (綴り 131 > 103)<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | 未設定・書けない | 書けない | × | — | — | — | symlink-file: 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |

#### 既定の bind / iOS 等の他の Apple の OS

効かない条件: 言語

| ファイル名 (バイト) | スレッドの cwd を使える | bind が symlink を辿る | $TMPDIR | /tmp | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | ○ | 既定 (/private/var/folders/…/T、56、0700) | 全部 | ○ | symlink-file | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 全部 | 全部 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | symlink-file | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 1–92 | ○ | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 1–92 | ○ | × | 全部 | 全部 | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 1–92 | × | ○ | 深い所 (113、0700 の下) | 書けない | × | — | — | — | symlink-file: 置き場が長い (綴り 131 > 103)<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | × | ○ | 未設定・書けない | 書けない | × | — | — | — | symlink-file: 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | × | × | 全部 | 全部 | × | — | — | — | symlink-file: bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 93–255 | ○ | ○ | 深い所 (113、0700 の下) | 書けない | × | — | — | — | symlink-file: 置き場が長い (綴り 131 > 103)<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | ○ | 未設定・書けない | 書けない | × | — | — | — | symlink-file: 書ける置き場が無い<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | × | 全部 | 全部 | × | — | — | — | symlink-file: bind が symlink を辿らない<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | × | ○ | 深い所 (113、0700 の下) | 書けない | × | — | — | — | symlink-file: 置き場が長い (綴り 131 > 103)<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | ○ | 未設定・書けない | 書けない | × | — | — | — | symlink-file: 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | × | 全部 | 全部 | × | — | — | — | symlink-file: bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |

#### 既定の bind / FreeBSD

効かない条件: 言語、$TMPDIR、/tmp

| ファイル名 (バイト) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|
| 1–92 | ○ | at | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 93–255 | × | — | — | — | at: ファイル名 > 92 | — | 見積もり |

#### 既定の bind / NetBSD

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|
| 全部 | 全部 | 書ける (1777) | ○ | symlink-file | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 全部 | /var/tmp (8、1777) | 書けない | ○ | symlink-file | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 1–92 | 深い所 (113、0700 の下) | 書けない | × | — | — | — | symlink-file: 置き場が長い (綴り 131 > 103) | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | 未設定・書けない | 書けない | × | — | — | — | symlink-file: 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書けない | × | — | — | — | symlink-file: 置き場が長い (綴り 131 > 103) | — | 見積もり |
| 93–255 | 未設定・書けない | 書けない | × | — | — | — | symlink-file: 書ける置き場が無い | — | 見積もり |

#### 既定の bind / OpenBSD

効かない条件: 言語、$TMPDIR、/tmp

| ファイル名 (バイト) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|
| 1–92 | × | — | — | — | この OS で試す経路が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | × | — | — | — | この OS で試す経路が無い | — | 見積もり |

#### 既定の bind / illumos

効かない条件: 言語、$TMPDIR、/tmp

| ファイル名 (バイト) | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|
| 1–96 | × | — | — | — | この OS で試す経路が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 97–255 | × | — | — | — | この OS で試す経路が無い | — | 見積もり |

#### 既定の bind / その他の Unix

効かない条件: 言語

| ファイル名 (バイト) | bind が symlink を辿る | $TMPDIR | /tmp | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | ○ | 全部 | 書ける (1777) | ○ | symlink-file | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 全部 | ○ | /var/tmp (8、1777) | 書けない | ○ | symlink-file | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 1–92 | ○ | 深い所 (113、0700 の下) | 書けない | × | — | — | — | symlink-file: 置き場が長い (綴り 131 > 103) | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | ○ | 未設定・書けない | 書けない | × | — | — | — | symlink-file: 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | × | 全部 | 全部 | × | — | — | — | symlink-file: bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | ○ | 深い所 (113、0700 の下) | 書けない | × | — | — | — | symlink-file: 置き場が長い (綴り 131 > 103) | — | 見積もり |
| 93–255 | ○ | 未設定・書けない | 書けない | × | — | — | — | symlink-file: 書ける置き場が無い | — | 見積もり |
| 93–255 | × | 全部 | 全部 | × | — | — | — | symlink-file: bind が symlink を辿らない | — | 見積もり |

### bind_ex

B の綴り (link-dir・link-file) を先に試し、収まらなければ thread-cwd (FreeBSD は at)

#### bind_ex / Linux / Android

効かない条件: 言語

| ファイル名 (バイト) | スレッドの cwd を使える | /proc を使える | $XDG_RUNTIME_DIR | $TMPDIR | /tmp | PrivateTmp (自分か相手が /tmp を隔離) | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1–67 | 全部 | 全部 | 全部 | /var/tmp (8、1777) | 全部 | ○ | ○ | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 1–67 | 全部 | 全部 | 全部 | /var/tmp (8、1777) | 全部 | × | ○ | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–71 | 全部 | 全部 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | ○ | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 1–71 | 全部 | 全部 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | × | ○ | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–74 | 全部 | ○ | 全部 | 全部 | 全部 | 全部 | × | ○ | link-dir (procB) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 1–67 | 全部 | × | 全部 | /var/tmp (8、1777) | 全部 | ○ | × | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 1–67 | 全部 | × | 全部 | /var/tmp (8、1777) | 全部 | × | × | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–61 | 全部 | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 全部 | 全部 | × | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–71 | 全部 | × | 無い・書けない | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 1–71 | 全部 | × | 無い・書けない | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | × | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–96 | ○ | 全部 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | ○ | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 1–96 | ○ | × | 無い・書けない | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 1–96 | × | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 1–96 | × | × | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 1–96 | × | × | 無い・書けない | 深い所 (113、0700 の下) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 1–96 | × | × | 無い・書けない | 未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 62–71 | 全部 | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 62–71 | 全部 | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | × | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 62–96 | ○ | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 62–96 | × | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 68–71 | 全部 | 全部 | 全部 | /var/tmp (8、1777) | 書ける (1777) | ○ | ○ | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 68–71 | 全部 | 全部 | 全部 | /var/tmp (8、1777) | 書ける (1777) | × | ○ | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 68–71 | 全部 | × | 全部 | /var/tmp (8、1777) | 書ける (1777) | ○ | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 68–71 | 全部 | × | 全部 | /var/tmp (8、1777) | 書ける (1777) | × | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 68–96 | ○ | 全部 | 全部 | /var/tmp (8、1777) | 書けない | 全部 | ○ | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 68–96 | ○ | × | 全部 | /var/tmp (8、1777) | 書けない | 全部 | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 68–96 | × | ○ | 全部 | /var/tmp (8、1777) | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 68–96 | × | × | 全部 | /var/tmp (8、1777) | 書けない | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–96 | ○ | 全部 | 全部 | 全部 | 書ける (1777) | 全部 | ○ | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 72–96 | ○ | × | 全部 | 全部 | 書ける (1777) | 全部 | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 72–96 | × | ○ | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–96 | × | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–96 | × | × | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–96 | × | × | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–96 | × | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–96 | × | × | 無い・書けない | 深い所 (113、0700 の下) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–96 | × | × | 無い・書けない | 未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | ○ | ○ | 全部 | 全部 | 全部 | 全部 | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 75–96 | × | ○ | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | × | ○ | 全部 | /var/tmp (8、1777) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | × | ○ | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | × | ○ | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | × | ○ | 無い・書けない | 深い所 (113、0700 の下) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | × | ○ | 無い・書けない | 深い所 (113、0700 の下) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | × | ○ | 無い・書けない | 未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | × | ○ | 無い・書けない | 未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 97–255 | ○ | ○ | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | ○ | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | ○ | 全部 | /var/tmp (8、1777) | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | ○ | 全部 | /var/tmp (8、1777) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | ○ | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | ○ | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | ○ | 無い・書けない | 深い所 (113、0700 の下) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | ○ | 無い・書けない | 深い所 (113、0700 の下) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | ○ | 無い・書けない | 未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | ○ | 無い・書けない | 未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | × | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | × | 全部 | /var/tmp (8、1777) | 書けない | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | × | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | × | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | × | 無い・書けない | 深い所 (113、0700 の下) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | × | 無い・書けない | 深い所 (113、0700 の下) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | × | 無い・書けない | 未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | ○ | × | 無い・書けない | 未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 96 | — | 見積もり |
| 97–255 | × | ○ | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | ○ | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | ○ | 全部 | /var/tmp (8、1777) | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | ○ | 全部 | /var/tmp (8、1777) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | ○ | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | ○ | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | ○ | 無い・書けない | 深い所 (113、0700 の下) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | ○ | 無い・書けない | 深い所 (113、0700 の下) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | ○ | 無い・書けない | 未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | ○ | 無い・書けない | 未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | × | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | × | 全部 | /var/tmp (8、1777) | 書けない | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | × | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | × | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | × | 無い・書けない | 深い所 (113、0700 の下) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | × | 無い・書けない | 深い所 (113、0700 の下) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | × | 無い・書けない | 未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 97–255 | × | × | 無い・書けない | 未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |

#### bind_ex / macOS

効かない条件: 言語

| ファイル名 (バイト) | スレッドの cwd を使える | $TMPDIR | /tmp | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1–15 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 全部 | × | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–59 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 書ける (1777) | ○ | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–59 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | ○ | 既定 (/private/var/folders/…/T、56、0700) | 書けない | ○ | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 1–92 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 1–92 | × | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | × | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | × | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 16–255 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 全部 | × | ○ | link-file (dirB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 60–255 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 書ける (1777) | ○ | ○ | link-file (tmpB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 60–255 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-file (tmpB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 93–255 | ○ | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | × | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |

#### bind_ex / iOS 等の他の Apple の OS

効かない条件: 言語

| ファイル名 (バイト) | スレッドの cwd を使える | bind が symlink を辿る | $TMPDIR | /tmp | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1–59 | 全部 | 全部 | 全部 | 書ける (1777) | ○ | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–15 | 全部 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 全部 | × | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–59 | 全部 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | ○ | 全部 | 全部 | 書けない | ○ | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 1–92 | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 1–92 | × | ○ | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | × | ○ | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | × | ○ | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | × | × | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | × | × | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | × | × | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 16–255 | 全部 | ○ | 既定 (/private/var/folders/…/T、56、0700) | 全部 | × | ○ | link-file (dirB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 16–59 | 全部 | × | 既定 (/private/var/folders/…/T、56、0700) | 書ける (1777) | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 16–92 | ○ | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない | × | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 16–92 | × | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない | × | × | — | — | — | link-dir (dirB): ファイル名 > 15<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 60–255 | 全部 | ○ | 全部 | 書ける (1777) | ○ | ○ | link-file (tmpB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 60–255 | 全部 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | × | ○ | link-file (tmpB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 60–92 | ○ | × | 全部 | 書ける (1777) | 全部 | ○ | thread-cwd | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 60–92 | × | × | 全部 | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 60–92 | × | × | 既定 (/private/var/folders/…/T、56、0700) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): ファイル名 > 15<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 60–92 | × | × | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 60–92 | × | × | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 93–255 | ○ | ○ | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | ○ | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | ○ | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | × | 全部 | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | × | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | × | 既定 (/private/var/folders/…/T、56、0700) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): ファイル名 > 15<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない | × | × | — | — | — | link-dir (dirB): ファイル名 > 15<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | × | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | × | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | × | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | ○ | × | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: ファイル名 > 92 | — | 見積もり |
| 93–255 | × | ○ | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | ○ | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | ○ | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | × | 全部 | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | × | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | × | 既定 (/private/var/folders/…/T、56、0700) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): ファイル名 > 15<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない | × | × | — | — | — | link-dir (dirB): ファイル名 > 15<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | × | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | × | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | × | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |
| 93–255 | × | × | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない<br>thread-cwd: スレッドの cwd を使えない | — | 見積もり |

#### bind_ex / FreeBSD

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1–63 | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–63 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–63 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | ○ | at | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 64–67 | 全部 | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 64–67 | 全部 | 書けない | 全部 | ○ | at | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 68–92 | 全部 | 全部 | 全部 | ○ | at | Dangling | 辿れない (片付け済み) | — | — | 見積もり |
| 93–255 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-dir (tmpB): ファイル名 > 67<br>at: ファイル名 > 92 | — | 見積もり |
| 93–255 | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-dir (tmpB): 書ける置き場が無い<br>at: ファイル名 > 92 | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 67<br>at: ファイル名 > 92 | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-dir (tmpB): ファイル名 > 67<br>at: ファイル名 > 92 | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>at: ファイル名 > 92 | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>at: ファイル名 > 92 | — | 見積もり |
| 93–255 | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 67<br>at: ファイル名 > 92 | — | 見積もり |
| 93–255 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>at: ファイル名 > 92 | — | 見積もり |

#### bind_ex / NetBSD

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1–63 | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–67 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 64–255 | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-file (dirB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 68–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-file (tmpB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |

#### bind_ex / OpenBSD

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1–63 | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–63 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 64–67 | 全部 | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 64–92 | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-dir (tmpB): ファイル名 > 67 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 67 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-dir (tmpB): ファイル名 > 67 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 67 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-dir (tmpB): ファイル名 > 67 | — | 見積もり |
| 93–255 | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 67 | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-dir (tmpB): ファイル名 > 67 | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 67 | — | 見積もり |
| 93–255 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |

#### bind_ex / illumos

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1–67 | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–67 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–96 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–96 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–96 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–71 | 全部 | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 68–96 | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 72–96 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 72–96 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 72–96 | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 72–96 | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 97–255 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |

#### bind_ex / その他の Unix

効かない条件: 言語

| ファイル名 (バイト) | bind が symlink を辿る | $TMPDIR | /tmp | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1–63 | 全部 | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–67 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | ○ | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | ○ | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | × | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | × | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | × | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 64–255 | ○ | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-file (dirB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 64–67 | × | /var/tmp (8、1777) | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 64–92 | × | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–255 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-file (tmpB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 68–92 | × | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | × | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | × | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | × | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | ○ | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | ○ | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | × | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |

### resolve_for_bind

bind_ex と同じ順で、パスを返すだけなので thread-cwd・at を持たない

#### resolve_for_bind / Linux / Android

効かない条件: 言語、スレッドの cwd を使える

| ファイル名 (バイト) | /proc を使える | $XDG_RUNTIME_DIR | $TMPDIR | /tmp | PrivateTmp (自分か相手が /tmp を隔離) | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1–67 | 全部 | 全部 | /var/tmp (8、1777) | 全部 | ○ | ○ | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 1–67 | 全部 | 全部 | /var/tmp (8、1777) | 全部 | × | ○ | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–71 | 全部 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | ○ | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 1–71 | 全部 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | × | ○ | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–74 | ○ | 全部 | 全部 | 全部 | 全部 | × | ○ | link-dir (procB) | Linked<br>removable: true<br>until: Process<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (プロセスが終わるまで) | — | — | 見積もり |
| 1–96 | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 1–67 | × | 全部 | /var/tmp (8、1777) | 全部 | ○ | × | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 1–67 | × | 全部 | /var/tmp (8、1777) | 全部 | × | × | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–96 | × | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 1–61 | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 全部 | 全部 | × | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–71 | × | 無い・書けない | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 1–71 | × | 無い・書けない | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | × | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–96 | × | 無い・書けない | 深い所 (113、0700 の下) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 1–96 | × | 無い・書けない | 未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 62–71 | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 62–71 | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | × | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 62–96 | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 68–71 | 全部 | 全部 | /var/tmp (8、1777) | 書ける (1777) | ○ | ○ | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 68–71 | 全部 | 全部 | /var/tmp (8、1777) | 書ける (1777) | × | ○ | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 68–96 | ○ | 全部 | /var/tmp (8、1777) | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 68–71 | × | 全部 | /var/tmp (8、1777) | 書ける (1777) | ○ | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れない (PrivateTmp) | — | — | 見積もり |
| 68–71 | × | 全部 | /var/tmp (8、1777) | 書ける (1777) | × | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 68–96 | × | 全部 | /var/tmp (8、1777) | 書けない | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–96 | ○ | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–96 | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–96 | × | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–96 | × | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–96 | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–96 | × | 無い・書けない | 深い所 (113、0700 の下) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 72–96 | × | 無い・書けない | 未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | ○ | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | ○ | 全部 | /var/tmp (8、1777) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | ○ | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | ○ | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | ○ | 無い・書けない | 深い所 (113、0700 の下) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | ○ | 無い・書けない | 深い所 (113、0700 の下) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | ○ | 無い・書けない | 未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 75–96 | ○ | 無い・書けない | 未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-linux-without-thread-cwd) | 見積もり |
| 97–255 | ○ | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | ○ | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | ○ | 全部 | /var/tmp (8、1777) | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | ○ | 全部 | /var/tmp (8、1777) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | ○ | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): 別の uid の指定で使わない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | ○ | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | ○ | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | ○ | 無い・書けない | 深い所 (113、0700 の下) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | ○ | 無い・書けない | 深い所 (113、0700 の下) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | ○ | 無い・書けない | 未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | ○ | 無い・書けない | 未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): ファイル名 > 74<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | × | 全部 | /var/tmp (8、1777) | 書ける (1777) | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | × | 全部 | /var/tmp (8、1777) | 書けない | 全部 | 全部 | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | × | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | × | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | ○ | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): ファイル名 > 61<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | × | 無い・書けない | 深い所 (113、0700 の下) | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | × | 無い・書けない | 深い所 (113、0700 の下) | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | × | 無い・書けない | 未設定・書けない | 書ける (1777) | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | × | 無い・書けない | 未設定・書けない | 書けない | 全部 | × | × | — | — | — | link-dir (procB): /proc を使えない<br>link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |

#### resolve_for_bind / macOS

効かない条件: 言語、スレッドの cwd を使える

| ファイル名 (バイト) | $TMPDIR | /tmp | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1–92 | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–15 | 既定 (/private/var/folders/…/T、56、0700) | 全部 | × | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–59 | 既定 (/private/var/folders/…/T、56、0700) | 書ける (1777) | ○ | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–59 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 16–255 | 既定 (/private/var/folders/…/T、56、0700) | 全部 | × | ○ | link-file (dirB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 60–255 | 既定 (/private/var/folders/…/T、56、0700) | 書ける (1777) | ○ | ○ | link-file (tmpB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 60–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-file (tmpB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 93–255 | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |

#### resolve_for_bind / iOS 等の他の Apple の OS

効かない条件: 言語、スレッドの cwd を使える

| ファイル名 (バイト) | bind が symlink を辿る | $TMPDIR | /tmp | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1–59 | 全部 | 全部 | 書ける (1777) | ○ | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–15 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 全部 | × | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–59 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | ○ | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | ○ | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | ○ | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | × | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | × | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 1–92 | × | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 16–255 | ○ | 既定 (/private/var/folders/…/T、56、0700) | 全部 | × | ○ | link-file (dirB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: false<br>usable_with_private_tmp: true | 辿れる (cleanup まで) | — | — | 見積もり |
| 16–59 | × | 既定 (/private/var/folders/…/T、56、0700) | 書ける (1777) | × | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 16–92 | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない | × | × | — | — | — | link-dir (dirB): ファイル名 > 15<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 60–255 | ○ | 全部 | 書ける (1777) | ○ | ○ | link-file (tmpB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 60–255 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | × | ○ | link-file (tmpB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 60–92 | × | 全部 | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 60–92 | × | 既定 (/private/var/folders/…/T、56、0700) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): ファイル名 > 15<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 60–92 | × | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 60–92 | × | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-apple-without-thread-cwd) | 見積もり |
| 93–255 | ○ | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | ○ | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | ○ | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | × | 全部 | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 全部 | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 既定 (/private/var/folders/…/T、56、0700) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): ファイル名 > 15<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 既定 (/private/var/folders/…/T、56、0700) | 書けない | × | × | — | — | — | link-dir (dirB): ファイル名 > 15<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 59<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |

#### resolve_for_bind / FreeBSD

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1–63 | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–63 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 64–67 | 全部 | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 64–92 | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-dir (tmpB): ファイル名 > 67 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 67 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-dir (tmpB): ファイル名 > 67 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 67 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-dir (tmpB): ファイル名 > 67 | — | 見積もり |
| 93–255 | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 67 | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-dir (tmpB): ファイル名 > 67 | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 67 | — | 見積もり |
| 93–255 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |

#### resolve_for_bind / NetBSD

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1–63 | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–67 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 64–255 | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-file (dirB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 68–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-file (tmpB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |

#### resolve_for_bind / OpenBSD

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1–63 | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–63 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 64–67 | 全部 | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 64–92 | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-dir (tmpB): ファイル名 > 67 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 67 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-dir (tmpB): ファイル名 > 67 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 67 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-dir (tmpB): ファイル名 > 67 | — | 見積もり |
| 93–255 | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 67 | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-dir (tmpB): ファイル名 > 67 | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 67 | — | 見積もり |
| 93–255 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |

#### resolve_for_bind / illumos

効かない条件: 言語

| ファイル名 (バイト) | $TMPDIR | /tmp | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1–67 | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–67 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–96 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–96 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–96 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–71 | 全部 | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 68–96 | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 72–96 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 72–96 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 72–96 | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 72–96 | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 97–255 | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 67<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 107)<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |
| 97–255 | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): ファイル名 > 71 | — | 見積もり |
| 97–255 | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い | — | 見積もり |

#### resolve_for_bind / その他の Unix

効かない条件: 言語

| ファイル名 (バイト) | bind が symlink を辿る | $TMPDIR | /tmp | 別の uid の相手と通信する | 届く | 経路 | 綴り | 綴りを相手が辿れるか | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1–63 | 全部 | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-dir (dirB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–67 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 1–92 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | ○ | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | ○ | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | × | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | × | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 1–92 | × | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 64–255 | ○ | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-file (dirB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 64–67 | × | /var/tmp (8、1777) | 書ける (1777) | 全部 | ○ | link-dir (tmpB) | Linked<br>removable: true<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 64–92 | × | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–255 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-file (tmpB) | Linked<br>removable: false<br>until: Cleanup<br>usable_cross_uid: true<br>usable_with_private_tmp: false | 辿れる (cleanup まで) | — | — | 見積もり |
| 68–92 | × | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | × | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | × | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 68–92 | × | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | [届く](../fork-cwd.md#bind-without-thread-cwd-means) | 見積もり |
| 93–255 | ○ | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): 別の uid が辿れる書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | ○ | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | ○ | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 93–255 | × | /var/tmp (8、1777) | 書ける (1777) | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | /var/tmp (8、1777) | 書けない | 全部 | × | — | — | — | link-dir (dirB): ファイル名 > 63<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 深い所 (113、0700 の下) | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 深い所 (113、0700 の下)<br>未設定・書けない | 書けない | ○ | × | — | — | — | link-dir (dirB): 別の uid が辿れる書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 深い所 (113、0700 の下) | 書けない | × | × | — | — | — | link-dir (dirB): 置き場が長い (ファイル名の他で 145 > 103)<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 未設定・書けない | 書ける (1777) | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): ファイル名 > 67<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |
| 93–255 | × | 未設定・書けない | 書けない | × | × | — | — | — | link-dir (dirB): 書ける置き場が無い<br>link-file (dirB): bind が symlink を辿らない<br>link-dir (tmpB): 書ける置き場が無い<br>link-file (tmpB): bind が symlink を辿らない | — | 見積もり |

### connect

connect・connect_nonblocking・connect_ex 系。DGRAM の connect・send_to も同じ経路 (send_to が relative を使わないかは issue の未決)

#### connect / Linux / Android

効かない条件: 言語

| ファイル名 (バイト) | 元のパスと相対パスの短い方 (バイト) | スレッドの cwd を使える | /proc を使える | $XDG_RUNTIME_DIR | $TMPDIR | /tmp | ソケットのディレクトリに書ける | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 108 以上 | × | × | 全部 | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| 全部 | 108 以上 | × | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 全部 | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| 全部 | 108 以上 | × | × | 無い・書けない | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-file (tmpB) | — | — | 見積もり |
| 1–90 | 全部 | 全部 | ○ | 全部 | 全部 | 全部 | 全部 | ○ | proc-direct | — | — | 実測: linux-long-connect |
| 1–107 | 1–107 | 全部 | × | 全部 | 全部 | 全部 | 全部 | ○ | relative | — | — | 実測: no-proc-connect-near-cwd |
| 1–107 | 108 以上 | ○ | × | 全部 | 全部 | 全部 | 全部 | ○ | thread-cwd-direct | — | — | 見積もり |
| 1–107 | 108 以上 | × | × | 無い・書けない | 深い所 (113、0700 の下) | 書けない | 全部 | × | — | proc-direct: /proc を使えない<br>relative: 相対パス > 107<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (procB): /proc を使えない<br>link-file (dirB): 置き場が長い (綴り 144 > 107)<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| 1–107 | 108 以上 | × | × | 無い・書けない | 未設定・書けない | 書けない | 全部 | × | — | proc-direct: /proc を使えない<br>relative: 相対パス > 107<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (procB): /proc を使えない<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| 91–107 | 全部 | ○ | ○ | 全部 | 全部 | 全部 | 全部 | ○ | thread-cwd-direct | — | — | 見積もり |
| 91–107 | 全部 | × | ○ | 全部 | 全部 | 書ける (1777) | 全部 | ○ | link-file (procB) | — | — | 見積もり |
| 91–107 | 全部 | × | ○ | 全部 | /var/tmp (8、1777)<br>深い所 (113、0700 の下) | 書けない | 全部 | ○ | link-file (procB) | — | — | 見積もり |
| 91–107 | 全部 | × | ○ | /run/user/<uid> (14、0700) | 未設定・書けない | 書けない | 全部 | ○ | link-file (procB) | — | — | 見積もり |
| 91–107 | 全部 | × | ○ | 無い・書けない | 未設定・書けない | 書けない | 書ける | ○ | link-file (procB) | — | — | 見積もり |
| 91–107 | 全部 | × | ○ | 無い・書けない | 未設定・書けない | 書けない | 書けない | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (procB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| 108–255 | 108 以上 | 全部 | ○ | 全部 | 全部 | 書ける (1777) | 全部 | ○ | link-file (procB) | — | — | 見積もり |
| 108–255 | 108 以上 | 全部 | ○ | 全部 | /var/tmp (8、1777)<br>深い所 (113、0700 の下) | 書けない | 全部 | ○ | link-file (procB) | — | — | 見積もり |
| 108–255 | 108 以上 | 全部 | ○ | /run/user/<uid> (14、0700) | 未設定・書けない | 書けない | 全部 | ○ | link-file (procB) | — | — | 見積もり |
| 108–255 | 108 以上 | 全部 | ○ | 無い・書けない | 未設定・書けない | 書けない | 書ける | ○ | link-file (procB) | — | — | 見積もり |
| 108–255 | 108 以上 | ○ | ○ | 無い・書けない | 未設定・書けない | 書けない | 書けない | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: ファイル名 > 107<br>link-file (procB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 108–255 | 108 以上 | ○ | × | 全部 | /var/tmp (8、1777) | 全部 | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| 108–255 | 108 以上 | ○ | × | /run/user/<uid> (14、0700) | 深い所 (113、0700 の下)<br>未設定・書けない | 全部 | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| 108–255 | 108 以上 | ○ | × | 無い・書けない | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | 全部 | ○ | link-file (tmpB) | — | — | 見積もり |
| 108–255 | 108 以上 | ○ | × | 無い・書けない | 深い所 (113、0700 の下) | 書けない | 全部 | × | — | proc-direct: /proc を使えない<br>relative: 相対パス > 107<br>thread-cwd-direct: ファイル名 > 107<br>link-file (procB): /proc を使えない<br>link-file (dirB): 置き場が長い (綴り 144 > 107)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 108–255 | 108 以上 | ○ | × | 無い・書けない | 未設定・書けない | 書けない | 全部 | × | — | proc-direct: /proc を使えない<br>relative: 相対パス > 107<br>thread-cwd-direct: ファイル名 > 107<br>link-file (procB): /proc を使えない<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 108–255 | 108 以上 | × | ○ | 無い・書けない | 未設定・書けない | 書けない | 書けない | × | — | proc-direct: ファイル名 > 90<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (procB): 書ける置き場が無い<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 108–255 | 108 以上 | × | × | 無い・書けない | 深い所 (113、0700 の下) | 書けない | 全部 | × | — | proc-direct: /proc を使えない<br>relative: 相対パス > 107<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (procB): /proc を使えない<br>link-file (dirB): 置き場が長い (綴り 144 > 107)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 108–255 | 108 以上 | × | × | 無い・書けない | 未設定・書けない | 書けない | 全部 | × | — | proc-direct: /proc を使えない<br>relative: 相対パス > 107<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (procB): /proc を使えない<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |

#### connect / macOS

効かない条件: ソケットのディレクトリに書ける

| 言語 | ファイル名 (バイト) | 元のパスと相対パスの短い方 (バイト) | スレッドの cwd を使える | $TMPDIR | /tmp | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 1–103 | 1–103 | 全部 | 全部 | 全部 | ○ | relative | — | — | 実測: long-connect |
| 全部 | 1–103 | 254 以上 | ○ | 全部 | 全部 | ○ | thread-cwd-direct | — | — | 見積もり |
| 全部 | 1–103 | 254 以上 | × | 既定 (/private/var/folders/…/T、56、0700) | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| 全部 | 1–103 | 254 以上 | × | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | link-file (tmpB) | — | — | 見積もり |
| rs<br>py | 1–253 | 104–253 | 全部 | 全部 | 全部 | ○ | widened | — | — | 実測: long-filename-connect |
| rs<br>py | 1–253 | 254 以上 | × | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 1–253 | 254 以上 | × | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 1–103 | 104–253 | ○ | 全部 | 全部 | ○ | thread-cwd-direct | — | — | 見積もり |
| go | 1–103 | 104–253 | × | 既定 (/private/var/folders/…/T、56、0700) | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| go | 1–103 | 104–253 | × | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | link-file (tmpB) | — | — | 見積もり |
| go | 1–253 | 104 以上 | × | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 1–253 | 104 以上 | × | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| 全部 | 104–255 | 254 以上 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| 全部 | 104–255 | 254 以上 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | link-file (tmpB) | — | — | 見積もり |
| rs<br>py | 104–253 | 254 以上 | ○ | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 104–253 | 254 以上 | ○ | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 104–253 | 104–253 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| go | 104–253 | 104–253 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | link-file (tmpB) | — | — | 見積もり |
| go | 104–253 | 104 以上 | ○ | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 104–253 | 104 以上 | ○ | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 254–255 | 254 以上 | ○ | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | ○ | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | × | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | × | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| go | 254–255 | 254 以上 | ○ | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| go | 254–255 | 254 以上 | ○ | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| go | 254–255 | 254 以上 | × | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| go | 254–255 | 254 以上 | × | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |

#### connect / iOS 等の他の Apple の OS

効かない条件: ソケットのディレクトリに書ける

| 言語 | ファイル名 (バイト) | 元のパスと相対パスの短い方 (バイト) | スレッドの cwd を使える | $TMPDIR | /tmp | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|---|---|
| 全部 | 1–103 | 1–103 | 全部 | 全部 | 全部 | ○ | relative | — | — | 見積もり |
| 全部 | 1–103 | 254 以上 | ○ | 全部 | 全部 | ○ | thread-cwd-direct | — | — | 見積もり |
| 全部 | 1–103 | 254 以上 | × | 既定 (/private/var/folders/…/T、56、0700) | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| 全部 | 1–103 | 254 以上 | × | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | link-file (tmpB) | — | — | 見積もり |
| rs<br>py | 1–253 | 104–253 | 全部 | 全部 | 全部 | ○ | widened | — | — | 見積もり |
| rs<br>py | 1–253 | 254 以上 | × | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 1–253 | 254 以上 | × | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 1–103 | 104–253 | ○ | 全部 | 全部 | ○ | thread-cwd-direct | — | — | 見積もり |
| go | 1–103 | 104–253 | × | 既定 (/private/var/folders/…/T、56、0700) | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| go | 1–103 | 104–253 | × | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | link-file (tmpB) | — | — | 見積もり |
| go | 1–253 | 104 以上 | × | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 1–253 | 104 以上 | × | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| 全部 | 104–255 | 254 以上 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| 全部 | 104–255 | 254 以上 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | link-file (tmpB) | — | — | 見積もり |
| rs<br>py | 104–253 | 254 以上 | ○ | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 104–253 | 254 以上 | ○ | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 104–253 | 104–253 | 全部 | 既定 (/private/var/folders/…/T、56、0700) | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| go | 104–253 | 104–253 | 全部 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | link-file (tmpB) | — | — | 見積もり |
| go | 104–253 | 104 以上 | ○ | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| go | 104–253 | 104 以上 | ○ | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| rs<br>py | 254–255 | 254 以上 | ○ | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | ○ | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | × | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| rs<br>py | 254–255 | 254 以上 | × | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: 元のパスも相対パスも > 253<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| go | 254–255 | 254 以上 | ○ | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| go | 254–255 | 254 以上 | ○ | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: ファイル名 > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| go | 254–255 | 254 以上 | × | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| go | 254–255 | 254 以上 | × | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>widened: この言語に無い<br>thread-cwd-direct: スレッドの cwd を使えない<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |

#### connect / FreeBSD

効かない条件: 言語、ソケットのディレクトリに書ける

| ファイル名 (バイト) | $TMPDIR | /tmp | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|
| 1–103 | 全部 | 全部 | ○ | at-direct | — | — | 見積もり |
| 104–255 | /var/tmp (8、1777) | 全部 | ○ | link-file (dirB) | — | — | 見積もり<br>FreeBSD の connect で link-file を使えるかは未確認 (issue) |
| 104–255 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | link-file (tmpB) | — | — | 見積もり<br>FreeBSD の connect で link-file を使えるかは未確認 (issue) |
| 104–255 | 深い所 (113、0700 の下) | 書けない | × | — | at-direct: ファイル名 > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 104–255 | 未設定・書けない | 書けない | × | — | at-direct: ファイル名 > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |

#### connect / NetBSD

効かない条件: 言語、ソケットのディレクトリに書ける

| ファイル名 (バイト) | 元のパスと相対パスの短い方 (バイト) | $TMPDIR | /tmp | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|
| 全部 | 104 以上 | /var/tmp (8、1777) | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| 全部 | 104 以上 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | link-file (tmpB) | — | — | 見積もり |
| 1–103 | 1–103 | 全部 | 全部 | ○ | relative | — | — | 見積もり |
| 1–103 | 104 以上 | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| 1–103 | 104 以上 | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| 104–255 | 104 以上 | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 104–255 | 104 以上 | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |

#### connect / OpenBSD

効かない条件: 言語、ソケットのディレクトリに書ける

| ファイル名 (バイト) | 元のパスと相対パスの短い方 (バイト) | $TMPDIR | /tmp | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|
| 全部 | 104 以上 | /var/tmp (8、1777) | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| 全部 | 104 以上 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | link-file (tmpB) | — | — | 見積もり |
| 1–103 | 1–103 | 全部 | 全部 | ○ | relative | — | — | 見積もり |
| 1–103 | 104 以上 | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| 1–103 | 104 以上 | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| 104–255 | 104 以上 | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 104–255 | 104 以上 | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |

#### connect / illumos

効かない条件: 言語、ソケットのディレクトリに書ける

| ファイル名 (バイト) | 元のパスと相対パスの短い方 (バイト) | $TMPDIR | /tmp | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|
| 全部 | 108 以上 | /var/tmp (8、1777) | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| 全部 | 108 以上 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | link-file (tmpB) | — | — | 見積もり |
| 1–107 | 1–107 | 全部 | 全部 | ○ | relative | — | — | 見積もり |
| 1–107 | 108 以上 | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 107<br>link-file (dirB): 置き場が長い (綴り 144 > 107)<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| 1–107 | 108 以上 | 未設定・書けない | 書けない | × | — | relative: 相対パス > 107<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| 108–255 | 108 以上 | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 107<br>link-file (dirB): 置き場が長い (綴り 144 > 107)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 108–255 | 108 以上 | 未設定・書けない | 書けない | × | — | relative: 相対パス > 107<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |

#### connect / その他の Unix

効かない条件: 言語、ソケットのディレクトリに書ける

| ファイル名 (バイト) | 元のパスと相対パスの短い方 (バイト) | $TMPDIR | /tmp | 届く | 経路 | 届かない理由 | fork-cwd なら | 根拠 |
|---|---|---|---|---|---|---|---|---|
| 全部 | 104 以上 | /var/tmp (8、1777) | 全部 | ○ | link-file (dirB) | — | — | 見積もり |
| 全部 | 104 以上 | 深い所 (113、0700 の下)<br>未設定・書けない | 書ける (1777) | ○ | link-file (tmpB) | — | — | 見積もり |
| 1–103 | 1–103 | 全部 | 全部 | ○ | relative | — | — | 見積もり |
| 1–103 | 104 以上 | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| 1–103 | 104 以上 | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | [届く](../fork-cwd.md#connect-without-place-or-thread-cwd) | 見積もり |
| 104–255 | 104 以上 | 深い所 (113、0700 の下) | 書けない | × | — | relative: 相対パス > 103<br>link-file (dirB): 置き場が長い (綴り 144 > 103)<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |
| 104–255 | 104 以上 | 未設定・書けない | 書けない | × | — | relative: 相対パス > 103<br>link-file (dirB): 書ける置き場が無い<br>link-file (tmpB): 書ける置き場が無い | — | 見積もり |

