# CPython の os.getcwd が、PATH_MAX を超える cwd で引き直しを止めない件 (本家へ報告するための下調べ)

- Date: 2026-11-22
- Status: Concluded (CPython に公開の issue で報告した: [gh-162441](https://github.com/python/cpython/issues/162441)、2026-11-23、kawaz の名前で。非公開の窓口には出していない。illumos にも、元の原因 (cwd の文字列を覚えた後は `getcwd` が大きさによらず `ERANGE` を返す) を報告した: [illumos #18799](https://www.illumos.org/issues/18799)、2026-11-23、kawaz の名前で、分類は kernel。同じ現象の既存の報告は無かった (tracker・メーリングリスト・OmniOS と SmartOS の GitHub を検索)。sockat-py の深い cwd の試験は、illumos で `os.getcwd` を通らない作りにし、子プロセスのメモリに上限を掛けた)

## 動機

- sockat-py の Release v0.4.0 の CI ([run 44988309674](https://github.com/kawaz/sockat-py/actions/runs/44988309674)) で、illumos (OmniOS r151060 の VM) の job だけが落ちた。落ちたのは cwd の絶対パスを PATH_MAX (1024) より長くした試験 `test_a_short_relative_path_in_a_cwd_past_path_max` で、`os.path.realpath('.')` の中で `MemoryError` になった
- sockat-py は自分の側で cwd を PATH_MAX を上限に読むように直した (sockat-py の `_sys.getcwd`、v0.4.1)。残るのは CPython 本体の振る舞いで、本家に報告するかを決める前に知りたいこと
  - 本当に CPython 本体の問題か (illumos の libc・カーネルの問題との切り分け)
  - 既に報告されていないか
  - 公開の issue か、非公開の窓口 (PSRT) か
  - 直し方の案

## 調査範囲

- 対象: CPython の `os.getcwd` / `os.getcwdb` (POSIX の実装 `posix_getcwd`)。illumos の `getcwd(3C)` とその下のカーネル。比べる相手として Linux (glibc・musl)、macOS、FreeBSD、NetBSD、OpenBSD の `getcwd`
- 扱わない: Windows の実装 (`GetCurrentDirectoryW` の節。引き直しの形が違う)、CPython の build を illumos で行うこと
- 「確認済み」は下の環境の実測か、ソースの該当行で確かめたもの。「推測」はソースを読んだ上での推論で、実機では確かめていないもの。「未確認」は確かめていないもの (理由を書く)

## 環境

| 項目 | 値 |
|---|---|
| macOS | Darwin 25.5.0 arm64。CPython 3.11.3 / 3.13.4 (uv)、3.15.2 (Homebrew) |
| Linux | docker (OrbStack) の aarch64。`python:3.11-slim` (3.11.18)、`python:3.13-slim` (3.13.18)、`python:3.15-slim` (3.15.2)、`python:3.13-alpine` (3.13.18、musl)、`python:latest` (3.15.2、gcc 付き。CPython の main を build するのに使った) |
| CPython の main | `1cc580249141838a520809c21cd971883b5b10cb` (2026-11-21) |
| illumos | sockat-py の CI のログ。手元では CI と同じ VM の image (anyvm-org/omnios-builder v2.1.4 の `omnios-r151060.qcow2`) を qemu (TCG、x86_64 を arm64 の上で模倣) で動かした (結果は 3-2) |
| illumos のソース | illumos-gate `ec6987948e47ca22beba393ea01162d535aa7e8f`。OmniOS r151060 の illumos (`omniosorg/illumos-omnios` の branch r151060、`edb772c95084c0bcad18e7cf3bb68e827c4d4ee2`) と、下で引く関数 (`getcwd` の syscall、`dogetcwd`、`pn_get`、libc の `getcwd`) が同じであることを diff で確かめた |

実験物 (下の再現コード、`LD_PRELOAD` の shim) は `$TMPDIR` の下に置いた。

## 調査メモ

### 1. CI のログから読み取れること

失敗した job のログ ([job 137103645292](https://github.com/kawaz/sockat-py/actions/runs/44988309674/job/137103645292)) の要所:

```text
Target OS: omnios, Release: r151060
Requirement already satisfied: pip in /usr/lib/python3.13/vendor-packages (26.2.1)
...
E           Traceback (most recent call last):
E             File "<string>", line 32, in <module>
E             File "<string>", line 27, in _outcome
E             File "<string>", line 32, in <lambda>
E             File "<frozen posixpath>", line 424, in realpath
E           object address  : fffffc7feeb89180
E           object refcount : 3
E           object type     : fffffc7fedb05f40
E           object type name: MemoryError
E           object repr     : MemoryError()
E           lost sys.stderr
...
1 failed, 271 passed, 34 skipped in 806.40s (0:13:26)
```

- Python は OmniOS の system の 3.13。`<frozen posixpath>` の 424 行目が `getcwd()` の呼び出しになっているのは 3.13.10 以降 (3.13.1・3.13.3・3.13.5・3.13.8 では別の行、3.13.10〜3.13.18 では `path = sep if filename.startswith(sep) else getcwd()`)。omnios-build の branch r151060 の `build/python313/build.sh` は `VER=3.13.18`。VM の image に入っていた版は 3.13.16 (ログには無く、同じ image を手元で起動して `pkg list` で確かめた、3-2)
- OmniOS の Python のパッチ (`omnios-build` r151060 の `build/python313/patches/` の 35 本) に `posixmodule.c` や `getcwd` に触れるものは無い (確認済み)
- 試験のコード (sockat-py の `41a23e99` の `tests/test_relative.py`) は、`/tmp` の下に 200 バイトのディレクトリを相対パスで 1 段ずつ作って chdir し、cwd を 1027 バイトにした後、`os.getcwdb()` → `os.path.realpath(".", strict=True)` の順に呼ぶ。traceback の最後の枠は `realpath` の lambda なので、**先の `os.getcwdb()` は返っていて (成功か、`OSError`)、2 回目の cwd の読み (`realpath` の中の `os.getcwd()`) で止まらなくなった** と読める
- 進み具合の行の時刻 (05:13:04 に 70%、05:26:21 に 94%) から、この試験 1 本でおよそ 13 分かかって `MemoryError` になった (pytest の最後の行の 806 秒は 306 本全体の時間で、試験 1 本の時間ではない)。VM のメモリは 6144 MiB (`anyvm.py ... --mem 6144`)。`lost sys.stderr` は、エラーを書き出す時にもメモリが足りなかったため (推測)
- 同じ試験は他の OS で次の結果 (同じ run の各 job の `[deep cwd]` の行):

| OS (CI) | PATH_MAX | cwd | `os.getcwdb()` | `os.path.realpath('.')` |
|---|---|---|---|---|
| OpenBSD | 1024 | 1027 バイト | `ENAMETOOLONG` | `ENAMETOOLONG` |
| NetBSD | 1024 | 1027 | 成功 (1027) | 成功 (1027) |
| FreeBSD | 1024 | 1027 | 成功 (1027) | 成功 (1027) |
| Linux (ubuntu、docker) | 4096 | 4243 | 成功 (4243) | 成功 (4243) |
| macOS (3.11・3.15) | 1024 | 1027 | 成功 (1035。`/tmp` が `/private/tmp` に解決される) | 成功 (1035) |
| illumos | 1024 | 1027 | (返った。中身は出力されずに分からない) | `MemoryError` |

### 2. CPython の `posix_getcwd`

POSIX の実装 ([main の Modules/posixmodule.c 4718〜4752 行](https://github.com/python/cpython/blob/1cc580249141838a520809c21cd971883b5b10cb/Modules/posixmodule.c#L4718-L4752)):

```c
    const size_t chunk = 1024;
    ...
    Py_BEGIN_ALLOW_THREADS
    do {
        char *newbuf;
        if (buflen <= PY_SSIZE_T_MAX - chunk) {
            buflen += chunk;
            newbuf = PyMem_RawRealloc(buf, buflen);
        }
        else {
            newbuf = NULL;
        }
        if (newbuf == NULL) {
            PyMem_RawFree(buf);
            buf = NULL;
            break;
        }
        buf = newbuf;

        cwd = getcwd(buf, buflen);
    } while (cwd == NULL && errno == ERANGE);
    Py_END_ALLOW_THREADS

    if (buf == NULL) {
        return PyErr_NoMemory();
    }
```

- `getcwd(3)` が `ERANGE` を返す間、バッファを 1024 バイトずつ大きくして呼び直す。止まるのは、成功した時、`ERANGE` 以外で失敗した時、`realloc` が失敗した時 (`MemoryError`)、`PY_SSIZE_T_MAX` に届いた時だけ。**libc が大きさによらず `ERANGE` を返し続けると、メモリが尽きるまで続く** (確認済み、ソース)
- 3.13.18 ([4157〜4181 行](https://github.com/python/cpython/blob/0d4bd512fc429e3d4eacdd113c975e161f21644d/Modules/posixmodule.c#L4157-L4181)) と 3.15.2 ([4737〜4761 行](https://github.com/python/cpython/blob/5e58eaad7c58df58dfa8ea549c87996e01dd1077/Modules/posixmodule.c#L4737-L4761)) も POSIX の節は main と同じ (diff で確かめた。3.13.18 との違いは Windows の節の型変換 1 か所だけ、3.15.2 は全く同じ)。3.11.0 も引き直しのループは同じ (ループの後の処理が違う)
- 前提にしているのは POSIX の `ERANGE` の定義「The size argument is greater than 0, but is smaller than the length of the string +1.」([POSIX.1-2024 getcwd](https://pubs.opengroup.org/onlinepubs/9799919799/functions/getcwd.html) の ERRORS、`shall fail` の側)。つまり「`ERANGE` ならバッファを大きくすれば通る」は POSIX の上では正しいが、それに従わない実装に対する歯止めが無い

経緯 (確認済み、各 commit と issue):

| 時期 | 出来事 |
|---|---|
| 2008 | [gh-46974 (bpo-2722)](https://github.com/python/cpython/issues/46974): 2.x の `os.getcwd` が `ERANGE` で引き直す形になる |
| 2010 | [gh-53431 (bpo-9185) "os.getcwd causes infinite loop on solaris"](https://github.com/python/cpython/issues/53431): Solaris と OpenBSD で、PATH_MAX を超える cwd では `getcwd()` が `ERANGE` を返し続け、引き直しが止まらずメモリを食う。2.7 では Solaris・OpenBSD だけ `PATH_MAX+2` の固定のバッファで 1 回呼ぶ形にして直した ([182ae64](https://github.com/python/cpython/commit/182ae64235c510c7b40f7b26a1490d3f2163d00d))。当時の 3.x は 1026 バイトの固定のバッファで、ループが無かった |
| 2012 | [gh-55434](https://github.com/python/cpython/issues/55434)・[gh-59969](https://github.com/python/cpython/issues/59969) (bpo-15765): NetBSD も同じで、2.7 の回避に NetBSD を足した ([da4277a](https://github.com/python/cpython/commit/da4277a739bab61e79dc4d064b1e1648ddd59150)) |
| 2015 | [gh-53492 (bpo-9246) "os.getcwd() hardcodes max path len"](https://github.com/python/cpython/issues/53492): 3.4 / 3.5 に 2.x と同じ引き直しのループを入れた ([4403d7d](https://github.com/python/cpython/commit/4403d7def0ec8e6b395223fb2ab8b570ecc7a6e4))。2011 年の議論で「Solaris/OpenBSD に対応させる」と書かれていたが、入った変更に bpo-9185 の回避は無い。**3.x はこの時から bpo-9185 と同じ形に戻っている** (2.7 の回避が 3.x に移されなかった) |

試験の穴 (確認済み、ソース):

- bpo-9185 の試験 `test_getcwd_long_pathnames` ([main の Lib/test/test_os/test_posix.py 1296〜1329 行](https://github.com/python/cpython/blob/1cc580249141838a520809c21cd971883b5b10cb/Lib/test/test_os/test_posix.py#L1296-L1329)) は、本体が `except:` 節の `return` の後に字下げされていて一度も実行されない (2013 年に gh-53492 で指摘されたまま)。手元で走らせると 0.000 秒で ok になる
- bpo-37412 の試験 `test_getcwd_long_path` ([main の Lib/test/test_os/test_os.py 127〜183 行](https://github.com/python/cpython/blob/1cc580249141838a520809c21cd971883b5b10cb/Lib/test/test_os/test_os.py#L127-L183)) は、絶対パスで `os.mkdir(path)` / `os.chdir(path)` するので、PATH_MAX が 1024 の OS では 1024 を超えた所で `ENAMETOOLONG` になって打ち切る。相対パスで 1 段ずつ降りないので、PATH_MAX を超える cwd に入ることが無い。illumos・OpenBSD・NetBSD の buildbot が仮にあっても、この試験ではこの問題に当たらない

影響する呼び出し元 (確認済み、ソース。illumos の実機では `os.getcwd` と import の仕組みを確かめた、3-2):

- `os.getcwd` / `os.getcwdb` そのもの
- 相対パスを渡した `os.path.abspath` / `os.path.realpath` ([3.13.18 の posixpath.py 424 行](https://github.com/python/cpython/blob/0d4bd512fc429e3d4eacdd113c975e161f21644d/Lib/posixpath.py#L424))、`pathlib.Path.cwd` / `absolute` / `resolve`
- import の仕組み: `PathFinder._path_importer_cache` が `sys.path` の `''` (`python -c` や対話の時の先頭) を `os.getcwd()` に置き換える ([3.13.16 の Lib/importlib/_bootstrap_external.py 1509〜1513 行](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/importlib/_bootstrap_external.py#L1509-L1513)、[main では 1226〜1232 行](https://github.com/python/cpython/blob/1cc580249141838a520809c21cd971883b5b10cb/Lib/importlib/_bootstrap_external.py#L1226-L1232))。`find_spec` (3.13.16 の 1560 行) → `_get_spec` (1532 行) → `_path_importer_cache` (1511 行の `path = _os.getcwd()`) と辿る。illumos の実機の traceback の行番号 (3-2) と一致する。受ける例外は 3.13 では `FileNotFoundError` だけ、main では `FileNotFoundError` と `PermissionError`。どちらも `MemoryError` や他の `OSError` は受けない。そのため、PATH_MAX を超える cwd で起動した `python -c` や対話から、初めて読む top-level のモジュール (`json`、`ctypes` 等) を import するだけで当たる
- インタプリタの起動 (getpath) は影響しない: `_Py_wgetcwd` ([main の Python/fileutils.c 2784 行〜](https://github.com/python/cpython/blob/1cc580249141838a520809c21cd971883b5b10cb/Python/fileutils.c#L2784-L2800)) は `MAXPATHLEN` の固定のバッファで 1 回呼ぶだけ

### 3. illumos の `getcwd`

#### 3-1. ソース

libc の `getcwd` は、`buf` を渡された時は `SYS_getcwd` を 1 回呼ぶだけ ([usr/src/lib/libc/port/gen/getcwd.c 106〜112 行](https://github.com/illumos/illumos-gate/blob/ec6987948e47ca22beba393ea01162d535aa7e8f/usr/src/lib/libc/port/gen/getcwd.c#L106-L112))。`getcwd(NULL, 0)` の時だけ自分でバッファを倍にして呼び直し、「To protect against unbounded memory usage, cap to 128KiB.」と 128 KiB で打ち切る (同 [50〜91 行](https://github.com/illumos/illumos-gate/blob/ec6987948e47ca22beba393ea01162d535aa7e8f/usr/src/lib/libc/port/gen/getcwd.c#L50-L91))。

カーネルの `getcwd` ([usr/src/uts/common/syscall/getcwd.c 63〜95 行](https://github.com/illumos/illumos-gate/blob/ec6987948e47ca22beba393ea01162d535aa7e8f/usr/src/uts/common/syscall/getcwd.c#L63-L95)):

```c
	kbuflen = MIN(buflen, MAXPATHLEN);

	while (kbuflen <= kmem_max_cached) {
		kbuf = kmem_alloc(kbuflen, KM_SLEEP);

		if (((err = dogetcwd(kbuf, kbuflen)) == 0) &&
		    (copyout(kbuf, buf, strlen(kbuf) + 1) != 0)) {
			err = EFAULT;
		}

		kmem_free(kbuf, kbuflen);
		...
		if (err == ENAMETOOLONG || err == ERANGE) {
			/* For some reason, getcwd() uses ERANGE. */
			err = ERANGE;
			/*
			 * If the user's buffer really was too small, give up.
			 */
			if (kbuflen == buflen)
				break;
			kbuflen = MIN(kbuflen * 2, buflen);
		} else {
			break;
		}
	}
```

- `dogetcwd` が `ENAMETOOLONG` を返し続けると、カーネルの中で `kmem_max_cached` まで倍にして試した後、利用者のバッファの大きさによらず `ERANGE` を返す。この上限は illumos [9620 "getcwd() syscall has unbounded memory allocation"](https://github.com/illumos/illumos-gate/commit/7eb8c88abb70697edf48045434d2c18bb82ad2e7) (2021) で入った。それ以前のカーネルは同じ場面で上限なしに倍にし続けていた
- `dogetcwd` ([usr/src/uts/common/fs/lookup.c 1463〜1552 行](https://github.com/illumos/illumos-gate/blob/ec6987948e47ca22beba393ea01162d535aa7e8f/usr/src/uts/common/fs/lookup.c#L1463-L1552)) は、プロセスが覚えている cwd の文字列 (`u_cwd`) があれば、まずそれを `pn_get` で読み込んで引き直す。`pn_get` は `MAXPATHLEN` のバッファしか持たず、それより長い文字列は `ENAMETOOLONG` になる ([usr/src/uts/common/fs/pathname.c 125〜134 行](https://github.com/illumos/illumos-gate/blob/ec6987948e47ca22beba393ea01162d535aa7e8f/usr/src/uts/common/fs/pathname.c#L125-L134))。その時 `dogetcwd` は `u_cwd` を残したまま `ENAMETOOLONG` を返す ([1496〜1500 行](https://github.com/illumos/illumos-gate/blob/ec6987948e47ca22beba393ea01162d535aa7e8f/usr/src/uts/common/fs/lookup.c#L1496-L1500))
- `u_cwd` は、`dogetcwd` が逆引き (`vnodetopath_common`) で成功した時に、その結果で書かれる ([1535〜1546 行](https://github.com/illumos/illumos-gate/blob/ec6987948e47ca22beba393ea01162d535aa7e8f/usr/src/uts/common/fs/lookup.c#L1535-L1546))。長さの確かめは無い。chdir で別のディレクトリに移ると消える ([usr/src/uts/common/syscall/chdir.c 242〜253 行](https://github.com/illumos/illumos-gate/blob/ec6987948e47ca22beba393ea01162d535aa7e8f/usr/src/uts/common/syscall/chdir.c#L242-L253))

ここから読める筋書き (ソースからの推測。3-2 の実機で確かめた):

1. chdir の直後は `u_cwd` が無い。逆引きで、十分なバッファ (1027 バイトの cwd なら 2048) を渡せば成功し、1027 バイトの `u_cwd` が覚えられる
2. 次の `getcwd` は `u_cwd` を `pn_get` で読もうとして `ENAMETOOLONG`。逆引きに進まずに返り、カーネルの中の倍の試し直しも全部同じ所で失敗し、`ERANGE` になる。chdir で移るまで、どの大きさのバッファでも同じ
3. CPython の 1 回目 (`os.getcwdb()`) は 1024 → `ERANGE`、2048 → 成功 で返る。2 回目 (`realpath` の中の `os.getcwd()`) は 2 の状態に当たり、CPython が `ERANGE` のたびにバッファを大きくし続けて `MemoryError` になる。これは 1 の CI のログ (1 回目は返り、2 回目で止まらない) と合う

man ([getcwd.3c の ERRORS](https://github.com/illumos/illumos-gate/blob/ec6987948e47ca22beba393ea01162d535aa7e8f/usr/src/man/man3c/getcwd.3c#L189-L194)) は `ERANGE` を「The pathname (including its terminating nul character) is too long to fit into the provided (or allocated) buffer.」とだけ書く。十分なバッファでも `ERANGE` を返すのは、man とも POSIX とも違う (illumos 側の不具合)。

#### 3-2. 実機 (OmniOS r151060、qemu)

CI と同じ VM の image (`omnios-r151060.qcow2`) を手元の qemu で起動した。`uname -a` は `SunOS omnios 5.11 omnios-r151060-513bc64de92 i86pc i386 i86pc`、Python は `runtime/python-313` の 3.13.16、`getconf PATH_MAX /` は 1024。

libc の `getcwd` を ctypes で直接、バッファの大きさと順を変えて呼んだ (`libc_getcwd_probe.py`。各組の前に `chdir("..")` → `chdir(元の名前)` で cwd を入り直す):

```text
sunos5 PATH_MAX 1024, cwd 1224 bytes
A: fresh chdir, then 1 MiB buffer twice
   getcwd(buf, 1048576) -> ok 1224 bytes
   getcwd(buf, 1048576) -> NULL ERANGE
B: fresh chdir, then 1024, 2048, 1 MiB, 2048
   getcwd(buf, 1024) -> NULL ERANGE
   getcwd(buf, 2048) -> ok 1224 bytes
   getcwd(buf, 1048576) -> NULL ERANGE
   getcwd(buf, 2048) -> NULL ERANGE
C: fresh chdir, then os.getcwd() (CPython) once, then 1 MiB
   os.getcwd() -> ok 1224 bytes
   getcwd(buf, 1048576) -> NULL ERANGE
```

cwd を 5043 バイトにしても同じ形 (A は 1 回目 ok・2 回目 `ERANGE`、B は 1 MiB で ok の後 `ERANGE`、C も同じ)。macOS と Linux (glibc) で同じプローブを流すと、十分な大きさのバッファでは何度呼んでも成功する。

- **3-1 の筋書きのとおり (確認済み)**: chdir の後の最初の成功の後は、1 MiB のバッファでも `ERANGE` を返し続ける。chdir で入り直すと 1 回だけまた通る
- 再現コード (5): 引数なし (cwd 1224 バイト) も `5000` (5043 バイト) も、`call 1: ok`、`call 2: MemoryError`、exit 1 (子の `RLIMIT_AS` は 512 MiB、`MemoryError` まで 54 秒。上限を掛けなかった CI では VM のメモリを使い切るまで 13 分)
- import の仕組みでも当たる: 1224 バイトの cwd から `python3 -c "import json"` を起動すると (`ulimit -v 524288` の下)、`importlib._bootstrap_external` の `_path_importer_cache` の中で `MemoryError` になり、`lost sys.stderr` で exit 1 (起動の後の最初の `os.getcwd()` は通り、2 回目の import で当たる)

```text
  File "<frozen importlib._bootstrap_external>", line 1511, in _path_importer_cache
object type name: MemoryError
object repr     : MemoryError()
lost sys.stderr
```

### 4. 他の OS の `getcwd` の同じ場面

| OS | PATH_MAX を超える cwd で何を返すか | 根拠 | CPython の引き直し |
|---|---|---|---|
| Linux + glibc | カーネルは `PATH_MAX` (4096) を超えると `ENAMETOOLONG` ([fs/d_path.c 412〜446 行、v6.18](https://github.com/torvalds/linux/blob/7d0a66e4bb9081d75c82ec4957c50034cb0ea449/fs/d_path.c#L412-L446))。glibc はそれを受けて `..` を辿る一般の実装に切り替え ([sysdeps/unix/sysv/linux/getcwd.c 97〜116 行、2.42](https://github.com/bminor/glibc/blob/d2097651cc57834dbfcaa102ddfacae0d86cfb66/sysdeps/unix/sysv/linux/getcwd.c#L97-L116))、そこでの `ERANGE` は渡されたバッファが本当に足りない時だけ | ソース + 実測 (5) | 止まる (成功する) |
| Linux + musl | `ENAMETOOLONG` | 実測 (5) | 止まる (`OSError`) |
| macOS | 成功する (5104 バイトまで実測) | 実測 (5)。Apple の libc のソースは読んでいない | 止まる (成功する) |
| FreeBSD | カーネルは `MAXPATHLEN` までしか作らず ([sys/kern/vfs_cache.c 3237〜3238 行](https://github.com/freebsd/freebsd-src/blob/c6e1457a1cdbb0edd10bdce1e9e6c384a3b256e4/sys/kern/vfs_cache.c#L3237-L3238))、失敗すると libc が `..` を辿る実装に切り替える ([lib/libc/gen/getcwd.c 92 行〜](https://github.com/freebsd/freebsd-src/blob/c6e1457a1cdbb0edd10bdce1e9e6c384a3b256e4/lib/libc/gen/getcwd.c#L92))。`ERANGE` は利用者のバッファが足りない時だけ | ソース + CI (1) | 止まる (成功する) |
| NetBSD | カーネルは作業用のバッファを `MAXPATHLEN * 4` (4096) で打ち切る ([sys/kern/vfs_getcwd.c 490〜493 行](https://github.com/NetBSD/src/blob/4f3cc06c9f9280fc3dc148b00c8365eaf13d7ea5/sys/kern/vfs_getcwd.c#L490-L493))。libc は `buf` を渡されると 1 回呼ぶだけ ([lib/libc/gen/getcwd.c 228〜236 行](https://github.com/NetBSD/src/blob/4f3cc06c9f9280fc3dc148b00c8365eaf13d7ea5/lib/libc/gen/getcwd.c#L228-L236)) | ソース + CI (1027 バイトは成功) | 1027 バイトでは止まる。**4096 を超える cwd ではカーネルが大きさによらず `ERANGE` を返す見込みで、CPython は止まらない** (推測、未確認) |
| OpenBSD | カーネルは作業用のバッファを `MAXPATHLEN * 4` で打ち切り、結果を `MAXPATHLEN` までしか写さない ([sys/kern/vfs_getcwd.c 400〜403・422 行](https://github.com/openbsd/src/blob/db89d5490137134f5570d82b6a9461096998365a/sys/kern/vfs_getcwd.c#L400-L422))。作業用のバッファが足りないと `ERANGE` ([177〜180 行](https://github.com/openbsd/src/blob/db89d5490137134f5570d82b6a9461096998365a/sys/kern/vfs_getcwd.c#L177-L180)) | ソース + CI (1027 バイトは `ENAMETOOLONG`) | 1027 バイトでは止まる。**4096 を超える cwd では NetBSD と同じく止まらない見込み** (推測、未確認) |
| illumos | 3 のとおり。2 回目以降、大きさによらず `ERANGE` | ソース + CI + 実機 (3-2) | 止まらない |

- 2010 年の bpo-9185 は Solaris と OpenBSD、2012 年の bpo-15765 は NetBSD で同じ「`ERANGE` を返し続ける」を報告している。OpenBSD・NetBSD が当たったのは、どちらも試験の長さを 4099 バイトに上げた時 (gh-53431 の「OpenBSD has the same getcwd() bug. It was uncovered by raising current_path_length to 4099 in test_posix.」、gh-59969 の「4099 is a reasonable limit」)。今のカーネルの打ち切り (`MAXPATHLEN * 4` = 4096) と合い、1027 バイトでは当たらない (CI) こととも合う。今も 4096 を超える所で同じ形が残っていると読めるが、確かめていない
- PEP 11 の上で、illumos・NetBSD・OpenBSD は unsupported (どの tier にも無い)。FreeBSD は Tier 3 で、ソースと CI の両方で当たらない

### 5. 再現コード

`getcwd_past_path_max.py` (依存なし。PoC として報告に付ける形):

```python
"""Reproducer: os.getcwd() in a working directory longer than PATH_MAX.

The parent creates a directory chain one 200-byte component at a time
(relative mkdir + chdir, so no single path argument is longer than
PATH_MAX) until the cwd is longer than the target length, then calls
os.getcwd() twice in a child process whose address space is capped, so
that an unbounded retry loop ends in MemoryError instead of exhausting
the machine. Exits 1 if a call raised MemoryError or timed out, else 0.

usage: python3 getcwd_past_path_max.py [target_length]
"""
import os
import subprocess
import sys
import tempfile

CHILD = r"""
import os, resource, sys
limit = 512 * 1024 * 1024
for name in ("RLIMIT_AS", "RLIMIT_VMEM", "RLIMIT_DATA"):
    if hasattr(resource, name):
        try:
            resource.setrlimit(getattr(resource, name), (limit, limit))
            break
        except (ValueError, OSError):
            pass
for i in (1, 2):
    try:
        r = os.getcwd()
        print(f"call {i}: ok, {len(os.fsencode(r))} bytes", flush=True)
    except MemoryError:
        print(f"call {i}: MemoryError", flush=True)
        sys.exit(1)
    except OSError as e:
        print(f"call {i}: OSError errno={e.errno} ({os.strerror(e.errno)})", flush=True)
"""


def main() -> int:
    path_max = os.pathconf("/", "PC_PATH_MAX")
    target = int(sys.argv[1]) if len(sys.argv) > 1 else path_max
    root = tempfile.mkdtemp(prefix="gcwd-")
    os.chdir(root)
    length = len(os.fsencode(os.path.realpath(root)))
    depth = 0
    while length <= target:
        os.mkdir("d" * 200)
        os.chdir("d" * 200)
        length += 201
        depth += 1
    print(f"{sys.platform} Python {sys.version.split()[0]}: PATH_MAX {path_max}, cwd {length} bytes", flush=True)
    try:
        out = subprocess.run([sys.executable, "-I", "-c", CHILD], timeout=300)
        code = 1 if out.returncode != 0 else 0
    except subprocess.TimeoutExpired:
        print("child: timed out after 300 s", flush=True)
        code = 1
    for _ in range(depth):
        os.chdir("..")
        os.rmdir("d" * 200)
    os.chdir("/")
    os.rmdir(root)
    print("VULNERABLE (unbounded retry)" if code else "not affected", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
```

結果 (引数なしは PATH_MAX を少し超える長さ、`5000` は 5000 バイトを超える長さ):

| 環境 | 引数なし | 5000 |
|---|---|---|
| macOS、3.11.3 / 3.13.4 / 3.15.2 | 1084 バイト。1 回目・2 回目とも成功、exit 0 | 5104 バイト。両方成功、exit 0 |
| Linux glibc、3.11.18 / 3.13.18 / 3.15.2 | 4239 バイト。両方成功、exit 0 | 5043 バイト。両方成功、exit 0 |
| Linux musl、3.13.18 | 4239 バイト。両方 `OSError errno=36 (Filename too long)`、exit 0 | 5043 バイト。同じ |
| illumos (OmniOS r151060)、3.13.16 | 1224 バイト。1 回目は成功、2 回目は `MemoryError`、exit 1 | 5043 バイト。同じ |

CPython 側だけを見る実験 (Linux glibc、3.15.2): `getcwd()` が常に `ERANGE` を返す `LD_PRELOAD` の shim (`char *getcwd(char *b, size_t n) { errno = ERANGE; return NULL; }`) の下で `os.getcwd()` を呼ぶと、`RLIMIT_AS` を 64 MiB にしても 512 MiB にしても、上限まで確保して `MemoryError` になる。上限を掛けなければメモリが尽きるまで確保し続ける見込み (上限なしでは試していない。ソースからの推測で、illumos の CI の 13 分がその形)。

関連して見えたこと (この報告の範囲外): musl で PATH_MAX を超える cwd から `python3 -c "import json"` を動かすと、import の仕組みが `''` を `os.getcwd()` に置き換える所の `OSError: [Errno 36] Filename too long` で落ちる (glibc と macOS では通る)。import の仕組みが受ける例外が限られているため (2 の「影響する呼び出し元」)。

### 6. 既に報告されていないか

python/cpython の issue と PR を `getcwd ERANGE`、`getcwd MemoryError`、`getcwd illumos`、`getcwd Solaris`、`getcwd PATH_MAX`、`getcwd infinite loop`、`getcwd loop`、`posix_getcwd`、`getcwd long path` で検索した (2026-11-22)。

| issue | 状態 | 中身 |
|---|---|---|
| [gh-53431 (bpo-9185)](https://github.com/python/cpython/issues/53431) | closed (2010、2.7 で直した) | 同じ現象の Solaris・OpenBSD 版。3.x への回帰は書かれていない |
| [gh-51225 (bpo-6976)](https://github.com/python/cpython/issues/51225) | closed (bpo-9185 の重複) | Solaris 9 の同じ現象。1 MB で打ち切るパッチの提案 |
| [gh-55434](https://github.com/python/cpython/issues/55434)・[gh-59969](https://github.com/python/cpython/issues/59969) (bpo-15765) | closed (2012) | NetBSD の同じ現象 (2.7 の回避に NetBSD を足した) |
| [gh-53492 (bpo-9246)](https://github.com/python/cpython/issues/53492) | closed (2015) | 3.x にループを入れた変更。Solaris/OpenBSD への配慮は議論にあったが入っていない |
| [gh-46974 (bpo-2722)](https://github.com/python/cpython/issues/46974) | closed (2008) | 2.x に引き直しを入れた変更 |
| [gh-117856](https://github.com/python/cpython/issues/117856) | closed (not planned) | `os.getcwd` の速さの話で無関係 |

3.x の今の実装でこの現象を報告した issue・PR は見つからなかった。

### 7. 公開の issue か、非公開の窓口か

CPython の [SECURITY.md](https://github.com/python/cpython/blob/1cc580249141838a520809c21cd971883b5b10cb/.github/SECURITY.md) は、何を脆弱性として扱うかを devguide の Security policy ([security/policy.rst](https://github.com/python/devguide/blob/8c852bdd3f06b8447185fe2945af5de52a96a0ac/security/policy.rst)) に委ねる。関係する段落 (段落ごとに引く):

> Vulnerabilities must not depend on malicious control of Python's launch conditions, including (but not limited to) command line arguments, environment variables, or modifications to files on the target system. We assume that, at the time Python is executed, the environment is as intended by the legitimate user, and any malicious variation from this cannot be mitigated by Python itself.

> Vulnerabilities that affect availability (such as DoS, ReDoS, crashes, dead-locks, and resource exhaustion) must be triggerable with data inputs that are reasonably sized for the use case. Availability vulnerabilities must also demonstrate an "upward" change in posture for the attacker, rather than a "lateral" one. This is to avoid handling performance improvements as security vulnerabilities.

> Exceptions are an expected part of control flow when processing inputs. Unhandled exceptions are not considered crashes and are not, by themselves, security vulnerabilities.

> If a vulnerability is platform-dependent, check if the platform is supported per :pep:`11`. Vulnerabilities that exclusively affect unsupported platforms are not treated as vulnerabilities in Python.

PEP 11 ([peps/pep-0011.rst](https://github.com/python/peps/blob/4434e728a7db24540d581f52e96570ca1230356e/peps/pep-0011.rst) の Unsupported platforms):

> All platforms not listed in the above tiers are *unsupported* by the core team. The core team does not develop and test on such platforms, and so they cannot provide any promises that Python will work on them.

判断: **公開の issue (Bug report) が妥当。非公開の窓口 (GHSA / security@python.org) には当たらない。** 理由:

- 当たる OS (illumos。推測では 4096 を超える cwd の NetBSD・OpenBSD も) は全部 PEP 11 の unsupported。policy は「unsupported の OS だけに当たるものは Python の脆弱性として扱わない」と書く。Tier の OS では当たらない (Linux・macOS・FreeBSD はソースと実測・CI で確かめた。Windows は別の実装 (`GetCurrentDirectoryW`) でこのループを通らない)
- 引き金は「PATH_MAX を超える深さのディレクトリを作り、そこを cwd にしたプロセスで `os.getcwd()` が呼ばれる」こと。攻撃者がそれを起こすには、被害者のプロセスの cwd か、被害者が入るディレクトリの木を作る力が要る。これは policy の言う launch conditions / modifications to files on the target system に当たり、得るものはそのプロセスを止めることだけで、既に持っている力に対して lateral
- 止まった先は `MemoryError` (例外)。ただしメモリを使い切るまでの間、同じ機械の他のプロセスにも影響しうる (CI では 13 分かけて 6144 MiB の VM のメモリを使い切った)。この点は policy の resource exhaustion に字の上では当たるが、上の 2 点 (unsupported、launch conditions) で外れる
- 前の CPython への報告 (8) は、macOS (Tier 1) で初期化されていないメモリを読んで返す (情報が漏れうる) ものだったので非公開にした。今回はそれと違い、情報は漏れない

unsupported の OS の不具合を公開の issue に出すこと自体は、PEP 11 の Unsupported platforms の「Contributions in this area are welcome as long as they: pose a minimal maintenance burden to the core team, and benefit substantially more people than the contributor.」の範囲で受け付けられる。直し方を OS によらない数行にすれば (9)、この条件に合わせやすい。devguide の [Ports and contacts](https://github.com/python/devguide/blob/8c852bdd3f06b8447185fe2945af5de52a96a0ac/developer-workflow/porting.rst) は Solaris/OpenIndiana の窓口として `jcea`・`kulikjak` (GitHub のユーザ名) を挙げ、「It is OK to @mention the listed GitHub usernames to draw maintainers' attention」と書く。illumos の項は無い。

### 8. 前に CPython へ上げた例

sockat と sockat-py の `docs` を `cpython`・`bpo`・`python/cpython`・`getsockname`・`security@python`・`PSRT` で検索して、1 件見つかった。

- 中身: macOS で広げた sockaddr (104 バイトを超えるパス) で bind したソケットの `getsockname()` / `getpeername()` が、`sun_path` の外の初期化されていないバイトまで読んで返す ([sockat-py の findings 2026-11-18](https://github.com/kawaz/sockat-py/blob/main/docs/findings/2026-11-18-cpython-getsockname-widened-sockaddr.md))
- 進め方: 2026-11-18 に security@python.org へ非公開で送り (公開の [gh-52619](https://github.com/python/cpython/issues/52619) と同じ根の macOS 版として)、security@python.org から GitHub Security Advisory (GHSA) に回すよう返事があったので、2026-11-19 に CPython の GHSA で報告し直した (getsockname / getpeername / accept の 3 経路、3.11〜3.15 で再現)。PSRT の判断待ち ([issue の記録](../issue/archive/2026-11-19-roll-out-dr-0012.md) の「関連」)
- 今回に効くこと: CPython 本体の脆弱性の窓口は、今は GHSA (`https://github.com/python/cpython/security/advisories/new`) で、security@python.org は CPython 以外か迷った時の窓口 (policy の「How to submit a vulnerability report?」と合う)。今回は 7 のとおり脆弱性に当たらないので、どちらも使わず公開の issue にする

### 9. 直し方の案

#### 9-1. 案

OS によらず、引き直しにバッファの上限を置き、届いたら最後の `ERANGE` をそのまま `OSError` にする。CPython の main に当てる diff:

```diff
--- a/Modules/posixmodule.c
+++ b/Modules/posixmodule.c
@@ -4716,6 +4716,11 @@ posix_getcwd(int use_bytes)
     return resobj;
 #else
     const size_t chunk = 1024;
+    /* Some getcwd() implementations keep failing with ERANGE for a working
+       directory longer than PATH_MAX, whatever the size of the buffer
+       (illumos).  Stop growing the buffer at this size and raise the
+       ERANGE error rather than growing it until memory runs out. */
+    const size_t max_buflen = 1024 * 1024;
 
     char *buf = NULL;
     char *cwd = NULL;
@@ -4724,13 +4729,12 @@ posix_getcwd(int use_bytes)
     Py_BEGIN_ALLOW_THREADS
     do {
         char *newbuf;
-        if (buflen <= PY_SSIZE_T_MAX - chunk) {
-            buflen += chunk;
-            newbuf = PyMem_RawRealloc(buf, buflen);
-        }
-        else {
-            newbuf = NULL;
+        if (buflen >= max_buflen) {
+            /* errno is still ERANGE from the last getcwd() call */
+            break;
         }
+        buflen += chunk;
+        newbuf = PyMem_RawRealloc(buf, buflen);
         if (newbuf == NULL) {
             PyMem_RawFree(buf);
             buf = NULL;
```

- 上限に届くと `buf` は残り `cwd` は `NULL` なので、ループの後の既存の `posix_error()` が `OSError(ERANGE)` を投げる。`Py_END_ALLOW_THREADS` は errno を保つ (既存のコードも同じことに頼っている)
- 上限の値 (1 MiB) は仮。決め手は「実在する cwd より十分大きく、使い切ってもすぐ返る」こと。参考: illumos の libc は `getcwd(NULL, 0)` を 128 KiB で、NetBSD の libc は 4096 で打ち切る。Linux (glibc) と macOS では PATH_MAX を超える cwd も返るので、PATH_MAX を上限にしてはいけない (5 で 5000 バイトを超える cwd が成功している)
- 1024 バイトずつなので、上限まで 1024 回 `getcwd` を呼ぶ。倍にしていく形 (10 回程度) に変えることもできるが、diff を小さく保つために足し算のままにした。どちらにするかは査読に任せる
- 返す errno: libc が返した `ERANGE` をそのまま返す。`ENAMETOOLONG` に換える案もある (musl・OpenBSD がこの場面で返すもの) が、libc の答えを換えない方が説明しやすい

他の案 (比べた):

| 案 | 中身 | 良い点 | 悪い点 |
|---|---|---|---|
| A (推し) | 上の、OS によらない上限 | 数行で、unsupported の OS 向けの `#ifdef` を増やさない。illumos で 1 回目に通る cwd (3-2) は今までどおり読める | 上限の値に根拠となる標準が無い |
| B | 2.7 の bpo-9185 の形: illumos・Solaris (と NetBSD・OpenBSD) だけ `PATH_MAX+2` の固定のバッファで 1 回 | 2.7 で実績がある | OS ごとの `#ifdef` が増える (PEP 11 の「minimal maintenance burden」に反しやすい)。illumos で 1 回目なら読める cwd も読めなくなる |
| C | `getcwd(NULL, 0)` (libc に確保させる) を使う | 確保の上限を libc に任せる | `getcwd(NULL, 0)` は POSIX では unspecified。musl は PATH_MAX の固定、illumos は内部で同じ `ERANGE` に当たる。確保に `PyMem_Raw*` を使わなくなる |

#### 9-2. 確かめたこと

CPython の main (`1cc5802`) に上の diff を当てて、docker の Linux (`python:latest`、gcc 14.2) で build した (`./configure && make`)。

```text
3.16.0a2+dev (1cc5802-dirty:1cc5802, Nov 22 2026, 05:56:36) [GCC 14.2.0]
--- patched build, getcwd() forced to ERANGE (shim), no RLIMIT
getcwd -> OSError 34 Numerical result out of range after 0.000 s
getcwdb -> OSError 34 Numerical result out of range after 0.000 s
--- stock python3 (unpatched) under the same shim, RLIMIT_AS 512 MiB
RLIMIT_AS 512 MiB: os.getcwd() -> MemoryError after 0.0 s
--- patched build, real deep cwd
linux Python 3.16.0a2+dev: PATH_MAX 4096, cwd 5043 bytes
call 1: ok, 5043 bytes
call 2: ok, 5043 bytes
```

- `ERANGE` を返し続ける libc (shim) の下で、直した版はすぐ `OSError(ERANGE)` を返し、直す前の版は上限まで確保して `MemoryError` になる
- 直した版でも PATH_MAX (4096) を超える 5043 バイトの cwd は今までどおり読める
- `test_os` の `MiscTests.test_getcwd` / `test_getcwd_long_path` / `test_getcwdb` と `test_os.test_posix` の `test_getcwd_long_pathnames` は、直す前と後の両方で通る (`./python -m test test_os -m "*getcwd*" -v`)
- 未検証: illumos で直した版を build して動かすこと (VM で CPython を build する手順を用意していない。上の shim と 3-2 の実機の振る舞いを合わせた推測)

#### 9-3. 試験と NEWS (CPython の作法)

- 試験の置き場: `Lib/test/test_os/test_os.py` の `MiscTests` (今の `test_getcwd_long_path` の隣)。案: 相対パスで 1 段ずつ降りて PATH_MAX を超える cwd を作り、`os.getcwd()` が「成功する」か「`OSError` (`ENAMETOOLONG` か `ERANGE`) を投げる」ことだけを確かめ、`MemoryError` にならない・返ってくることを見る。Tier の OS (Linux は PATH_MAX が 4096) で意味のある試験にするには 4096 を超えて降りる必要がある。上限そのものの試験は `ERANGE` を返し続ける libc が要り、Tier の OS では作れない (未検証。案だけ)
- 一度も実行されない `test_getcwd_long_pathnames` (2) を直すか消すかは、別の issue にする方が査読しやすい
- NEWS: `Misc/NEWS.d/next/Library/<日時>.gh-issue-<番号>.<nonce>.rst` を `blurb` で作る。文案: ``:func:`os.getcwd` and :func:`os.getcwdb` no longer grow their buffer until memory runs out when the C ``getcwd()`` keeps failing with :data:`~errno.ERANGE` whatever the buffer size, as illumos does for a working directory longer than ``PATH_MAX``. They now raise :exc:`OSError` instead.``

### 10. 出した報告 (英語、公開の issue)

[gh-162441](https://github.com/python/cpython/issues/162441) に出した文面。再現コードは 5 節、直し方の diff は 9-1 節と同じ物を埋めてある (ここでは埋めた所を省く)。出す前に、CPython の main (`436d791c`、2026-11-22) で呼び直しの形が変わっていないことと、同じ報告が無いことを確かめ直した。Solaris 系の担当者は本文で呼んでいない。

題:

```text
os.getcwd() in a very long working directory can allocate memory without bound and end in MemoryError
```

本文:

````markdown
# Bug report

### Bug description:

In a very long working directory, `os.getcwd()` can allocate memory without bound and end in `MemoryError`.

I have only reproduced this on illumos, in a working directory longer than `PATH_MAX`. It is unlikely to be hit in common environments: Linux and macOS are not affected. From reading the kernel sources, though, it looks like it could also happen on NetBSD and OpenBSD.

This is a regression of gh-53431 (bpo-9185): it was fixed in 2.7 only, and Python 3 has had the original behaviour again since 3.5.

#### What happens

- On POSIX, `os.getcwd()` / `os.getcwdb()` (`posix_getcwd()` in `Modules/posixmodule.c`) retry the C `getcwd()` with a buffer 1024 bytes larger each time it fails with `ERANGE`.
- The only limit is `PY_SSIZE_T_MAX`.
- POSIX says `ERANGE` means the buffer is too small, so the loop normally ends after a retry or two.
- On illumos, in a working directory longer than `PATH_MAX` (1024), `getcwd()` can keep failing with `ERANGE` whatever the buffer size.
- `os.getcwd()` then keeps reallocating until memory runs out, and raises `MemoryError`.

#### How it showed up

- In our CI on OmniOS r151060 (system Python 3.13.16), one test took about 13 minutes and exhausted the VM's memory. The traceback ended in `posixpath.realpath` -> `os.getcwd()`, followed by `lost sys.stderr`.
- importlib resolves the `''` entry of `sys.path` with `os.getcwd()`. So even `python3 -c "import json"` started in such a directory ends the same way.

#### History

- gh-53431 (bpo-9185, 2010) reported the same problem on Solaris and OpenBSD. bpo-15765 (2012) reported it on NetBSD.
- Both were fixed only in 2.7: on those platforms, `getcwd()` is called once with a fixed `PATH_MAX + 2` buffer.
- gh-53492 (bpo-9246) added the growing loop to Python 3 in 2015. The 2.7 workaround was not carried over.

#### Reproducer

No dependencies. The script:

1. builds a deep directory with relative `mkdir` / `chdir`, until the cwd is longer than the target length;
2. calls `os.getcwd()` twice in a child process whose address space is capped at 512 MiB;
3. exits 1 if a call raised `MemoryError` or timed out.

<details>
<summary>getcwd_past_path_max.py</summary>

```python
(5 節の再現コード)
```

</details>

Results:

| Platform | Python | cwd length | Result | Exit |
|---|---|---|---|---|
| illumos (OmniOS r151060) | 3.13.16 | 1224 and 5043 bytes | first call succeeds, second raises `MemoryError` | 1 |
| Linux (glibc) | 3.11 / 3.13 / 3.15 | 4239 and 5043 bytes | both calls succeed | 0 |
| Linux (musl) | 3.13 | 4239 and 5043 bytes | both calls raise `OSError(ENAMETOOLONG)` | 0 |
| macOS | 3.11 / 3.13 / 3.15 | 1084 and 5104 bytes | both calls succeed | 0 |

#### Why illumos does this

From the illumos-gate source, and checked on OmniOS r151060 by calling libc `getcwd()` through ctypes:

- The kernel's `dogetcwd()` first re-reads the cached cwd string (`u_cwd`) with `pn_get()`.
- `pn_get()` only accepts strings shorter than `MAXPATHLEN`.
- Once a call has succeeded with a large enough buffer, the cached cwd is longer than `MAXPATHLEN`.
- From then on `pn_get()` fails with `ENAMETOOLONG` on every call, and the `getcwd` syscall turns that into `ERANGE` whatever the buffer size, until the process changes directory.

So the first `os.getcwd()` after a `chdir()` succeeds, and the second one never returns.

Calling libc `getcwd()` directly on OmniOS shows exactly this: right after `chdir()`, `getcwd(buf, 1 MiB)` succeeds, and the next `getcwd(buf, 1 MiB)` fails with `ERANGE`.

This is an illumos bug: it contradicts both POSIX and the illumos man page. But CPython should not turn a libc bug into unbounded memory growth, as was agreed for Solaris in gh-53431.

From the NetBSD and OpenBSD kernel sources, the same may happen there for a cwd longer than 4 * `MAXPATHLEN`. I have not checked that on a real system.

#### Possible fix

Stop growing the buffer at a fixed size (e.g. 1 MiB), and raise the `ERANGE` from the last call as `OSError`. No platform-specific code is needed.

```diff
(9-1 節の diff)
```

What I checked with this patch on main:

- With an `LD_PRELOAD` shim whose `getcwd()` always fails with `ERANGE`, the patched build raises `OSError(ERANGE)` at once instead of `MemoryError`.
- A 5043-byte cwd on Linux is still returned.
- `test_os` passes.
- I have not built the patch on illumos.

I can open a PR if this approach is acceptable.

#### Notes on the tests

No existing test reaches this code path on the affected platforms:

- `test_posix.test_getcwd_long_pathnames` was added for bpo-9185, but its body never runs. It is indented under the `return` of the `except:` clause (already noted in gh-53492 in 2013).
- `test_os.test_getcwd_long_path` uses absolute paths. On a platform whose `PATH_MAX` is 1024, it stops at `ENAMETOOLONG` from `mkdir()` before the cwd gets longer than `PATH_MAX`.

### CPython versions tested on:

3.11, 3.13, 3.15, CPython main branch

### Operating systems tested on:

Linux, macOS, Other
````

### 11. CPython 以外で同じ呼び直しをする実装 (ソースだけ。実機では動かしていない)

illumos のように `getcwd` が大きさによらず `ERANGE` を返し続ける時に、止まらなくなる実装が他にあるかをソースで見た (2026-11-22)。「止まる」は数回の呼び出しで返ること。止まらない時の終わり方は推測。

| 対象 | 版 (commit) | `ERANGE` で呼び直すか | 上限 | `ERANGE` が続いた時 |
|---|---|---|---|---|
| Rust `std::env::current_dir` | 1.100.0 (`0ef1bc38`) | する (倍にする) | 無い | 止まらない。確保の失敗で abort する見込み ([paths/unix.rs](https://github.com/rust-lang/rust/blob/0ef1bc386059596dada8fb65b50425aab2ea637a/library/std/src/sys/paths/unix.rs#L21-L46)) |
| busybox `xrealloc_getcwd_or_warn` | 1_38_0 (`fc71374d`) | する (64 バイトずつ) | 無い | 止まらない (`libbb/xgetcwd.c`) |
| libstdc++ `std::filesystem::current_path` (glibc 以外) | gcc-16.2.0 (`78d4ac73`) | する (倍にする) | 無い | 確保の失敗でエラーを返す見込み ([fs_ops.cc](https://github.com/gcc-mirror/gcc/blob/78d4ac73dd391005b895a6148cd9831e28e1208b/libstdc++-v3/src/c++17/fs_ops.cc#L735-L788)) |
| glib `g_get_current_dir` | 2.88.4 (`802d1893`) | する (倍にする) | 実質無い | 確保の失敗で abort する見込み ([gfileutils.c](https://github.com/GNOME/glib/blob/802d1893cd5f4928991b5295263f1700311a3490/glib/gfileutils.c#L3016-L3043)) |
| Go `os.Getwd` | go1.27.4 (`7b288102`) | しない (1024 バイトで 1 回) | — | 止まる。`..` を辿る方式に移る ([getwd.go](https://github.com/golang/go/blob/7b2881024c95a11ddb86663a616340aa3a88b67f/src/os/getwd.go#L36-L64)) |
| Node.js `process.cwd()` (libuv `uv_cwd`) | v26.13.1 (`e9c27764`) | しない | — | 止まる (エラーを投げる。[core.c](https://github.com/libuv/libuv/blob/840404ce8ba7cc0204be52389a6cfff9f2c90fb6/src/unix/core.c#L753-L789)) |
| Ruby `Dir.pwd` | v4.0.10 (`a704b7cd`) | build による | `getcwd(NULL, 0)` に任せる build は libc の 128 KiB。自前で倍にする build は無い | 前者は止まる ([util.c](https://github.com/ruby/ruby/blob/a704b7cd95a42cc0cf5f307137bf3aac0285b915/util.c#L526-L573)) |
| Perl `Cwd::getcwd` | v5.44.0 (`e634cc83`) | しない (固定長で 1 回) | — | 止まる |
| OpenJDK `user.dir` | jdk-27-ga (`815ff4dc`) | しない (固定長で 1 回) | — | 止まる |
| bash の `pwd`、coreutils の `pwd` (gnulib `xgetcwd`) | bash `9c465866`、coreutils v9.12 (`c0f8514d`) | しない (`getcwd(NULL, 0)` を 1 回) | libc の 128 KiB | 止まる |

- 上限なしで呼び直すのは CPython の他に Rust の標準ライブラリ、busybox、libstdc++、glib。元の原因 (illumos のカーネル) を直さない限り、これらも同じ場面で当たりうる
- illumos の libc の `getcwd(NULL, 0)` は自分で倍にして呼び直し、128 KiB で打ち切る (3-1)。libc に確保を任せる実装が止まるのはこのため

## 暫定的な結論

### 確かめたこと

- CPython の `posix_getcwd` は `ERANGE` の間、上限なしにバッファを 1024 バイトずつ大きくして引き直す。3.11.0・3.13.18・3.15.2・main で同じ (ソース)
- 2.7 には同じ現象 (Solaris・OpenBSD・NetBSD) の回避があり、3.x にループを入れた 2015 年の変更 (bpo-9246) で回避が移されなかった (commit と issue)。回避のために足された試験は一度も実行されない形のまま残っている
- illumos のカーネルは、cwd の文字列を覚えた後は `MAXPATHLEN` を超える cwd を読めず、バッファの大きさによらず `ERANGE` を返す (ソースと、OmniOS r151060 の実機。chdir の後の 1 回目だけ通る)
- illumos の system の Python 3.13.16 で、PATH_MAX を超える cwd の 2 回目の `os.getcwd()` と、そこからの `python3 -c "import json"` が `MemoryError` になる (実機)
- Linux (glibc・musl)、macOS、FreeBSD は、PATH_MAX を超える cwd で成功するか `ERANGE` 以外で失敗するので、CPython の引き直しは止まる (Linux・macOS は 3 版で実測、FreeBSD はソースと CI)
- `ERANGE` を返し続ける libc の下で、今の CPython は上限まで確保して `MemoryError` になり、上限を置く案の diff を当てた main は `OSError(ERANGE)` を返す (Linux の docker で build して確かめた)
- 既存の issue・PR に、3.x のこの現象の報告は無い
- 公開の issue が妥当 (devguide の Security policy の unsupported platform と launch conditions の段落)

### 本体の問題か

両方に原因がある。

- 引き金は illumos の `getcwd` (十分なバッファでも `ERANGE`)。POSIX と illumos 自身の man に反するので、illumos 側の不具合。illumos への報告は別の仕事 (この文書では扱わない)
- メモリを使い切るまで止まらないのは CPython 側 (libc の答えを信じて上限なしに確保する)。CPython 自身が 2010 年に同じ現象を「Python の側で回避すべき」として 2.7 で直しており (gh-53431 の議論: 「While getcwd is buggy on solaris I think it's not the correct behavior from python to get to an infinite loop and eat up the memory.」に core developer が同意)、3.x はその回避を失っている。報告は「3.x の回帰」として出せる

### 未検証のこと

| 項目 | 理由 | 確かめ方 |
|---|---|---|
| NetBSD・OpenBSD で 4096 バイトを超える cwd の時に CPython が止まらないか | 実機が無い (ソースからの推測だけ) | sockat-py の CI と同じ VM (vmactions の NetBSD / OpenBSD) で再現コードを `5000` で動かす |
| 直した版の illumos での振る舞い | illumos で CPython を build していない | `omnios-r151060-build` の image (gcc 入り) で main を build し、再現コードを動かす |
| 試験の案 (9-3) が Tier の OS で意味を持つか | 書いていない | 案を書いて Linux・macOS で 4096 を超えて降りる |

## 関連

- sockat-py の対処: `src/sockat/_sys.py` の `getcwd` (illumos では PATH_MAX のバッファで `getcwd(3C)` を 1 回)、commit `a7ecf50`・`f38e2ab`
- [前の CPython への報告 (getsockname)](https://github.com/kawaz/sockat-py/blob/main/docs/findings/2026-11-18-cpython-getsockname-widened-sockaddr.md)
- 一次資料: CPython の [posixmodule.c (main)](https://github.com/python/cpython/blob/1cc580249141838a520809c21cd971883b5b10cb/Modules/posixmodule.c#L4718-L4752)、[devguide の Security policy](https://github.com/python/devguide/blob/8c852bdd3f06b8447185fe2945af5de52a96a0ac/security/policy.rst)、[PEP 11](https://github.com/python/peps/blob/4434e728a7db24540d581f52e96570ca1230356e/peps/pep-0011.rst)、illumos-gate の [syscall/getcwd.c](https://github.com/illumos/illumos-gate/blob/ec6987948e47ca22beba393ea01162d535aa7e8f/usr/src/uts/common/syscall/getcwd.c)・[fs/lookup.c](https://github.com/illumos/illumos-gate/blob/ec6987948e47ca22beba393ea01162d535aa7e8f/usr/src/uts/common/fs/lookup.c)・[fs/pathname.c](https://github.com/illumos/illumos-gate/blob/ec6987948e47ca22beba393ea01162d535aa7e8f/usr/src/uts/common/fs/pathname.c)
