# 利用者 2 つが sockat-rs 0.5.1 に上げた時の実測 (置き場に残る物と届く範囲)

- Date: 2026-11-21 (測定日)

llm-gateway と hyoui (どちらも sockat-rs 0.5.1 を使う kawaz のプロダクト) が 0.5.1 に上げた時に、自分の試験と実機確認で置き場 B に何が残るかと、ファイル名の長さごとに bind / connect が届くかを測った。その結果を、届く範囲の表 ([pages/reach](../../pages/reach/README-ja.md)) と突き合わせる。

## 判明した事実

- 置き場に溜まるのは D より E が多い。1 プロセスが D を 1 つ作り、その中に長いパスの bind の数だけ E を残す。hyoui の lib test では D 1 つあたり E は平均 15 程度、llm-gateway では D 1 つあたり 1〜65、hyoui のフル検証 1 回では D 264・E 2550
- 容量は無視できる。llm-gateway の 1 回分 (D 12・E 150) は `du` で 0
- macOS の `/tmp` の B (`/tmp/sockat-501`) は、試験を繰り返すと再起動まで溜まり続ける (`sweep()` を呼ばない限り)。測ったマシン (macOS 26) には定期の掃除の設定 (`/etc/defaults/periodic.conf`) が無い
- `sockat::sweep()` は、生きている D が無い時に B の中の D を全部消し、B は残した (D 292・E 3035 → 0・0)
- Linux docker (root) でも同じ形で溜まる。試験のプロセス 88 個の後に `/tmp/sockat-0` に D 87・E 1008
- 届く範囲の実測は、届く範囲の表が「届く」とした所で届かなかった所は無い。逆 (表が「届かない」とし、実測で届いた) は Linux の bind の 77〜79 バイト (thread-cwd を使えない環境) で、uid・pid・fd・E の桁が表の代表値より短かったため
- 経路の境目は表の見積もりより 1〜3 バイト後ろにずれた。ずれは全部、綴りの式に実測の環境の桁 (uid 0 / 501、pid・fd が 1〜2 桁、E が 1 文字) を入れると説明できる

## 実用的な示唆 / ベストプラクティス

- 置き場の溜まり方を見積もる時は E の数 (長いパスで bind した回数の合計) で見る。D の数 (長いパスで bind したプロセスの数) は 1 桁小さい
- 試験で長いパスの bind を繰り返す利用者は、試験の後に `sweep()` を呼ぶ (macOS の `/tmp` は再起動まで消えない)。効くのは容量でなく数
- 届く範囲の表は、桁を長め (uid 4 桁、pid 7 桁、fd 2 桁、E 2 文字) に見積もっているので、実機では表より少し長い名前まで届く。表は安全側に外れていて、表を直す必要は今回の実測からは出ない
- 「環境によらず届く」ファイル名の長さは下の「環境によらず届く長さ」の節の式で出せる。Linux で thread-cwd を使えない環境 (docker の既定 seccomp 等) の bind は 70 バイト以下が目安

## 検証の詳細

### 環境と手順

| 利用者 | 環境 | 手順 |
|---|---|---|
| llm-gateway | macOS、`$TMPDIR` を 113 バイトの深い所に向ける | `just test` を 1 回 (1669 passed)。前後に `/tmp/sockat-501` の D と E を数える |
| hyoui | macOS 26 (Darwin 25.5.0)、`$TMPDIR` は既定、`$XDG_RUNTIME_DIR` は未設定 | `cargo test` 数回、lib test のプロセス 140 個の繰り返し、実機確認の daemon 約 22 個、`cargo test --workspace` 1 回、`sockat::sweep()`。各時点で D と E を数える |
| hyoui | Linux docker (native arm64)、root、既定 seccomp と `--security-opt seccomp=unconfined` | 試験のプロセス 88 個 (lib test 86 + 統合 test 2)。届く範囲は、深さ 2 通りのディレクトリ (106 バイトと 306 バイト) で、ファイル名の長さを変えて bind / connect を試す |
| hyoui | macOS 26 | 届く範囲を、深さ 2 通りのディレクトリ (119 バイトと 291 バイト) で、ファイル名 41〜253 バイトについて試す |

