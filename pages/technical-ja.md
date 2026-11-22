# sockat 技術説明

> [English](./technical.md) | 日本語

sockat が長いパスの代わりに短いパスをどう作っているかの説明です。検討した手法を並べて比べ、sockat がどれをどの順で使うかと、その理由を書きます。使い方は [README](../README-ja.md) と [利用マニュアル](./manual-ja.md) にあります。

## 何が問題か

```
/home/u/.cache/example-app/worktrees/feature-login/.tmp/test-0f3a9c/daemon.sock
```

Unix domain socket のアドレス (`sockaddr_un`) は、パスを `sun_path` という固定長の欄に入れて渡します。NUL の分を除いて入るのは、Linux で 107 バイト、macOS と BSD で 103 バイトです。この文書ではこれを「sockaddr に入る長さ」と呼びます。上のような深い所のパスはこれを超え、標準ライブラリが bind / connect の前に断ります (Rust の `path must be shorter than SUN_LEN`、Python の `AF_UNIX path too long` 等)。Linux の Node.js 22 のように、黙って 108 バイトに切り詰めて別の所に作ってしまう標準ライブラリもあります。

上限に当たるのは、カーネルに渡すパスの文字列の長さです。ディレクトリの深さではありません。同じ場所を指す短い文字列を渡せば、深い所のソケットにも届きます。

```
/very/deep/.../dir/daemon.sock    長すぎて sun_path に入らない
daemon.sock                       cwd が /very/deep/.../dir なら同じ所
/tmp/x/L/daemon.sock              /tmp/x/L が /very/deep/.../dir を指す symlink なら同じ所
```

この文書では、カーネルに渡すパスの文字列を「綴り」と呼びます。元のパスと同じ所を指す短い綴りをどう作るかが、sockat の中身です。

- `/tmp` 等の短い場所に別のソケットを作る回避策は、元のパスにソケットができないので扱いません
- ディレクトリの部分は手法しだいで綴りから消せますが、ファイル名 (パスの最後の要素) は多くの手法で綴りに残ります。そのため届く長さは、多くの手法で「ファイル名が何バイトまでか」で決まります

## 短い綴りを作る手法

### cwd を移す

```
chdir("/very/deep/.../dir")
bind(sock, "daemon.sock")
```

cwd をソケットのディレクトリに移せば、ファイル名だけの綴りで届きます。誰の cwd を移すかで 3 つに分かれます。

- **プロセスの chdir**: 一番素直です。ただし cwd はプロセスに 1 つなので、ライブラリの呼び出しがプロセス全体の状態を変えます
- **スレッドの cwd**: 使い捨てのスレッドの cwd だけを移します。Linux は `unshare(CLONE_FS)` の後に `fchdir`、Apple の OS は `pthread_fchdir_np` を使います。使えるのは Linux / Android と Apple の OS です
- **fork した子**: 子だけが移って bind / connect し、すぐ終わります。子と親は同じソケットを共有しているので、結果は親のソケットに残ります。bind の後の listen は親がします (子に listen させると、相手に見えるサーバの peer が死んだ子になります)

届く長さは、綴りがファイル名だけなら、ファイル名が sockaddr に入る長さ (Linux 107、macOS と BSD 103) までです。

短所:

