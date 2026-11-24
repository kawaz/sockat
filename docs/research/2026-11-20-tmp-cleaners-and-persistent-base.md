# OS の一時ディレクトリの自動掃除と、消さない置き場 B (2026-11-20 調査)

## 目的

[issue: resolve と消さない置き場 B](../issue/archive/2026-11-20-resolve-and-persistent-base.md) の案 (利用者ごとの置き場 B をプロセスをまたいで使い回し、中のディレクトリ D と symlink をソケットの寿命の間残す) に対して、OS の一時ディレクトリの自動掃除が使用中の B・D・symlink を消すかを調べた。

- 「確」は上流のソース・公式文書・手元のファイルや実験で確かめたもの。「推測」は読みからの推論。「未確認」は確かめていないもの
- BSD・illumos は上流の既定を読んだだけで、実機の確認ではない

## Linux (systemd-tmpfiles と /run/user)

### /tmp・/var/tmp (確、上流の既定。ディストリや管理者の設定で変わる)

| 項目 | 内容 |
|---|---|
| 既定の age | `q /tmp 1777 root root 10d`、`q /var/tmp 1777 root root 30d` ([tmp.conf](https://github.com/systemd/systemd/blob/main/tmpfiles.d/tmp.conf)) |
| 参照 | [tmpfiles.d(5)](https://www.freedesktop.org/software/systemd/man/latest/tmpfiles.d.html)、systemd-tmpfiles(8) |
| age の判定 | 既定は `abcmABM` (ファイルは atime・birth・ctime・mtime、ディレクトリは atime・birth・mtime)。どれかが新しければ消さない |
| 再帰 | ディレクトリの古い子も対象。親 B の時刻を触っても、古い D や symlink は守れない |
| 親の sticky bit | 配下を age 掃除から守らない |
| 除外 | `x /tmp/sockat-<uid>` で配下ごと除外 (管理者の設定が要る)。`X` はそのディレクトリ自身だけ |
| flock による保護 | 降りる前に BSD flock(2) の非ブロッキング排他ロックを試し、既に LOCK_SH / LOCK_EX が掛かっていれば配下ごと飛ばす。ディレクトリは systemd v242 ([52b32b2aac](https://github.com/systemd/systemd/commit/52b32b2aac96562ae8c380d8869b667f806471e0))、個々のファイルの確認は v254 ([65e179a1e7](https://github.com/systemd/systemd/commit/65e179a1e7021ab655c07dc392d5dd6fba2d2acb))。fcntl のロックは別物で、flock が要る |
| 生きているソケットの保護 | src/tmpfiles/tmpfiles.c が `S_ISSOCK && unix_socket_alive` (/proc/net/unix の絶対パスの文字列) で飛ばす。B・D・symlink はソケットでないのでこの保護を受けない |

### /run/user/<uid> (確)

- systemd.conf.in は `d /run/user 0755 root root -` (age なし)
- /run/user/<uid> は最終ログアウトで中身ごと消える (pam_systemd(8)、systemd-user-runtime-dir(8))。`loginctl enable-linger` で user manager が残る
- 再起動で消える (tmpfs)

## macOS (tmp_cleaner と dirhelper)

手元の macOS 26.5.2 のファイルを読んだ結果。

- /etc/defaults/periodic.conf、/etc/periodic/daily/、/etc/periodic.conf は無い (古い macOS の periodic.conf(5) と混同しない)
- /tmp (= /private/tmp): /usr/libexec/tmp_cleaner が launchd の com.apple.tmp_cleaner.plist で毎日 0 時に動く
  - `find -dx . -fstype local -type f -atime +3 -mtime +3 -ctime +3 -delete` (通常のファイル)
  - `find ... -type d -empty -mtime +3 -delete` (空のディレクトリだけ)
  - .X11-unix 等は名前で除外
  - symlink とソケットはどちらにも当たらない。symlink が残る D と B は空でないので消えない
- 手元の実験: $TMPDIR の下の `mktemp -d` に通常のファイル・symlink・AF_UNIX のソケット・D を作り、atime / mtime を 7 日古くして同じ find の式を流した。ctime が今なので通常のファイルも消えず、symlink・ソケット・空でない D は残った
- $TMPDIR (/var/folders/.../T/): /usr/libexec/dirhelper (com.apple.bsd.dirhelper.plist、03:35、CLEAN_FILES_OLDER_THAN_DAYS=3) が管理
  - バイナリの逆アセンブルで /var/folders/ を歩いて古いものを消す関数があることは確認した
  - 種類ごとの扱い・使う時刻は未確認。$TMPDIR の symlink が 3 日後も残るとは言えない

## BSD と illumos (上流の既定、実機の確認ではない)

| OS | 掃除 | B / D / symlink への影響 |
|---|---|---|
| FreeBSD | `clear_tmp_enable="NO"` ([rc.conf](https://cgit.freebsd.org/src/plain/etc/defaults/rc.conf))、`daily_clean_tmps_enable="NO"` ([periodic.conf](https://cgit.freebsd.org/src/plain/usr.sbin/periodic/periodic.conf)) | 既定は消えない。有効にすると 110.clean-tmps が通常のファイル (atime・mtime・ctime が +3) と空のディレクトリ (mtime +3) を消す。symlink・ソケットは対象外 |
| NetBSD | `clear_tmp=YES` が既定で起動時に消す ([rc.conf](https://cdn.netbsd.org/pub/NetBSD/NetBSD-current/src/etc/defaults/rc.conf)、rc.d/cleartmp)。/etc/daily の /tmp の掃除はコメントアウト (symlink の競合攻撃のため有効にしないとコメント) | 再起動で消える |
| OpenBSD | /etc/rc が起動時に /tmp を消す。/etc/daily が通常のファイル (`-atime +7`) と古い空のディレクトリ (`-mtime +1`) を毎日消す。tmux-*・ssh-*・.X11-unix・.ICE-unix は除外 ([daily](https://cvsweb.openbsd.org/checkout/src/etc/daily?rev=HEAD)) | 再起動で消える。日次は symlink を消さない |
| illumos | /tmp は tmpfs で再起動で消える。日次の掃除は無い ([rmtmpfiles](https://raw.githubusercontent.com/illumos/illumos-gate/master/usr/src/cmd/svc/milestone/rmtmpfiles) 等) | 再起動で消える |

## 先例 (tmux、ssh-agent、X11、Emacs、GnuPG)

| 先例 | 置き場と確認 | 掃除への備え |
|---|---|---|
| tmux ([tmux.c](https://github.com/tmux/tmux/blob/master/tmux.c)) | `mkdir("/tmp/tmux-<uid>", 0700)`。既にあれば lstat で実ディレクトリ・持ち主が uid・other の権限なし、を確かめる | 定期的な時刻の更新やロックは無い。ソケットが消えたら SIGUSR1 で作り直せる |
| ssh-agent | 既定は ~/.ssh/agent、`-T` で `mkdtemp("/tmp/ssh-XXXXXXXXXXXX")` | /tmp の永続の置き場の先例ではない |
| X11 | libxtrans が /tmp/.X11-unix を lstat で確かめる | systemd の x11.conf が `D /tmp/.X11-unix 1777 root root 1h` 等。root が管理する共有の置き場 |
| Emacs (server.el) | $XDG_RUNTIME_DIR/emacs、無ければ `${TMPDIR:-/tmp}/emacs<uid>`。実ディレクトリ・uid 一致・group/other の権限なしを確かめる。emacsclient.c は `open(O_DIRECTORY\|O_NOFOLLOW)` → fstat で確かめ直す | 特になし |
| GnuPG (common/homedir.c) | /run/gnupg/user/<uid>、/run/user/<uid>/gnupg。種類・持ち主・他人の権限を確かめる (stat で symlink を辿る) | /run 系の置き場に頼る |

## 設計への含意

| 掃除 | B / D / symlink | 避ける手段 | 費用・限界 |
|---|---|---|---|
| Linux /tmp・/var/tmp の systemd の age | 古ければ全部消える対象。親を触っても子は守れない | 生きているプロセスが D に flock (LOCK_SH) を掛け続ける (systemd v242 以上)。管理者の `x` の設定 | flock はプロセスごとに fd 1 つ |
| Linux /run/user/<uid> | ログアウトで丸ごと消える | linger の運用に限る | 再起動を越えない |
| macOS /tmp (tmp_cleaner) | symlink が入った D は空でないので消えない | 不要 | 死んだプロセスの D も消えない (再起動まで) |
| macOS $TMPDIR (dirhelper) | 3 日で消えうる。種類ごとの扱いは未確認 | 長命の daemon の置き場にしない | |
| FreeBSD の既定 | 消えない | 不要 | |
| NetBSD・OpenBSD・illumos | 再起動で消える (日次は symlink を消さない) | 不要 | 再起動を越えない |

- ソケットが生きているかと、B・D・symlink の寿命は別

## 未確認

- Docker での実験はしていない (debian:stable-slim に systemd-tmpfiles が無い)
- symlink の age 掃除の実機の再現は無い
- macOS の dirhelper が $TMPDIR の symlink・ソケット・ディレクトリをどう扱い、どの時刻を使うか
- BSD・illumos は上流の既定を読んだだけで、実機では確かめていない