- D と E の数え方: B の直下のディレクトリを D、D の中の symlink を E として数える。D は、中の E の指す先で「hyoui の検証の物」と「それ以外」(同じ時間に動いていた llm-gateway の試験、sockat 自身の試験) に分けた
- 届く範囲の connect は、bind が届かない長さでは socket のディレクトリに移って標準の bind で作った socket に対して測った。108 バイト以上は Linux の標準の bind でも socket を作れないので測っていない
- ファイル名の標本: Linux は 41、55〜110、120、200、250。macOS は 41、60〜130、200〜253。間の長さは補間

### 置き場に残った物 (macOS、hyoui、`/tmp/sockat-501`)

`$TMPDIR` と `$XDG_RUNTIME_DIR` の下には B が無かった (`/tmp` が書けるので 1 番目の置き場が使われる)。B の直下の E (既定の connect の物) はどの時点も 0。

| 時点 | D 合計 | E 合計 | hyoui の D / E | それ以外の D / E | 空の D |
|---|---|---|---|---|---|
| 作業前 | 3 | 185 | 0 / 0 | 3 / 185 | 1 |
| 繰り返しの前 (cargo test 数回の後) | 32 | 733 | 5 / 248 | 26 / 485 | 1 |
| 繰り返しの後 (lib test 140 プロセス + daemon 約 22) | 194 | 2915 | 167 / 2430 | 26 / 485 | 1 |
| `cargo test --workspace` 1 回の後 | 292 | 3035 | 264 / 2550 | 26 / 485 | 2 |
| `sockat::sweep()` の後 | 0 | 0 | 0 / 0 | 0 / 0 | 0 |

- 作業前の D 3 つのうち 1 つは E 184 を持っていた (sockat 自身の試験とみられる)
- `sweep()` の時点で生きている D は無く、全部消えた。B (`/tmp/sockat-501`) 自身は残った

### 置き場に残った物 (macOS、llm-gateway)

| 項目 | 値 |
|---|---|
| `/tmp/sockat-501` の D (試験の前 → 後) | 3 → 15 (+12。長いパスで bind した試験のバイナリの数) |
| 増えた D の中の E の合計 | 150 |
| D ごとの E | 1〜65 |
| 容量 (`du`) | 0 |

### 置き場に残った物 (Linux docker、hyoui)

| 項目 | 値 |
|---|---|
| 試験のプロセス | 88 (lib test 86 + 統合 test 2) |
| `/tmp/sockat-0` の D | 87 |
| E の合計 | 1008 |
| 届く範囲の測定 (2 プロセス) の後 | D 2・E 52 |

### 届く範囲 (Linux docker arm64、root、hyoui)

ディレクトリ 106 バイトと 306 バイトで同じ結果。

| ファイル名 (バイト) | 既定 seccomp: bind | 既定 seccomp: connect | unconfined: bind | unconfined: connect |
|---|---|---|---|---|
| 41〜79 | ok (link-dir、procB) | ok (proc-direct) | ok (link-dir、procB) | ok (proc-direct) |
| 80〜91 | ENAMETOOLONG | ok (proc-direct) | ok (thread-cwd、Dangling) | ok (proc-direct) |
| 92〜96 | ENAMETOOLONG | ok (link-file) | ok (thread-cwd、Dangling) | ok (thread-cwd-direct) |
| 97〜107 | ENAMETOOLONG | ok (link-file) | ENAMETOOLONG | ok (thread-cwd-direct) |
| 108 以上 | ENAMETOOLONG | 測れない (相手の socket を作れない) | ENAMETOOLONG | 測れない |