- スレッドの cwd は、Linux で seccomp の filter が掛かっていると使えません (docker の既定や、systemd の `SystemCallFilter=`)。filter によっては `unshare` を呼んだだけでプロセスが SIGSYS で殺されるので、掛かっているかを先に確かめる必要があります
- `pthread_fchdir_np` は libSystem の非公開 API で、将来消えるおそれがあります
- スレッドを立てる費用が掛かります。TypeScript の実装の調査では、使い捨ての Worker を立てる形が 1 回およそ 9ms、symlink を通した綴りで標準ライブラリの connect をする形が 0.1ms でした
- fork は副作用がプロセス全体に及びます。子が全 fd の複製を持つ、親に `SIGCHLD` が届く、`pthread_atfork` の handler が走る、他のスレッドの `waitpid(-1)` が子を刈り取りうる、connect では相手に見える peer の pid が終わった子になる、等です。Go では fork した子で runtime が動かないので使えません
- bind では、カーネルが覚える綴りがファイル名だけになります ([次の節](#bind-と-connect-で事情が違う))

### cwd からの相対パス

```
cwd:   /home/u/work
元:    /home/u/work/a/very/deep/.../dir/daemon.sock
綴り:  a/very/deep/.../dir/daemon.sock
```

chdir はせず、文字列を書き直すだけです。cwd が元のパスの上にあれば前を削り、そうでなければ `..` で上る綴りを作ります。

- 長所: 書き込みもスレッドも要らず、どの OS でも使えます。ソケットのディレクトリが cwd に近ければ、ファイル名が長くても届きます
- 短所: 届くかは cwd しだいです (相対パス全体が sockaddr に入る長さ以内)。綴りを作ってから使うまでに他のスレッドが cwd を変えると、別の所を指します。bind の綴りは、後で cwd が変わった時にも別の所を指します

### `/proc/self/fd/<fd>/<名前>`

```
fd = open("/very/deep/.../dir", O_PATH | O_DIRECTORY)     → 7
綴り:  /proc/self/fd/7/daemon.sock
```

ソケットのディレクトリを開いて fd を持ち、`/proc` の fd を通して綴ります。

- 使える OS: `/proc` のある Linux / Android
- 届く長さ: ファイル名がおよそ 90 バイトまで (fd の桁で変わる)
- 長所: 書き込みもスレッドも要りません。crun・conmon・podman・systemd の `connect_unix_path`・Bun の標準ライブラリ (Linux) が、長いパスにこの形を使っています
- 短所: PID 名前空間と `/proc` の mount が食い違う環境に備える必要があります。sockat は `/proc/self/fd/<fd>` を stat した `(st_dev, st_ino)` が fd の `fstat` と同じ時だけ使います。bind では、fd を閉じた後に綴りが別の所を指します

### symlink を置く

```
/tmp/x/L  →  /very/deep/.../dir                  ディレクトリを指す
綴り:  /tmp/x/L/daemon.sock

/tmp/x/L  →  /very/deep/.../dir/daemon.sock      ファイルを指す
綴り:  /tmp/x/L
```

短い場所に symlink を置き、それを通して綴ります。

ディレクトリを指す symlink は、どの OS でも使えます。届くファイル名は、sockaddr に入る長さから置き場の綴りと symlink の名前の分を引いた長さです。綴りで unlink すると途中の symlink を辿って元のファイルが消え、元のパスで unlink するのと同じに働きます。

ファイルを指す symlink:

- connect は最後の要素の symlink をいつも辿るので、どの OS でも使えます
- bind が最後の要素の symlink を辿るかは OS で違います。実測で辿るのは macOS と NetBSD、辿らないのは Linux・FreeBSD・OpenBSD です。辿らない OS では `EADDRINUSE` で失敗し、元のパスには何もできません
- 綴りにファイル名が出ないので、ファイル名の長さによらず届きます (元のパス全体は PATH_MAX まで)
- 綴りで unlink すると symlink が消えるだけで、ソケットのファイルは残ります

どちらも:

- 長所: 書き込める短い場所があれば、スレッドも `/proc` も要りません
- 短所: 置き場に書く必要があり、物が残ります。置き場を他人が書けると、symlink を差し替えられます。綴りが元のパスと同じ所を指すのは、symlink がある間だけです

### `bindat` / `connectat`

```
fd = open("/very/deep/.../dir", O_RDONLY | O_DIRECTORY)
connectat(fd, sock, <"daemon.sock" の sockaddr>, len)
```

ディレクトリの fd を渡し、相対の綴りをそのディレクトリから引かせます。`openat` の bind / connect 版です。

- 使える OS: FreeBSD
- 届く長さ: ファイル名 103 バイトまで
- 長所: 書き込みもスレッドも要りません
- 短所: FreeBSD にしかありません。bind では、カーネルが覚える綴りがファイル名だけになります

### Apple の広げた sockaddr

```
sun_len とアドレス長を「2 + パスの長さ」にした sockaddr に、253 バイトまでのパスを入れて渡す
```

Apple の OS のカーネルは、`sun_path` の宣言 (104 バイト) より長いアドレスを受け付けます。

- 使える OS: Apple の OS
- 届く長さ: パス全体 (か相対パス) が 253 バイトまで
- 長所: 何も作らず、元のパスをそのまま渡せます。Node.js は macOS で libuv 1.53 以上の時、104〜253 バイトのパスをこの形で bind / connect します
- 短所: この形で bind したソケットのアドレスは途中で切れ、読む側が壊れます。CPython の `getsockname` は後ろに無関係なバイトを付けて返し、asyncio の後始末が落ちます。Go の `net.FileConn` は相手の `RemoteAddr` が nil になり、`.String()` が panic します

### 比較

| 手法 | 綴りの例 | 使える OS | 届く長さ (Linux / macOS) | 要る物 |
|---|---|---|---|---|
| プロセスの chdir | `daemon.sock` | 全部 | ファイル名 107 / 103 | プロセスの cwd を変えてよいこと |
| スレッドの cwd | `daemon.sock` | Linux / Android<br>Apple の OS | ファイル名 107 / 103 | スレッド<br>Linux は seccomp の filter が無いこと |
| fork した子 | `daemon.sock` | 全部 | ファイル名 107 / 103 | fork してよいこと |
| 相対パス | `a/…/daemon.sock` | 全部 | 相対パス全体 107 / 103 | cwd がソケットに近いこと |
| `/proc/self/fd` | `/proc/self/fd/7/daemon.sock` | Linux / Android | ファイル名およそ 90 / — | `/proc` |
| ディレクトリを指す symlink | `/tmp/x/L/daemon.sock` | 全部 | 置き場の綴りの長さしだい | 書ける短い置き場 |
| ファイルを指す symlink | `/tmp/x/L` | connect は全部<br>bind は macOS・NetBSD | ファイル名によらない | 書ける短い置き場 |
| `bindat` / `connectat` | fd + `daemon.sock` | FreeBSD | — / — (FreeBSD でファイル名 103) | — |
| 広げた sockaddr | 元のパス | Apple の OS | — / パス全体 253 | — |

## bind と connect で事情が違う

### bind の綴りはカーネルに残る

```
fd = open("/very/deep/.../dir", O_PATH | O_DIRECTORY)     → 7
bind(sock, "/proc/self/fd/7/daemon.sock")
close(fd)
getsockname(sock)                                          → "/proc/self/fd/7/daemon.sock"
```

カーネルは bind に渡された綴りを覚え、`getsockname` (と、そこへ connect した相手の `getpeername`) で返します。この綴りは後で使われます。

- 上のライブラリが、返ってきた綴りで unlink / stat します (Python の asyncio の後始末、Go の `UnixListener.Close`)。利用者の `remove_file(local_addr)` も同じです
- DGRAM の受け手は、送り元の綴りへ返信します
- `ss -x`・`lsof`・`/proc/net/unix` 等の運用の道具が、その綴りを見せます

綴りは後で、別の文脈で解決し直されます。そこで無関係なファイルに当たる綴りは、bind に使えません。

| bind の綴り | 後で解決すると |
|---|---|
| `/proc/self/fd/<n>/<ファイル名>` | 閉じた fd の番号が使い回され、別のディレクトリの同名ファイルに当たる (sockat-rs が docker で実測し、無関係なファイルが消えた) |
| ファイル名だけ (cwd を移す系、`bindat`) | プロセスの cwd にある同名ファイルに当たる (sockat-py が macOS で実測) |
| cwd からの相対パス | cwd が変わると別の場所に当たる |
| 広げた sockaddr | アドレスが途中で切れ、読む側が壊れる |

消すのは利用者のコードでなく上のライブラリなので、利用者には避けようがありません。実際に使われている例もあります。Bun の標準ライブラリは長いパスの bind で、Linux では `/proc/self/fd/<fd>/<ファイル名>` で bind した後に fd を閉じ、macOS ではファイル名だけで bind します。crun と conmon も、後で閉じる fd の `/proc/self/fd/<fd>/<名前>` で bind しています。

逆に、乱数の名前の symlink を通して bind し、呼び出しの中ですぐ消す形もあります。後で無関係なファイルには当たりませんが、綴りがどこにも届かなくなるので、`getsockname` の綴りで消すライブラリ、DGRAM の返信、運用の道具が元のパスに届きません。長いパスに bind した DGRAM の送り元に返信が届かないことは、実測で確かめています。

bind の綴りに求めることは 2 つです。

1. ソケットが生きている間は、元のパスと同じ所を指し続ける
2. 後でどう解決されても、無関係なファイルに当たらない

### connect の綴りは相手に残らない

connect した側のソケットは bind されないので、connect に使った綴りは相手に残りません。届いた後に、使った symlink を消しても、ディレクトリの fd を閉じても、cwd を戻しても、接続はそのままです。DGRAM も connect した時点で宛先が固まり、その後の `send` は届きます。

そのため connect は、bind の 2 つの条件を気にせず、使われ方に合わせて手法を選べます。connect は CLI や制御の問い合わせで、必要な時に都度行われます。短命で数の多いプロセスが、書き込める場所の無い sandbox から呼ぶこともあります。だから connect では、手数が少ないことと、書き込みもスレッドも要らないことを優先します。

- 相対パスの connect は、connect の後に cwd を確かめ、変わっていれば結果を捨ててエラーにします。別の所に届いたまま返すことはありません

## sockat が選んだ形

### 置き場 B と、その中の D・E

sockat は symlink の手法を、bind の 2 つの条件を満たす形で置きます。中心になるのは次の 3 つです。

```
/tmp/sockat-1000/                    B  利用者ごとの置き場。プロセスをまたいで使い回す
/tmp/sockat-1000/k3J9xQ2mZa/         D  プロセスごとのディレクトリ。名前は乱数 10 文字
/tmp/sockat-1000/k3J9xQ2mZa/0        E  symlink。ソケットのディレクトリかファイルを指す
```

綴りの例:

```
/tmp/sockat-1000/k3J9xQ2mZa/0/daemon.sock     E がソケットのディレクトリを指す
/tmp/sockat-1000/k3J9xQ2mZa/1                 E がソケットのファイルを指す
/proc/4242/fd/5/k3J9xQ2mZa/0/daemon.sock      Linux。B をプロセスの fd で綴る
```

- **B**: 一時ディレクトリの中に作る実在のディレクトリです。名前は `sockat-<uid>` (`$XDG_RUNTIME_DIR` の下は `sockat`) です。1 つのプロセスが使う B は、普段は 1 つです
- **D**: B の中に (プロセス, B) ごとに 1 つ作るディレクトリです。プロセスは D の fd に flock (共有ロック) を掛けて持ち続けます
- **E**: D の中の symlink です。綴りに残す E の名前はプロセスの中のカウンタ (36 進) で、D がプロセスごとに一意なので短くて済みます。すぐ消す E (thread-cwd・at と既定の connect の物) の名前は乱数 10 文字です

Linux で `/proc` を使える時は、B を `/proc/<pid>/fd/<B の fd>` で綴る形 (procB) を先に試します (別の uid の相手に辿らせる指定 `usable_cross_uid` の時は使いません)。procB の綴りは同じ uid のプロセスだけが辿れ、プロセスが終われば辿れなくなります。`/tmp` を通らないので、相手が systemd の `PrivateTmp` で `/tmp` を隔離していても辿れます。

前の節の手法と、sockat の中での名前の対応です。名前は `_ex` 系の診断 (`route`・`skipped`) に出ます。

| 手法 | sockat の中での名前 | 使う操作 |
|---|---|---|
| 元のパスをそのまま標準ライブラリに渡す | `standard` | bind、connect |
| ディレクトリを指す symlink (B・D・E を通す) | `link-dir` | bind |
| ファイルを指す symlink (B・D・E を通す) | `link-file` | bind、connect |
| スレッドの cwd (D と、すぐ消す E を通す) | `thread-cwd` | bind |
| `bindat` (D と、すぐ消す E を通す) | `at` | bind |
| スレッドの cwd (ソケットのディレクトリへ直接) | `thread-cwd-direct` | connect |
| `connectat` | `at-direct` | connect |
| `/proc/self/fd` | `proc-direct` | connect |
| cwd からの相対パス | `relative` | connect |
| 広げた sockaddr | `widened` | connect |
| プロセスの chdir、fork した子 | 無し (使わない) | |

### bind の順

| 順 | 経路 | 綴り | 使う時 |
|---|---|---|---|
| 1 | `standard` | 元のパス | 標準ライブラリに渡す長さ以下 |
| 2 | `link-dir` | `/proc/<pid>/fd/<B の fd>/D/E/<ファイル名>` | Linux で `/proc` を使えて収まる |
| 3 | `link-dir` | `<B の実パス>/D/E/<ファイル名>` | 収まる |
| 4 | `link-file` | `<B の実パス>/D/E` | bind が symlink を辿る OS |
| 5 | `thread-cwd` (FreeBSD は `at`) | `E/<ファイル名>` (E はすぐ消す) | Linux / Android、Apple の OS、FreeBSD |
| 6 | `ENAMETOOLONG` | | |

- 2〜4 は綴りを残します。ソケットが生きている間は綴りが元のパスと同じ所を指すので、`getsockname` の綴りで消すライブラリ、DGRAM の返信、運用の道具が元のパスと同じに働きます
- link-dir を link-file より先にします。link-dir の綴りで unlink すると E を辿って元のファイルが消え (元のパスと同じ働き)、運用の道具にもファイル名が見えます。link-file の綴りで unlink すると E が消えるだけでソケットのファイルは残り、綴りにファイル名も出ません
- link-file はファイル名の長さによらず届くので、macOS と NetBSD の bind はファイル名の上限 (NAME_MAX、255 バイト) まで届きます。辿らないと実測した OS では試しません。辿るかを実測していない OS では試してみて、失敗した時に元のパスに物が無ければ「辿らなかった」とみなして次へ進みます
- thread-cwd・at は、2〜4 の綴りが収まらない時の後ろです。E を bind の直後に消すので、綴りはどこにも届きません。綴りの中に消した乱数の名前があるので、後で解決しても、cwd に同じ名前の物がたまたまある以外は当たりません
- bind は proc-direct・relative・at-direct・widened を使いません ([bind の綴りはカーネルに残る](#bind-の綴りはカーネルに残る) の表の理由)
- 綴りを後で使えるかは、`bind_ex` と `resolve_for_bind` が返す `Spelling` で分かります (元の綴り、cwd からの相対、B・D・E を通る、どこにも届かない、の 4 種類)

### connect の順

| 順 | 経路 | 中身 |
|---|---|---|
| 1 | `standard` | 元のパス |
| 2 | Linux: `proc-direct` (`/proc` を使えなければ `relative`)<br>Apple の OS: `relative` → `widened`<br>FreeBSD: `at-direct`<br>NetBSD・OpenBSD: `relative` | 書き込みもスレッドも要らない |
| 3 | `thread-cwd-direct` | 使い捨てのスレッドの cwd をソケットのディレクトリに移し、ファイル名で connect する (Linux / Android、Apple の OS) |
| 4 | `link-file` | B の直下に乱数 10 文字の E を作って `<B の実パス>/<E>` で connect し、すぐ E を消す |
| 5 | `ENAMETOOLONG` | |

- 書き込みもスレッドも要らない経路を先にします。CLI の 1 回だけの connect は普通ここで終わり、置き場に書けない sandbox でも届きます。relative と widened は、置き場を通す経路より遠くまで届く場面があります
- thread-cwd-direct は D も E も要りません。connect の綴りは相手に残らないので、bind と違って乱数の名前を挟む必要がありません
- link-file はファイル名の長さによらず届く最後の経路です。D を作らず B の直下に E を作り、connect の直後に消すので、プロセスの中に D も E も残りません (B を初めて作った時は、その B を以後もプロセスの B として使います)
- 同じパスへ何度も connect するなら、`resolve_for_connect` で 1 度作った綴りを使い回し、最後に `cleanup` します

普段の環境 (スレッドの cwd と `/proc` を使え、置き場が OS の既定のまま書ける) で届くファイル名の長さです。Rust・Python・Go の実装の値で、TypeScript の実装は一部短くなります (届く範囲の表)。

| OS | bind | connect |
|---|---|---|
| Linux | 96 バイトまで (77 以上は thread-cwd) | 255 バイトまで |
| macOS | 255 バイトまで | 255 バイトまで |
| FreeBSD | 92 バイトまで (at) | 255 バイトまで |
| NetBSD | 255 バイトまで | 255 バイトまで |
| OpenBSD | 72 バイトまで | 255 バイトまで |

### 置き場をどこに作るか

B は次の順で、最初に作れた所に作ります。OS の掃除で死んだ D が消え、生きている D が守られる所を先にしています。

| 順 | 置き場 | 理由 |
|---|---|---|
| 1 | `/tmp` | Linux は systemd-tmpfiles が死んだ D を 10 日で消し、生きている D は flock で守られる。macOS は生きている D を消さない |
| 2 | `$XDG_RUNTIME_DIR` | age の掃除が無く、死んだ D がログアウトまで残る |
| 3 | `$TMPDIR` | macOS の `$TMPDIR` は dirhelper が生きている D も 3 日で消しうる |
| 4 | ソケットのディレクトリ | 1〜3 のどこにも作れない時。名前は `.sockat.<乱数 10 文字>` |

- B を使う前に、実ディレクトリであること、持ち主が自分であること、他人 (group を含む) が書けないことを確かめます。ルートから B の親までの途中も、持ち主が root か自分で、他人が書けないか sticky であることを確かめます。祖先を他人が書けると、親ごと付け替えられるためです
- 他人が `/tmp/sockat-<uid>` を先に作っていて確かめに外れたら、その置き場は使わずに次の置き場へ進みます。代わりの名前の B は作らないので、置き場に物が増えません
- B と D は 0711 で作ります。`/tmp` の B の実パスの綴りは、別の uid の相手も辿れます。`$XDG_RUNTIME_DIR` と macOS の `$TMPDIR` は 0700 なので、そこにある B は同じ uid だけです
- 置き場を自分で決めたいアプリは、`Options.base` で B のパスを渡せます

### 消さずに残し、flock で守る

B・D・E は、ソケットを使っている間は消しません。bind の綴りはカーネルがソケットの寿命の間覚えるので、綴りが辿れ続けることが、正しく動く条件になるからです。

残しても後で無関係なファイルに当たらないように、次のようにしています。

- D の名前は乱数です。カウンタにすると、プロセスが終わった後に同じ PID・同じ fd 番号の別のプロセスが現れた時、同じ綴りがそのプロセスのソケットを指してしまいます
- D が生きている間は flock で守られ、B と D が 0711 なので、綴りが後で無関係なファイルに当たりません。procB の綴りはプロセスが終われば辿れなくなり、実パスの綴りは D が消えるまで同じ所を指します
- 持っている B・D が消されていたら、次の呼び出しで作り直します。外した B・D の fd は閉じずに持ち続けます。閉じると fd の番号が使い回され、その番号を通る procB の綴りが別のディレクトリに当たるためです

flock は OS の掃除からも D を守ります。systemd-tmpfiles (v242 以上) は、flock の掛かったディレクトリを配下ごと掃除から外します。生きている D が消されうるのは、systemd v242 より古い Linux (RHEL 8 の v239 等) と、B が macOS の `$TMPDIR` にある時です。その時も綴りが辿れなくなるだけで、危険はありません。

### 片付けは OS の掃除と、明示の `sweep` に任せる

sockat は B と D を自分では片付けません。死んだプロセスの D は、OS の一時ディレクトリの掃除で消えます。Linux の `/tmp` は 10 日、`$XDG_RUNTIME_DIR` は最終ログアウトか再起動、macOS の `/tmp` は symlink の入ったディレクトリを消さないので再起動までです。FreeBSD・NetBSD・OpenBSD の既定では、消えないか再起動で消えます。

- 残る物は小さいです。sockat を使う 2 つのアプリの実測では、試験 1 回分の D 12・E 150 が `du` で 0 でした。溜まるのは D (長いパスで bind したプロセスの数) より E (bind した回数) です
- `sweep()` を呼んだ時だけ、ロックの外れた D (持ち主の死んだ D) を消します。生きているプロセスの D は消しません。実測では D 292・E 3035 が 0 になり、B は残りました
- 試験を何度も回す環境では、利用者が `sweep()` を呼びます。macOS の `/tmp` は再起動まで溜まり続けるためです

自動で消さない理由:

- `/tmp` に利用者ごとの socket や一時物を置く道具 (ssh-agent、tmux 等) は、他人の残骸を消さず OS の掃除に任せるのが通例です。次のプロセスが片付ける形は、容量が増え続けるキャッシュ (Go のビルドキャッシュ等) の物で、容量がほぼ 0 の D・E には当たりません
- 呼び出しのたびに B の中を一覧すると、resolve と connect の手数と IO が増えます
- D の生死を flock で見分けるので、PID を名前に入れて生死を推し量る仕組みが要りません

### この形の弱み

- 状態がアプリの置き場の外 (`/tmp`・`$XDG_RUNTIME_DIR`・`$TMPDIR`) に増えます。既定の `bind` の E と死んだプロセスの D は、OS の掃除まで残ります
- 他人が `/tmp/sockat-<uid>` を先に作ると、次の置き場に移ります。macOS では長い `$TMPDIR` に移るので、届く長さが縮みます
- `/tmp` の B は、消えた後に他人が同じ名前で作り直せます。片付けた後の綴りは使いません
- procB の綴りは `/proc/<pid>/fd/<fd>/` と D・E の分だけ長く、Linux で届くファイル名は thread-cwd より短くなります
- exec をまたぐと D の flock の fd が閉じ、引き継いだ listener が生きていても D・E が `sweep()` や OS の掃除で消されることがあります (綴りが辿れなくなるだけです)。procB の綴りは exec の時点で辿れなくなります
- thread-cwd・at の途中でプロセスが死ぬと、E が D に残ります (D と一緒に OS の掃除で消えます)

## 採らなかった物

| 案 | 採らなかった理由 |
|---|---|
| fork した子で bind / connect する | 副作用 (fd の複製、`SIGCHLD`、`pthread_atfork`、他のスレッドの `waitpid(-1)`、connect では相手に見える pid) がプロセス全体に及び、望まない利用者の方が多い。bind の listen を親がすれば相手に見える副作用は消えるが、見えない副作用は残る。thread-cwd-direct と link-file の後に置くと、出番はスレッドも B も使えない環境だけになる |
| bind で広げた sockaddr を使う | アドレスが途中で切れ、CPython と Go の標準ライブラリを壊す |
| bind の綴りに乱数の名前を挟まない (`/proc/self/fd/<fd>/<ファイル名>`、ファイル名だけ) | 後で解決すると無関係なファイルに当たる。消すのは上のライブラリで、利用者が避けられない |
| bind の綴りを呼び出しの中で片付ける | `getsockname` の綴りで消すライブラリ、DGRAM の返信、運用の道具が元のパスに届かない |
| B を開いて fd で掴んだ後に消し、`/proc` の fd だけで使う (置き場に何も残さない) | 消したディレクトリの中には作れない (`ENOENT`、実測) |
| 名前に PID を入れ、次のプロセスが残骸を掃除する | exec をまたいで listener を引き継ぐプロセスは PID が変わらず、消されない。PID の使い回しで、生きている他人の物を消さない確かめ方が要る |
| プロセスが初めて B を使う時や、呼び出しのたびに掃除する | 手数が増える。`/tmp` の一時物は OS の掃除に任せるのが通例 |
| 終了時に自分の D を消す exit ハンドラを登録する | ライブラリが黙ってプロセス全体の終了の振る舞いを変える (fork した子でも走る)。Go には仕組みが無く、言語でそろわない。クラッシュ・kill・exec では走らない |
| 占拠された B の代わりに、乱数の名前の B を作る | 長いパスを使うプロセスごとに B が増え、`sweep` でも OS の掃除でも消えないことがある |
| 既定の connect が綴りをキャッシュして使い回す | プロセスの中に隠れた状態ができ、いつ片付くかが見えず、長命のプロセスでは宛先の数だけ symlink が溜まる。使い回したい人は `resolve_for_connect` を使う |
| ライブラリの API に、経路を利用者が選ぶ・組み合わせる口や、プロセス全体の既定を変える関数を置く | 下手な組み合わせで中途半端な使い方をされるだけで、意味が無い。プロセス全体の既定は隠れた状態になる |
| 経路の名前を約束として返す | 経路の追加や変更が破壊的な変更になる。分岐には `Spelling` を使う |

## 先へ

- 条件ごとにどこまで届くか: [届く範囲の表](./reach/README-ja.md)
- fork を自分のアプリで使う時: [fork-cwd](./fork-cwd-ja.md)
- 各経路の作り方 (実装する人向け): [SPEC-routes](../docs/SPEC-routes-ja.md)
- 約束の正本: [仕様](../docs/SPEC-ja.md)
- 判断の記録: [docs/decisions](../docs/decisions/INDEX.md)
