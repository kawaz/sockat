# 外部レビュー (Gemini 4 Carbon、agy、2026-11-21)

対象はハブ main (899c31eb 前後) と 4 言語の main。読み取りのみのレビューの出力をそのまま置く。各指摘の採否と対応は統括と各言語のセッションが実物で確かめて決める (このファイルの指摘は未確認の主張)。

ハブ（`kawaz/sockat`）の仕様・文書・適合試験・届く範囲のモデルと、4 言語の実装（`sockat-rs`・`sockat-py`・`sockat-go`・`sockat-ts`）を読み取りのみで突き合わせました。以下に観点別・優先度順で報告します。

---

## 1. 仕様の正しさと安全性

### 1-1. 消された B・D を外す際に fd を閉じると、fd 番号の使い回しで無関係なファイルの削除・別ディレクトリへの接続が起きる（仕様の記載漏れ ＋ Rust・Python の実装の穴）
- **優先度**: 高
- **どこ**:
  - ハブ: [SPEC-routes-ja.md](../../docs/SPEC-routes-ja.md#L46)（「実体の置き場」）、[SPEC-ja.md](../../docs/SPEC-ja.md#L262)（「置き場に残る物」）、[faq-ja.md](../../pages/faq-ja.md#L89-L91)（「後始末」）
  - Rust: [base.rs](https://github.com/kawaz/sockat-rs/blob/main/src/base.rs#L538-L545) (`Registry::find`)、[base.rs](https://github.com/kawaz/sockat-rs/blob/main/src/base.rs#L603-L611) (`held_in`)、[base.rs](https://github.com/kawaz/sockat-rs/blob/main/src/base.rs#L946-L955) (`Link`)
  - Python: [_place.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_place.py#L354-L374) (`Dir.unlink_or_raise`, `Dir.unlink`, `Dir.close`)、[_place.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_place.py#L461-L467) (`Base.dir`)、[_place.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_place.py#L489-L495) (`Base.close`)、[_place.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_place.py#L949-L957) (`_alive`)
  - 対比（fd を閉じない実装）: Go [base.go](https://github.com/kawaz/sockat-go/blob/main/base.go#L228-L231)、TypeScript [world.ts](https://github.com/kawaz/sockat-ts/blob/main/src/world.ts#L276-L280)
- **根拠**:
  - `SPEC-routes-ja.md` L46: `持っている B・D が消されていたら (B・D の fd の fstat の st_nlink が 0、または名前の lstat と fd の (st_dev, st_ino) が違う)、次の呼び出しで外して作り直す`（外した fd を閉じない規定が無い）
  - `SPEC-ja.md` L262: `生きている D が消された時は、綴りが辿れなくなるだけで危険はない` / `faq-ja.md` L89-91: `/tmp/sockat-<uid> の中身は消してよい?` → `よい。`
  - Python `_place.py` L954-956: `if b.gone(): b.close(); return None` / L494: `os.close(self.fd)`
  - Rust `base.rs` L608-609: `slots[slot] = None; lock(&REGISTRY).all.retain(|r| !Arc::ptr_eq(r, &b));`（`Link` は `Arc<Dir>` を持つが `Dir` は `Arc<Base>` を持たないため、`Arc<Base>` が Drop され `fd: OwnedFd` が close される）
- **何が起きるか**:
  1. Linux で `link-dir` (`procB`) により bind したソケットのカーネル上の綴りは `/proc/<pid>/fd/<B の fd>/<D>/<E>/<ファイル名>`（`removable: true`）になる。`/tmp/sockat-<uid>` が消された後に同プロセスで次の sockat 呼び出しが走ると、Rust と Python は `<B の fd>` を close する。直後に開かれた別ディレクトリ（新しい B を作るために開く `/tmp` やアプリの作業ディレクトリ等）に同じ fd 番号が割り当てられると、生きているソケットの綴りがその別ディレクトリ基準で再び解決される。`/proc/net/unix` 等で `<D>/<E>` 名を見た他ユーザが `/tmp/<D>/<E>` に symlink を置けば、その綴りでの `unlink` や DGRAM 返信が無関係なファイルに当たる。
  2. さらに Python の `Dir.unlink_or_raise` / `Dir.unlink` はロック無しで `if self.closed: return` → `os.unlink(name, dir_fd=self.fd)` を呼ぶため、別スレッドが `b.close()` した瞬間に再利用された別ディレクトリの fd に対して `unlinkat` を実行する競合窓がある。
- **直し方の案**: `SPEC-routes-ja.md`「実体の置き場」に「外した B・D の fd 番号が他のディレクトリに使い回されないようにする（閉じずに保持するか、`/dev/null` 等へ `dup2` して番号を塞ぐ）」と明記し、Rust・Python も Go・TS に揃える（Python の fork 子プロセス `_after_fork_in_child` でのみ閉じる）。

### 1-2. `sockat-ts`: `/proc` の無い OS（macOS・BSD）で B・D が消された後、`cleanup()` / `remove()` が実パス文字列で `unlink` するため、`/tmp` の symlink すり替えで自分の無関係なファイルを消しうる
- **優先度**: 高
- **どこ**: [world.ts](https://github.com/kawaz/sockat-ts/blob/main/src/world.ts#L100-L113) (`dHeld`, `linkEntry`, `removeLink`)、[fsx.ts](https://github.com/kawaz/sockat-ts/blob/main/src/fsx.ts#L175-L177) (`entry`)、[connect.ts](https://github.com/kawaz/sockat-ts/blob/main/src/connect.ts#L281-L293) (`connectSteps` の `link-file`)
- **根拠**:
  - `world.ts` L110-112: `export function removeLink(e: Link): Result<void> { const r = attempt(() => fs.unlinkSync(linkEntry(e))); ... }`
  - `fsx.ts` L176: `return dir.at !== null ? `${dir.at}/${name}` : joinUnder(dir.real, name);`
- **何が起きるか**: native 抜きの `sockat-ts` は、`/proc` の無い macOS・BSD（および `/proc` 無し Linux）では `e.d.at === null` となり、実パス文字列 `"/private/tmp/sockat-<uid>/<D>/<E>"` に `fs.unlinkSync` を呼ぶ。`SocketFile` / `ForBind` / `ForConnect` の保持中に `/tmp/sockat-<uid>` が消された場合、sticky な `/tmp` (`1777`) では別の uid の攻撃者が（`netstat -f unix` 等で見える `<D>` 名を使い）`/tmp/sockat-<uid>/<D>` を被害者のディレクトリ（例: `/Users/<victim>/work`）への symlink として先に作れる。その後被害者プロセスが `cleanup()` / `remove()` を呼ぶと、元の B・D が生きているか確かめずに `fs.unlinkSync` を呼ぶため、攻撃者の symlink を辿って `/Users/<victim>/work/0` 等の無関係な自分のファイルを消してしまう。既定の非同期 `connect` の `link-file`（`await` を挟んで `fs.unlinkSync(entry(b, name))`）にも同じ窓がある。
- **直し方の案**: `at === null` の時は `fs.unlinkSync` の直前に `dirGone` 相当（`fstat` と `lstat(b.real)`・`lstat(joinUnder(b.real, d.name))` の `(st_dev, st_ino)` が保持中の `b.id`・`d.id` と一致するか）を確かめ、不一致なら元の D/B ごと既に消えているので `unlinkSync` せず成功を返す（sticky な親の下で自分が owner の実ディレクトリであることが確認できれば、他人はその中のエントリを付け替えられない）。

### 1-3. `sockat-ts`: README の推奨コードが SPEC で禁止されている `path.resolve` を使っており、`a/sym/../s.sock` で別のディレクトリに bind / remove する
- **優先度**: 高
- **どこ**: [README-ja.md](https://github.com/kawaz/sockat-ts/blob/main/README-ja.md#L128) と [README-ja.md](https://github.com/kawaz/sockat-ts/blob/main/README-ja.md#L136-L137)（「使ってはいけない書き方」）、仕様 [SPEC-ja.md](../../docs/SPEC-ja.md#L299) と [SPEC-ja.md](../../docs/SPEC-ja.md#L384)
- **根拠**:
  - `SPEC-ja.md` L384: ``bind の前に、cwd を前に付けて絶対パスにする (`..` を字句で畳む関数を使わない。`a/sym/..` が別のディレクトリになる)``
  - `sockat-ts/README-ja.md` L128, L137: ``bind の前に `path.resolve` で絶対パスにする`` / `const b = await bindEx(nodePath.resolve(relative));`
- **何が起きるか**: `node:path.resolve` はファイルシステムを引かずに `..` を字句で消すため、`sym` が別ディレクトリへの symlink である `"a/sym/../s.sock"` を渡すと `<cwd>/a/s.sock` に書き換わり、カーネルが辿る先とは別のディレクトリに bind してしまう。
- **直し方の案**: 実装本体（`route.ts` の `absTarget`）と同じく ``relative.startsWith("/") ? relative : `${process.cwd()}/${relative}` `` に直し、ハブの [langs-ja.md](../../pages/langs-ja.md#L18-L24) にも Python の `os.path.abspath` と同様の注意を追記する。

### 1-4. `sockat-rs`: Linux の `proc-direct` が `(st_dev, st_ino)` 一致を確かめないため、PID 名前空間と `/proc` が食い違う環境で別プロセスのディレクトリへ connect しうる（Python にも一部抜け）
- **優先度**: 高
- **どこ**: Rust [route.rs](https://github.com/kawaz/sockat-rs/blob/main/src/route.rs#L1697-L1733) (`linux::probe`, `linux::fd_dir`, `linux::proc_direct`)、Python [_routes.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_routes.py#L198-L216) と [_routes.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_routes.py#L789-L801)
- **根拠**:
  - Rust `route.rs` L1704-1707: `let fd_dir = proc_self_fd.join(fd.as_raw_fd().to_string()); std::fs::metadata(&fd_dir).ok()?; Some(fd_dir)`（`procB` 用の `base::proc_spelling` L1051-1052 と違い `(dev, ino)` 比較が無い）
- **何が起きるか**: コンテナ等で食い違った `/proc` がマウントされ `/proc/self` が同じ uid の別プロセスを指している場合、その別プロセスが同じ fd 番号で別ディレクトリを開いていると `metadata` が通り、`proc-direct` が無関係なディレクトリの同名ソケットへ connect してしまう。また Python は `proc_usable` で `/` の fd の一致は見るが、`connect_proc_direct` で `cc.dirfd` 自身の一致を見ないため、全 fd が `/` を指すような `/proc` では `/<name>` へ connect する。
- **直し方の案**: Go（[os_linux.go](https://github.com/kawaz/sockat-go/blob/main/os_linux.go#L48-L54)）や TS（[fsx.ts](https://github.com/kawaz/sockat-ts/blob/main/src/fsx.ts#L183-L190)）と同様、`dir_fd` の `fstat` と `stat("/proc/self/fd/<dir_fd>")` の `(st_dev, st_ino)` 一致を必ず確認する。

### 1-5. `sockat-py`: `in_thread_cwd` の `thread.start()` 中に `KeyboardInterrupt` が入ると、スレッド終了前に `dirfd` と `sock` を閉じて無関係なディレクトリに移りうる
- **優先度**: 高
- **どこ**: [_routes.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_routes.py#L509-L523) (`in_thread_cwd`)、仕様 [SPEC-routes-ja.md](../../docs/SPEC-routes-ja.md#L233)（「使い捨てのスレッド」）
- **根拠**:
  - `SPEC-routes-ja.md` L233: `待つのが割り込まれても (Python の KeyboardInterrupt 等)、スレッドが終わるまでは片付けない (先に閉じた fd の番号が使い回されると、スレッドが無関係なディレクトリに移って bind / connect する)`
  - `_routes.py` L510-518: `try: thread.start() except RuntimeError: ...` の後に `while True: try: thread.join()` が置かれている。
- **何が起きるか**: CPython の `Thread.start()` は OS スレッドを起動した**後**に内部の `self._started.wait()` で待つ。この待機中、または `start()` 直後から `try: thread.join()` に入るまでの間（あるいは `except BaseException:` 節の中で 2 回目の `SIGINT` が届いた時）に `KeyboardInterrupt` が発生すると、`join()` せずに抜けて呼び出し元が `sock.close()`・`d.unlink(e)`・`os.close(dirfd)` を進め、走り続けている使い捨てスレッドが再利用された fd に `fchdir` / `bind` / `connect` しうる。
- **直し方の案**: OS スレッド起動後の `_started.wait()` と `join()` 全体を、連続した `BaseException` でも抜けないループで保護する。

### 1-6. `sockat-ts`（および一部 `sockat-go`）: 短い相対パスの `bindEx` で cwd 変更時に `close()` が移動先 cwd の無関係な同名ファイルを `unlink` する ＋ `realFile` を bind の前に引いている
- **優先度**: 高
- **どこ**: TS [drive.ts](https://github.com/kawaz/sockat-ts/blob/main/src/drive.ts#L84-L143) (`beforeBind`, `boundOf`)、[README-ja.md](https://github.com/kawaz/sockat-ts/blob/main/README-ja.md#L67-L68) と [README-ja.md](https://github.com/kawaz/sockat-ts/blob/main/README-ja.md#L188-L189)、Go [bind.go](https://github.com/kawaz/sockat-go/blob/main/bind.go#L399-L433)、ハブ [langs-ja.md](../../pages/langs-ja.md#L22)、仕様 [SPEC-ja.md](../../docs/SPEC-ja.md#L214)
- **根拠**:
  - `SPEC-ja.md` L214: `覚えるのは bind が通った直後 (listener を返す前)。`
  - `drive.ts` L91, L135: `return { relative, cwd: relative ? cwdId() : null, file: realFile(path) };` / `discard();`
- **何が起きるか**:
  1. Node (libuv) / Bun は短い相対パス `"s.sock"` を文字列のまま保持し、close 時にその時点の cwd で `unlink("s.sock")` する。非同期 `bindEx("s.sock")` の完了前に `process.chdir("/other")` が起きると、`boundOf` が cwd 変更を検知して `discard()` (`socket.close()`) を呼んだ瞬間に `/other/s.sock`（移動先の無関係なファイル）を消してしまう。正常終了後も `chdir` 後に `b.socket.close()` すると同じく移動先の同名ファイルを消す（`langs-ja.md` L22 の「元のパスを unlink する」は相対パス＋chdir 時に不正確）。
  2. Go（`bind.go` L399）と TS（`drive.ts` L91）は bind の**前**に `realFile(path)` を呼んでいる（Node は間に非同期 `await` も挟む）。`/tmp/sym/s.sock` で `realFile` と `bind` の間に `sym` が `dirA` → `dirB` に張り替わり `dirA/s.sock` に既存の別ソケットがあると、`dirB/s.sock` に bind したのに `SocketFile` が `dirA/s.sock` を覚え、`remove()` が別ソケットを消す窓が広がる。（また Go の `ForBind.SocketFile()` [resolve.go](https://github.com/kawaz/sockat-go/blob/main/resolve.go#L123-L136) は `realFile` の前だけ `statID(".")` を見て後で見ない。）
- **直し方の案**: Go・TS でも `realFile` は bind 直後に呼ぶ（Rust・Python と揃える）。TS の README と `langs-ja.md` L22 には「短い相対パスでは close 時点の cwd で unlink されるため、`bindEx` でも事前に絶対パスにする」と明記する。

### 1-7. 長命プロセスでの fd 蓄積（`sockdir` / 動的 `Options.base`）と、Go の `m0` スレッド固定による `/proc/<pid>/cwd` 変質・マウントピン留め
- **優先度**: 中
- **どこ**:
  - fd 蓄積: [SPEC-routes-ja.md](../../docs/SPEC-routes-ja.md#L44-L55)、Go [base.go](https://github.com/kawaz/sockat-go/blob/main/base.go#L410-L462)、TS [world.ts](https://github.com/kawaz/sockat-ts/blob/main/src/world.ts#L406-L440)、Rust [base.rs](https://github.com/kawaz/sockat-rs/blob/main/src/base.rs#L707-L716)
  - Go `m0`: [threadcwd.go](https://github.com/kawaz/sockat-go/blob/main/threadcwd.go#L28-L42)、[SPEC-ja.md](../../docs/SPEC-ja.md#L300)
- **根拠**:
  - Go `base.go` L447-461: `w.sockdir[id] = b`（消された後も fd は閉じない）
  - Go `threadcwd.go` L29-38: `go func() { runtime.LockOSThread(); if err := threadChdir(dirfd); ... }()`
- **何が起きるか**:
  1. 置き場 1〜3 がすべて使えない環境で、長命 daemon がセッションごとの一時ディレクトリにソケットを bind してディレクトリごと消す運用をすると、ディレクトリごとに `.sockat.<乱数>` の B・D の fd（2 個）が増え続け、`EMFILE` に達しうる（動的に多数の `Options.base` を作って消す場合も同じ）。
  2. Go ランタイムはメインスレッド `m0` (`TID == PID`) で `LockOSThread` したまま終了した goroutine に対し、スレッドを終了させずプロセス終了まで `mPark` で眠らせる。`main` 直後や `GOMAXPROCS=1` で使い捨て goroutine が `m0` に乗ると、Linux の `/proc/<pid>/cwd`（`m0` の cwd を返す）が `D` や接続先ソケットディレクトリに変わったままになり、`thread-cwd-direct` ではそのディレクトリがプロセス終了までピン留めされて `umount` が `EBUSY` になりうる（実機での再現頻度は `未確認`、Go runtime の `mexit` の仕様に基づく）。また `threadChdir` が `errUnusable`（cwd 未変更）で返る時も `UnlockOSThread` せずにスレッドを捨てている。
- **直し方の案**: SPEC「置き場に残る物」に、置き場 1〜3 が書けない環境で多数のディレクトリに bind する場合は固定の `Options.base` を渡す旨を補う（消えた B/D のカーネル参照を外すなら `/dev/null` への `dup2` が使える）。Go の `inThreadCwd` は `errUnusable` 時に `UnlockOSThread` し、Linux で `Gettid() == Getpid()` なら別 goroutine に逃がす。

### 1-8. `sockat-rs`: `chain()` が `static CHECKED` で永久キャッシュするため、`Options.base` と `sweep_base` の呼び出しごとの途中検査が行われない ＋ `sweep_in` がパス文字列で `read_dir` している
- **優先度**: 中
- **どこ**: [base.rs](https://github.com/kawaz/sockat-rs/blob/main/src/base.rs#L203-L229) (`chain`)、[base.rs](https://github.com/kawaz/sockat-rs/blob/main/src/base.rs#L741-L748) (`check_given`)、[base.rs](https://github.com/kawaz/sockat-rs/blob/main/src/base.rs#L1106-L1144) (`sweep_in`)、仕様 [SPEC-routes-ja.md](../../docs/SPEC-routes-ja.md#L49)
- **根拠**:
  - `SPEC-routes-ja.md` L49: ``Options.base` の安全の確かめ (途中、持ち主、他人が書けない) は呼び出しのたびに行う。`
  - `base.rs` L204-206: `if let Some(c) = lock(&CHECKED).as_ref().and_then(|m| m.get(real)) { return Ok(*c); }`
  - `base.rs` L1108, L1126: `std::fs::read_dir(&b.path)?` / `std::fs::read_dir(b.path.join(&name))`
- **何が起きるか**:
  1. 一度検査に通った `Options.base` の親までのディレクトリが後で `0777`（sticky 無し）や他人所有に変わっても、Rust だけはキャッシュを返して `EPERM` にしない（Python・Go・TS は毎回検査）。
  2. `sweep_in` が `b.fd` / `d` ではなくパス文字列で `read_dir` しており、排他ロック取得後の `(st_dev, st_ino)` 再確認（他 3 言語にはある）も無い。また Linux では `Base::make` が `O_PATH` で開くため、自分所有で `0111` の B があると `sweep()` が飛ばさず `EACCES` で失敗する。
- **直し方の案**: 自動置き場 1〜3 用の 1 回キャッシュと `Options.base` / `sweep_base` 用の毎回検査を分け、`sweep_in` は fd から列挙して排他ロック後に `sys::id_at(b.fd, &name)` の一致を確認し、`sweep()` では読めない B を飛ばす。

---

## 2. 仕様と実装の食い違い

（観点 1 で挙げた項目を除く）

### 2-1. Go・TypeScript: `Options.base` に NUL バイトが含まれる時、短いパスや abstract パスで引数の誤りにならず素通りする
- **優先度**: 中
- **どこ**: Go [base.go](https://github.com/kawaz/sockat-go/blob/main/base.go#L375-L380) (`givenShape`)、TS [world.ts](https://github.com/kawaz/sockat-ts/blob/main/src/world.ts#L165-L167) (`givenShapeOk`)、仕様 [SPEC-ja.md](../../docs/SPEC-ja.md#L403)
- **根拠**:
  - `SPEC-ja.md` L403: ``Options.base` が相対パス、または最後がファイル名でない (`dir/`・`..`・`/`)。パスの長さによらず、abstract の名前の判定より前に検査する (先頭以外の NUL と同じく引数の形の検査)`
  - Go `base.go` L376: `if _, _, err := splitPath(b); err != nil || !isAbs(b)`、TS `world.ts` L166: `return isAbs(b) && splitPath(b) !== null;`
- **何が起きるか**: 短いパスや abstract パスと一緒に `Options{Base: "/tmp/a\x00b"}` / `{ base: "/tmp/a\0b" }` を渡すと、Rust・Python では引数の誤りになるのに対し、Go と TS は素通りして成功する。
- **直し方の案**: `SPEC-ja.md` L403 にも「NUL を含む」を明記し、`givenShape` / `givenShapeOk` に NUL 検査を足す。

### 2-2. `sockat-go`: `SweepBase` の親が通常ファイルの時、`ENOTDIR` ではなく `EPERM` を返す
- **優先度**: 中
- **どこ**: [sweep.go](https://github.com/kawaz/sockat-go/blob/main/sweep.go#L42-L53) (`SweepBase`) vs [base.go](https://github.com/kawaz/sockat-go/blob/main/base.go#L322-L331) (`checkGiven`)、仕様 [SPEC-ja.md](../../docs/SPEC-ja.md#L269)
- **根拠**:
  - `SPEC-ja.md` L269: ``path の確かめは `Options.base` と同じ (... ディレクトリでなければ `ENOTDIR`)``
  - `sweep.go` L43-52: `real, err := realDir(parent)` の後に `S_IFDIR` 検査が無く、`if checkAncestors(real, false) != nil { return pathErr(syscall.EPERM) }` としている。
- **何が起きるか**: `SweepBase("/tmp/dir/regular_file/b")` のように親が実在する通常ファイルの時、`filepath.EvalSymlinks` (`realDir`) は成功して通常ファイルのパスを返し、`checkAncestors` で弾かれて `ENOTDIR` でなく `EPERM` が返る（`checkAncestors` の `lstat` 失敗も `EPERM` に潰れる）。
- **直し方の案**: `checkGiven` と同じく親の `S_IFDIR` 検査（`ENOTDIR`）と `errnoOf(err)` を通す。

### 2-3. `sockat-py`: 置き場の長さ見積もりと B 作成が分離しているため、1 番目が作れない時に収まらない 2 番目の置き場に B を作り、E が 2 桁以上の境界では未使用の共有 E を D に残す
- **優先度**: 中
- **どこ**: [_place.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_place.py#L837-L865) (`auto_base`, `cross_base`)、[_place.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_place.py#L915-L946) (`real_len_guess`)、[_routes.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_routes.py#L386-L400) (`_through_real`)、[_routes.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_routes.py#L456-L473) (`_link_in_d`)、仕様 [SPEC-routes-ja.md](../../docs/SPEC-routes-ja.md#L45-L47)
- **根拠**:
  - `SPEC-routes-ja.md` L47: `残った最初の置き場で綴りの長さを見積もる。収まらなければそこで止まり、次の置き場には移らない。見積もりに通った後に作れなかった時 (...) は次の置き場へ`
  - `_place.py` L845-849: `auto_base` が `fits` を見ずに `_at_place` を呼ぶ。`_routes.py` L456-472: `d.shared_link(target)` で E を作ってから `len(spelling) > DIRECT_MAX` で弾く（`kept=True` のため `discard()` は消さない）。
- **何が起きるか**:
  1. `/tmp` が書けない・占拠されている環境で `$TMPDIR` が深いと、`real_len_guess` は `/tmp` の長さで通った後、`auto_base` が収まらない深い `$TMPDIR/sockat-<uid>` に B を作って保持してしまう（2 番目が「長すぎ＋書けない」、3 番目が「短くて書ける」なら SPEC に反して 3 番目に進む）。また `made_plain`（`_routes.py` L278）は保持済み `Options.base` を返さず、`real_len_guess` は消された `held` の `gone()` を見ない。
  2. 35 個超のディレクトリに bind してカウンタが 2 文字 (`"10"`) になった後、1 文字なら収まるが 2 文字で溢れるファイル名を新規ディレクトリに既定 `bind` すると、使われない共有 E が D に残る。（逆に Go [bind.go](https://github.com/kawaz/sockat-go/blob/main/bind.go#L229-L249) と TS [bind.ts](https://github.com/kawaz/sockat-ts/blob/main/src/bind.ts#L201-L223) は既存の 1 文字共有 E `"0"` を見る前に `nextE` で弾く逆向きの境界差がある。）
- **直し方の案**: `auto_base` / `cross_base` のループ内に `fits` 判定を入れ、共有 E の長さは既存があればその長さ・無ければ次のカウンタ長で作成前に判定する。

### 2-4. 占拠された B を飛ばした後に後続の置き場が `TooLong` になった時、Rust・Python・TypeScript は `skipped` の `reason` から占拠の情報が消える
- **優先度**: 中
- **どこ**: [SPEC-ja.md](../../docs/SPEC-ja.md#L137) vs Rust [base.rs](https://github.com/kawaz/sockat-rs/blob/main/src/base.rs#L686-L688)、Python [_routes.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_routes.py#L398-L399)、TS [world.ts](https://github.com/kawaz/sockat-ts/blob/main/src/world.ts#L243-L245)（対比: Go [base.go](https://github.com/kawaz/sockat-go/blob/main/base.go#L195-L196)）
- **根拠**:
  - `SPEC-ja.md` L137: `置き場 1〜3 の既定の名前の B が既にあって確かめに外れた (占拠) 時は、B を使う経路の reason に占拠と分かる理由を入れる`
  - Rust `base.rs` L686-688: `if !fits(...) { return Automatic::TooLong; }`（`occupied` を捨てる）、TS `world.ts` L243-244: `return spellingTooLong;`（`taken` を捨てる）
- **何が起きるか**: macOS で `/tmp/sockat-<uid>` が占拠されて長い `$TMPDIR` に移り `link-dir` が収まらなくなる場面で、Go 以外は占拠の理由を出さない（また 1 回目で `$TMPDIR` の B を保持した後の 2 回目以降の呼び出しでは全言語で出ない）。
- **直し方の案**: `TooLong` で抜ける際もその呼び出しで検出した占拠理由を `reason` に含め、2 回目以降の扱いも SPEC で「その呼び出しで占拠を踏んだ時」と明確化する。

### 2-5. Linux で PID 名前空間と `/proc` が食い違う時の connect の行選択と `procB` 事前見積もりが 4 言語で揃っていない
- **優先度**: 中
- **どこ**: [SPEC-ja.md](../../docs/SPEC-ja.md#L35) と [SPEC-ja.md](../../docs/SPEC-ja.md#L350)、Python [_routes.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_routes.py#L206-L213) vs Go [os_linux.go](https://github.com/kawaz/sockat-go/blob/main/os_linux.go#L48-L54)・[link.go](https://github.com/kawaz/sockat-go/blob/main/link.go#L34-L42) vs TS [connect.ts](https://github.com/kawaz/sockat-ts/blob/main/src/connect.ts#L61-L63)・[bind.ts](https://github.com/kawaz/sockat-ts/blob/main/src/bind.ts#L112-L117) vs Rust [route.rs](https://github.com/kawaz/sockat-rs/blob/main/src/route.rs#L808)
- **根拠**:
  - `SPEC-ja.md` L35: `/proc を使える: /proc/self/fd/<fd> と /proc/<pid>/fd/<fd> を引ける`
  - Python `_routes.py` L206: `for who in (b"self", b"%d" % os.getpid()):`（両方見る）、Go `os_linux.go` L52 / TS `connect.ts` L63: `/proc/self/fd/<fd>` だけ見る。
  - Rust `route.rs` L808 / Go `link.go` L38 / TS `bind.ts` L113: `procB` 事前見積もりで `(st_dev, st_ino)` 一致を見ない。
- **何が起きるか**: 親 PID 名前空間の `/proc` が見えている子 PID 名前空間（`/proc/self` は一致するが `/proc/<getpid()>` は不一致）では、connect で Python だけ `relative` 行、他 3 言語は `proc-direct` 行になる。また bind では Rust・Go・TS の見積もりが `procB` 可能と判定するため、実パスでは収まらない深い置き場に無駄な B を作ってしまう。
- **直し方の案**: SPEC で「connect の `proc-direct` 行選択は `/proc/self/fd/<fd>` の inode 一致、`procB`（見積もり含む）は `/proc/<pid>/fd/<fd>` の inode 一致」と分けて定義し、4 言語を揃える。

### 2-6. Apple の OS の `thread-cwd` 失敗時（Go）、Linux の abstract 名の `ForBind::socket_file()`（Rust）、その他の Unix の `bind_link_file`（Python）の食い違い
- **優先度**: 中
- **どこ**:
  - Go: [os_darwin.go](https://github.com/kawaz/sockat-go/blob/main/os_darwin.go#L83-L91) (`threadChdir`) vs [SPEC-routes-ja.md](../../docs/SPEC-routes-ja.md#L155)
  - Rust: [route.rs](https://github.com/kawaz/sockat-rs/blob/main/src/route.rs#L1441-L1443) と [route.rs](https://github.com/kawaz/sockat-rs/blob/main/src/route.rs#L1560-L1570) (`remember_resolved`) vs Go [resolve.go](https://github.com/kawaz/sockat-go/blob/main/resolve.go#L119-L121)
  - Python: [_routes.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_routes.py#L628-L635) (`bind_link_file`)
- **根拠**:
  - Go `os_darwin.go` L87-90: `case syscall.ENOSYS: return errUnusable` 以外はその場でエラー返却（SPEC-routes L155 は `pthread_fchdir_np が無い・失敗した` で使えない扱い）。
  - Rust `route.rs` L1569: `remembered_at(spelling)` が `std::fs::canonicalize("\0name")` を呼んで `InvalidInput` になる（Python・Go・TS はファイル無しの `SocketFile` を返す）。
  - Python `_routes.py` L629-635: `call.plain()` 内の bind 成功後の記録失敗（`CwdChanged` 等）まで `except OSError:` で拾い、その他の Unix では `NOT_FOLLOWED` として次の経路で再 bind しうる。
- **直し方の案**: Go はサンドボックス等の `EPERM` を `errUnusable` にし（権限不足 `EACCES` の扱いは SPEC-routes L155 と L235 を整合させる）、Rust は `remember_resolved` で abstract 名を分岐（SPEC にも明記）、Python は `s.bind()` 自体の失敗だけを `NOT_FOLLOWED` 判定にかける。

### 2-7. 重複置き場の扱い、E カウンタ初期値、Go 適合試験 CLI の `EINVAL` 変換
- **優先度**: 低
- **どこ**: Rust [base.rs](https://github.com/kawaz/sockat-rs/blob/main/src/base.rs#L569-L571) と [base.rs](https://github.com/kawaz/sockat-rs/blob/main/src/base.rs#L668)、Python [_place.py](https://github.com/kawaz/sockat-py/blob/main/src/sockat/_place.py#L285)、Go [main.go](https://github.com/kawaz/sockat-go/blob/main/internal/cmd/sockat-conform/main.go#L60-L63) と [main.go](https://github.com/kawaz/sockat-go/blob/main/internal/cmd/sockat-conform/main.go#L142-L144)
- **根拠**: Rust `places_from`（字句比較のみ）、Python `itertools.count(1)`、Go `case syscall.EINVAL: return "invalid-argument"`
- **何が起きるか**: macOS で `TMPDIR=/private/tmp` の時、Rust は `/tmp` と重複除去せず `b.place == *place` も偽となって別スロットで再 open する（Go・TS も `sweep` で同じ B を 2 回見る）。Python だけ E 名が `"1"` 始まり（1 文字 E が 35 個、他は `"0"` 始まりの 36 個）。Go の `sockat-conform` は OS の `EINVAL` も `"invalid-argument"` に変換し、入力 JSON で `"path"` キーが欠落しても空文字として実行する。
- **直し方の案**: `sweep` 対象 B の `(st_dev, st_ino)` 重複排除、Python カウンタの `0` 始まり化、`sockat-conform` の `Path *string` 化を検討する。

---

## 3. 仕様の中の矛盾、決まっていない所、読み手 (各言語の実装者と利用者) が誤解しそうな所

### 3-1. 「標準に渡す長さが `sockaddr` に入る長さより長いランタイム」（Linux の Node: 108 > 107）が SPEC と適合試験から漏れている
- **優先度**: 中
- **どこ**: [SPEC-ja.md](../../docs/SPEC-ja.md#L17-L18)（「用語」）と [SPEC-ja.md](../../docs/SPEC-ja.md#L286)（「短いパス」）、[conformance.md](../../docs/design/conformance.md#L109-L115)、TS [config.ts](https://github.com/kawaz/sockat-ts/blob/main/src/config.ts#L81-L90)
- **根拠**:
  - `SPEC-ja.md` L17: `多くは sun_path − 1、Java は sun_path − 2。` / L286: `標準に渡す長さが sockaddr に入る長さより短い言語`
  - `sockat-ts/src/config.ts` L84: `return runtime === "bun" ? 107 : 108;`
- **何が起きるか**: SPEC は「標準に渡す長さ ≤ `sun_path - 1` (107)」の前提で書かれているが、Linux の Node は NUL 無し 108 バイトを通すため `sockat-ts` は `108` にしている。Linux で 108 バイトのパスを適合試験に入れると `ts-node` だけ `standard`、他は `link-dir` になり、`lacks` 組分けでは吸収できず「差」になる。また Linux で NUL 終端無しの 108 バイトで bind したソケットに他言語の標準ライブラリが connect して `getpeername` / `recv_from` した時の相互運用性は `未確認`。
- **直し方の案**: 108 バイト NUL 無しアドレスの他言語との相互運用性を実機確認した上で、問題なければ SPEC L17 と `conformance.md` に `sun_path` ちょうどを渡すランタイムの扱いを追記し、問題があれば `sockat-ts` の Node (Linux) も `107` に揃える。

### 3-2. `pages/reach/README-ja.md`（`gen.py` 生成物）の経路表が SPEC と矛盾し、connect 系に `usable_cross_uid` の条件を書いている
- **優先度**: 中
- **どこ**: [README-ja.md](../../pages/reach/README-ja.md#L104-L106)（「経路」）、[gen.py](../../pages/reach/gen.py#L1122)、[model.json](../../pages/reach/model.json#L94)、仕様 [SPEC-ja.md](../../docs/SPEC-ja.md#L95)
- **根拠**:
  - `SPEC-ja.md` L95: `connect 系 (connect_ex 等・resolve_for_connect) は見ない`
  - `pages/reach/README-ja.md` L104, L106: `既定の connect` と `resolve_for_connect` の「要る物」に `usable_cross_uid の指定では途中と B 自身が other に x の B` と記載。また `model.json` L94 の `Options.base` の `ops` に `connect`（`connect_ex`）が無い。
- **何が起きるか**: 表の読み手が、connect 系でも `usable_cross_uid` が B 選択に効く・`connect_ex` では `Options.base` が使えないと誤解する。
- **直し方の案**: `gen.py` で connect 系の時は `usable_cross_uid` 言及の無い文言を出し分け、`Options.base` の説明に `connect_ex` を補う。

### 3-3. ハブ内の複数文書に古い状態（fork 実装中・作り直し中・未実装・`sockat-ts` 未反映）が残り矛盾している
- **優先度**: 中
- **どこ**: [fork-cwd-ja.md](../../pages/fork-cwd-ja.md#L57)、[faq-ja.md](../../pages/faq-ja.md#L7)、[DR-0017-resolve-through-persistent-base.md](../../docs/decisions/DR-0017-resolve-through-persistent-base.md#L3)、[SPEC-ja.md](../../docs/SPEC-ja.md#L10) と [SPEC-ja.md](../../docs/SPEC-ja.md#L223-L228)、[INDEX.md](../../docs/decisions/INDEX.md#L9)、[model.json](../../pages/reach/model.json#L39) と [model.json](../../pages/reach/model.json#L162-L167)
- **根拠**:
  - `fork-cwd-ja.md` L57: `sockat-rs の今の版はこの手順を実装している`（同ファイル L5 の `sockat はこの手法を使わない` および 0.5.1 の実装と矛盾）
  - `faq-ja.md` L7: `各言語の実装はこの設計へ作り直し中で`（`README-ja.md` L31-34 では 4 言語とも公開済み）
  - `DR-0017` L3: `占拠された B で次の置き場へ進むことと、既定の bind の E の使い回しは未実装`（4 言語とも実装済み）
  - `SPEC-ja.md` L10, L223-228 と `decisions/INDEX.md` L9 に `sockat-ts` が無く、`model.json` に `sockat-rs 0.4 系`・`"go": "symlink-file"` が残っている。
- **直し方の案**: 4 言語公開済みの現状に合わせて一括更新する（英語対も同時更新）。

### 3-4. 関数表の `datagram::send_to` / `send_to_ex`、`ForBind` の `SocketFile` の記述、短いパスの末尾非ファイル名エラー
- **優先度**: 低
- **どこ**: [SPEC-ja.md](../../docs/SPEC-ja.md#L76-L80)（「関数」）、[SPEC-ja.md](../../docs/SPEC-ja.md#L233-L234)（「`ForBind` の `SocketFile`」）、[SPEC-ja.md](../../docs/SPEC-ja.md#L297) と [SPEC-ja.md](../../docs/SPEC-ja.md#L408)
- **根拠**: `SPEC-ja.md` L76, L79（SEQPACKET の L80 だけ「未確定」と表記し `send_to` は確定関数と同列）、L233-234
- **何が起きるか**: `send_to` / `send_to_ex` は L88, L460 で経路が未確定とされており 4 言語とも未実装だが、関数表だけ見ると実装必須に見える。また L233「綴りを辿り」と L234「元のパスの最後の要素が symlink なら」が別処理に見えるが、綴りを最後の symlink が無くなるまで辿れば両方を満たす。末尾がファイル名でない短いパス（`"dir/"`, `"."`）が標準任せで OS ごとにエラーが変わる点も一言あると明確になる。
- **直し方の案**: 関数表の `send_to` 系にも「未確定」を添え、L233-234 を 1 文に整理し、短いパスの末尾非ファイル名が標準のまま返ることを補う。

---

## 4. 利用者から見た分かりにくさ (README・FAQ)

### 4-1. ハブ `README-ja.md` と `faq-ja.md` のアドレスの説明が、Python・TypeScript 利用者には実際の挙動と逆に見える
- **優先度**: 中
- **どこ**: ハブ [README-ja.md](../../README-ja.md#L24)（「知っておくこと」）、[faq-ja.md](../../pages/faq-ja.md#L21)（「長いパスで何が標準と違う?」）、および [SPEC-ja.md](../../docs/SPEC-ja.md#L365)
- **根拠**:
  - `README-ja.md` L24: ``長いパスでは、listener のアドレス (`local_addr` / `getsockname`) が渡したパスと違う短い綴りになる。``
- **何が起きるか**: Python（`getsockname()`）と TypeScript（`server.address()` / `listener.unix`）ではライブラリが元のパスに差し替えて返すため、利用者が手元で確認すると「短い綴りになっていない」と混乱しうる（`SPEC-ja.md` L365 にも `(Python)` としかなく TypeScript が抜けている）。
- **直し方の案**: 「カーネルが覚えるアドレス（Rust の `local_addr`、Go の `Addr()`、`lsof` 等。Python と TypeScript のソケット自身のアドレス取得は元のパスを返す）が短い綴りになる」と補い、`SPEC-ja.md` L365 にも TypeScript を足す。

### 4-2. FAQ で `bind_ex` を勧める際の close 時削除の違いと、各言語 README の不整合（TS の illumos 表・デッドコード例、Python の NUL 注意漏れ）
- **優先度**: 低
- **どこ**: ハブ [faq-ja.md](../../pages/faq-ja.md#L87) と [faq-ja.md](../../pages/faq-ja.md#L103-L111)、TS [README-ja.md](https://github.com/kawaz/sockat-ts/blob/main/README-ja.md#L145-L150) と [README-ja.md](https://github.com/kawaz/sockat-ts/blob/main/README-ja.md#L174-L179)、ハブ [langs-ja.md](../../pages/langs-ja.md#L15-L18)
- **根拠**:
  - `sockat-ts/README-ja.md` L174, L179: 見出し `connect (connect・resolveForConnect)` に対し `illumos` が `255 まで`（同 L167 では resolve は `ENAMETOOLONG`）。同 L146-149: `resolveForBind(path, { usableCrossUid: true })` の後に `!f.spelling.usableCrossUid` を検査（満たせなければ `ENAMETOOLONG` で例外になるため到達不能）。
- **何が起きるか**: Go 利用者が FAQ を読んで `Listen` → `ListenEx` に変えると `Close()` だけでは短いパスでもファイルが消えなくなる点（逆に TS は `bindEx` でも `close()` で綴りを unlink する点）を見落としやすい。TS README の表では illumos で `resolveForConnect` が届くように読める。また Python 標準 `socket` も NUL でパスを黙って切り詰めるが、`SPEC-ja.md` L374 が求める NUL の注意が `sockat-py` と `langs-ja.md` に無い。
- **直し方の案**: FAQ の `bind_ex` 言及箇所から [langs-ja.md](../../pages/langs-ja.md) へ誘導し、TS README の表・例（`bindEx` での `Dangling` 判定等）と Python の NUL 注意を整える。

### 4-3. ハブ `README-ja.md` と `faq-ja.md` に、一時ディレクトリ全滅時にソケットのディレクトリ直下へ `.sockat.<乱数>` が残る言及が無い
- **優先度**: 低
- **どこ**: [README-ja.md](../../README-ja.md#L23)、[faq-ja.md](../../pages/faq-ja.md#L85-L100)（比較: [SPEC-ja.md](../../docs/SPEC-ja.md#L250)）
- **根拠**: `faq-ja.md` L87: `/tmp/sockat-<uid> の中に小さなディレクトリと symlink を残す。`
- **何が起きるか**: `/tmp`・`$XDG_RUNTIME_DIR`・`$TMPDIR` がどれも書けないコンテナ環境（Linux）ではソケットのディレクトリに `.sockat.<乱数>` が作られ、`sweep()` でも OS の掃除でも消えないため、FAQ だけを読んだ利用者が想定外の隠しディレクトリに気づきにくい。
- **直し方の案**: FAQ「既定の `bind` は何を残す?」に「一時ディレクトリがどれも使えない時はソケットのディレクトリに `.sockat.<乱数>` を作る（場所を固定したい時は `Options.base` を使う）」と 1 文添える。

---

## 良い点 (直さない所)

- **短いパスの完全パススルー**（[SPEC-ja.md](../../docs/SPEC-ja.md#L276-L286)）：標準に渡す長さ以下では環境変数もファイルシステムも引かずに標準へ渡すため、短いパスでのオーバーヘッドと挙動変化が無い。
- **実機計測に基づく bind 経路の絞り込みと `Spelling` 型**（[DR-0017-resolve-through-persistent-base.md](../../docs/decisions/DR-0017-resolve-through-persistent-base.md)）：後で無関係なファイルに当たりうる `proc-direct`・`relative`・`at-direct` と、読み手を壊す `widened`、プロセス全体に副作用が及ぶ `fork` を bind から外し、B・flock 付き D・E と判別共用体 `Spelling` に集約した設計が非常に明快で堅牢。
- **Linux seccomp 環境での安全性**：`unshare(CLONE_FS)` が `SIGSYS` でプロセスごと殺しうる問題に対し、`prctl(PR_GET_SECCOMP)` で事前回避し、適合試験（`kill-unshare`）で全言語を検査している。
- **`sockat-ts` の native 抜きロック**（[lock.ts](https://github.com/kawaz/sockat-ts/blob/main/src/lock.ts#L44-L69)）：BSD の `O_SHLOCK` / `O_EXLOCK` と、Linux の `flock(1)` 子プロセスへの fd 継承（open file description にロックを残して即終了）により、ネイティブアドオン無し・ゾンビ無し・イベントループ阻害無しで他言語の `sweep` や `systemd-tmpfiles` と完全に噛み合っている。
- **多言語の適合試験と届く範囲の自動検証**（`conformance/`・`pages/reach/`）：`lacks` による組分けと「きっかけの経路より前の `skipped`」の横断比較、および `model.json` からの帯境目の自動導出により、4 言語間の仕様ドリフトが最小限に抑えられている。