- 既定 seccomp では thread-cwd が経路に一度も出ない (seccomp が `unshare` を断る)
- 既定 seccomp の 79 バイトは、hyoui の 1 回目の測定では link-dir の実パスの B (`tmp`)、2 回目 (上の表) では procB で届いた。procB の綴りの長さが pid・fd の桁で変わるため
- link-dir の Spelling は `Linked { removable: true, until: Process, usable_cross_uid: false, usable_with_private_tmp: true }`

### 届く範囲 (macOS 26、hyoui)

ファイル名 41〜253 バイトの全部で bind も connect も届いた。

| ファイル名 (バイト) | bind | connect (119 バイトのディレクトリ) | connect (291 バイトのディレクトリ) |
|---|---|---|---|
| 41〜66 | link-dir (B: tmp) | widened | thread-cwd-direct |
| 67〜103 | link-file (B: tmp) | widened | thread-cwd-direct |
| 104〜128 | link-file (B: tmp) | widened | link-file |
| 129〜253 | link-file (B: tmp) | link-file | link-file |

- 119 バイトのディレクトリで widened が 128 まで、129 から link-file に変わる所は、パス全体が 253 バイト (Apple の広げた sockaddr に入る長さ) を超える所と一致する (128 でパス 253、129 で 254)
- 291 バイトのディレクトリで thread-cwd-direct が 103 まで、104 から link-file に変わる所は、ファイル名が sockaddr (103) を超える所と一致する

### 届く範囲の表との突き合わせ

表は [pages/reach/README-ja.md](../../pages/reach/README-ja.md) (正本は `model.json`、`gen.py` が生成)。条件を実測の環境に合わせて引いた。

| 実測 | 表の行 (条件) | 表 | 実測 | 判定 |
|---|---|---|---|---|
| Linux 既定 seccomp の bind 41〜73 | 既定の bind / Linux (スレッドの cwd ×、/proc ○、/tmp 書ける) | link-dir (B: proc) | link-dir (procB) | 一致 |
| Linux 既定 seccomp の bind 74〜76 | 同上 | link-dir (B: tmp) | link-dir (procB) | 届くは一致、経路が違う |
| Linux 既定 seccomp の bind 77〜79 | 同上 | 届かない | link-dir (procB、1 回目は B: tmp) | 表が届かないとし、届いた |
| Linux 既定 seccomp の bind 80〜96 | 同上 | 届かない | ENAMETOOLONG | 一致 |
| Linux の bind 97 以上 (両方) | 97–255 の行 | 届かない | ENAMETOOLONG | 一致 |
| Linux unconfined の bind 74〜76 | 既定の bind / Linux (スレッドの cwd ○、/proc ○、/tmp 書ける) | link-dir (B: tmp) | link-dir (procB) | 届くは一致、経路が違う |
| Linux unconfined の bind 77〜79 | 同上 | thread-cwd | link-dir (procB) | 届くは一致、経路が違う |
| Linux unconfined の bind 80〜96 | 同上 | thread-cwd | thread-cwd (Dangling) | 一致 |
| Linux の connect 91 | 既定の connect / Linux (/proc ○) | 91–107 は thread-cwd-direct (unconfined) / link-file (B: tmp) (既定 seccomp) | proc-direct | 届くは一致、経路が違う |
| Linux の connect 92〜107 | 同上 | thread-cwd-direct / link-file (B: tmp) | thread-cwd-direct / link-file | 一致 |
| macOS の bind 41〜64 | 既定の bind / macOS (/tmp 書ける) | link-dir (B: tmp) | link-dir (B: tmp) | 一致 |
| macOS の bind 65〜66 | 同上 | link-file (B: tmp) | link-dir (B: tmp) | 届くは一致、経路が違う |
| macOS の bind 67〜253 | 同上 | link-file (B: tmp) | link-file (B: tmp) | 一致 |
| macOS の connect (119 バイト) 41〜128 | 既定の connect / macOS (rs、短い方 104–253) | widened | widened | 一致 |
| macOS の connect (119 バイト) 129〜253 | 104–255、短い方 254 以上、/tmp 書ける | link-file (B: tmp) | link-file | 一致 |
| macOS の connect (291 バイト) 41〜103 | 1–103、短い方 254 以上、スレッドの cwd ○ | thread-cwd-direct | thread-cwd-direct | 一致 |
| macOS の connect (291 バイト) 104〜253 | 104–255、短い方 254 以上、/tmp 書ける | link-file (B: tmp) | link-file | 一致 |

ずれの説明 (綴りの式に実測の環境の桁を入れる。sockaddr は Linux 107、macOS 103):

| ずれ | 表の見積もり | 実測の環境 |
|---|---|---|
| Linux の procB の上限 | `107 − 23 − pid − fd − E` = 107 − 23 − 7 − 2 − 2 = 73 | docker の pid・fd が短く (pid + fd ≤ 3)、79 まで届く |
| Linux の実パスの B (`/tmp/sockat-<uid>`) の上限 | `107 − 25 − uid − E` = 107 − 25 − 4 − 2 = 76 | root で uid 1 桁: 107 − 25 − 1 − 2 = 79 (1 回目の測定で B: tmp が 79 まで届いたのと一致) |
| Linux の proc-direct の上限 | `107 − 15 − fd` = 107 − 15 − 2 = 90 | fd 1 桁: 91 |
| macOS の実パスの B (`/private/tmp/sockat-<uid>`) の link-dir の上限 | `103 − 33 − uid − E` = 103 − 33 − 4 − 2 = 64 | uid 501 で 3 桁、E 1 文字: 103 − 33 − 3 − 1 = 66 |

- 測定は名前ごとに bind と bind_ex を呼んでいる (生データの列が `bind` と `bind_ex_route`)。E のカウンタは呼ぶたびに進むので、Linux の 80 バイトの時点でカウンタは 36 を超え E は 2 文字だったとみられる (E が 1 文字なら実パスの B で 80 まで届く計算になるが、届いていない)。カウンタの値そのものは記録に無く、推定

### 環境によらず届く長さ

綴りの長さの式 (`/proc/` 6、`/fd/` 4、区切りの `/` 1 つ 1 バイト、D 10 文字、`sockat-` 7。[SPEC-routes の「綴りの形」「D と E」](../SPEC-routes-ja.md#d-と-e)) で、各桁の最悪の値を入れて、綴りが sockaddr に収まる最長のファイル名 F を出す。

桁の最悪の値:

| 記号 | 中身 | 最悪の桁 |
|---|---|---|
| p | procB の pid | 7 (Linux の pid_max の上限 4194304、最大の pid は 4194303) |
| f | procB の B の fd | 7 (Linux の `fs.nr_open` の既定 1048576、最大の fd は 1048575)。カーネルが許す `nr_open` の上限まで上げた環境では 10 |
| u | B の名前の uid | 10 (uid_t は 32 ビット、最大の有効な uid は 4294967294) |
| e | resolve の E の名前 | D ごとのカウンタ (0 から、36 進)。D の中で n 個目の E は `⌊log36 n⌋ + 1` 文字。1296 個までは 2、46656 個までは 3。u64 の上限で 13 |

Linux (sockaddr 107):

| 経路 | 綴り | 式 | 最悪の桁で (e = 2) |
|---|---|---|---|
| link-dir (procB) | `/proc/<pid>/fd/<fd>/<D>/<E>/<F>` | 6 + p + 4 + f + 1 + 10 + 1 + e + 1 + F ≤ 107 → F ≤ 84 − p − f − e | p 7、f 2: 73。f 4 (ulimit 1024): 71。f 7: 68 |
| link-dir (実パスの B、`/tmp`) | `/tmp/sockat-<uid>/<D>/<E>/<F>` | 4 + 1 + 7 + u + 1 + 10 + 1 + e + 1 + F ≤ 107 → F ≤ 82 − u − e | u 10: 70 (pid・fd によらない) |
| thread-cwd | `<Er>/<F>` | 10 + 1 + F ≤ 107 → F ≤ 96 | 96 (桁によらない) |
| proc-direct (connect) | `/proc/self/fd/<fd>/<F>` | 14 + f + 1 + F ≤ 107 → F ≤ 92 − f | f 7: 85 |
| link-file (connect、B の直下) | `/tmp/sockat-<uid>/<Er>` | 12 + u + 1 + 10 ≤ 107 | いつも収まる (F によらない) |

- Linux の bind は procB と実パスの B の両方を順に試すので、届く長さは 2 つの式の大きい方。thread-cwd を使えない環境 (docker の既定 seccomp) で、B が `/tmp` にある時: max(84 − p − f − e, 82 − u − e)。実パスの B の側が pid・fd によらないので、下限は **82 − 10 − e = 72 − e**。E が 2 文字 (D の中の E が 1296 個まで) で **70 バイト**、3 文字 (46656 個まで) で 69、カウンタの上限 (13 文字) で 59
- thread-cwd を使える環境では **96 バイト** (桁によらない)
- 前提: B は `/tmp/sockat-<uid>` (既にある `sockat-<uid>` が確かめに外れて `sockat-<uid>.<乱数 10 文字>` に落ちると 11 バイト長く、下限は 59 − (e − 2))。`/tmp` に作れず `$XDG_RUNTIME_DIR` (`/run/user/<uid>/sockat`) の時は 10 + u + 7 + 1 + 10 + 1 + e + 1 + F ≤ 107 → F ≤ 77 − u − e で 65 (e = 2)
- Linux の connect は、B を `/tmp` に作れれば link-file がファイル名によらず届く。置き場が無くても thread-cwd を使えれば 107、/proc だけなら 92 − f

macOS (sockaddr 103、`/tmp` の実パスは `/private/tmp`):

| 経路 | 綴り | 式 | 最悪の桁で |
|---|---|---|---|
| link-dir (実パスの B) | `/private/tmp/sockat-<uid>/<D>/<E>/<F>` | 12 + 1 + 7 + u + 1 + 10 + 1 + e + 1 + F ≤ 103 → F ≤ 70 − u − e | u 10、e 2: 58 |
| link-file (実パスの B) | `/private/tmp/sockat-<uid>/<D>/<E>` | 20 + u + 1 + 10 + 1 + e ≤ 103 | u 10、e 13: 55 で、いつも収まる (F によらない) |
| thread-cwd | `<Er>/<F>` | 10 + 1 + F ≤ 103 → F ≤ 92 | 92 |
| thread-cwd-direct (connect) | `<F>` | F ≤ 103 | 103 |
| link-file (connect、B の直下) | `/private/tmp/sockat-<uid>/<Er>` | 20 + u + 1 + 10 ≤ 103 | いつも収まる |

- macOS は bind が symlink を辿るので link-file を使え、B が `/tmp` にあれば bind も connect もファイル名の上限 (NAME_MAX 255) まで桁によらず届く。実測 (253 まで) と一致
- `/tmp` に B を作れず `$TMPDIR` が深い所 (113 バイト) の時は、bind は thread-cwd の **92 バイト**、connect は thread-cwd-direct の **103 バイト** が下限 (`pthread_fchdir_np` は macOS にいつもある)

## 未確認

- E の溜まり方の測定は macOS と Linux docker (root) だけ。Linux の一般ユーザ (`/tmp` の systemd-tmpfiles が死んだ D を 10 日で消す環境) で日をまたいだ減り方は測っていない
- Linux の届く範囲は arm64 の docker だけ。pid・fd が大きい環境 (pid 7 桁) で procB の境目が式どおり縮むかは測っていない
- 108 バイト以上のファイル名への Linux の connect は、相手の socket を作れないので測っていない (表は link-file で届くとする)
