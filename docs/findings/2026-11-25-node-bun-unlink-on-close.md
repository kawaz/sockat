# Node.js と Bun が listener を閉じる時のソケットのファイルの unlink

- Date: 2026-11-25 (測定日)

Node.js (`net.createServer().listen(<パス>)`) と Bun (`node:net` の同じ API と `Bun.listen({ unix })`) が、Unix domain socket の listener を閉じる時にソケットのファイルを消すか、どのパスで消すかを実機で確かめた。

## 判明した事実

表の記号: 消える = ソケットのファイルが消えた、残る = 残った。3 つの実装 (Node の `net`、Bun の `net`、`Bun.listen`) は全ての行で同じ結果だった。差が出たのは 5 行目の「普通に終わる」だけ。

| # | 場面 | macOS Node | macOS Bun (`net`・`Bun.listen`) | Linux Node | Linux Bun (`net`・`Bun.listen`) |
|---|---|---|---|---|---|
| 1 | 普通のパスで listen、close (`Bun.listen` は `stop`) | 消える | 消える | 消える | 消える |
| 2a | ディレクトリの symlink 越し (`link/s.sock`) で listen、close の前に symlink を消す | 実ディレクトリの `s.sock` が残る | 残る | 残る | 残る |
| 2b | 同じ、symlink を別の空のディレクトリへ張り替える | 実の `s.sock` が残る。張り替え先に何も作られない | 残る (同じ) | 残る (同じ) | 残る (同じ) |
| 2c | 同じ綴りで symlink を変えずに close | 消える | 消える | 消える | 消える |
| 3 | ファイルの symlink 越し (`link.sock` → `real/s.sock`) で listen、close | listen は通る。bind は symlink を辿って `real/s.sock` を作る。close で symlink の `link.sock` が消え、実の `real/s.sock` が残る | 同じ | listen が `EADDRINUSE` で失敗する。symlink も実のファイルも触られない (実のファイルは作られない) | 同じ (`Bun.listen` は `EADDRINUSE` を throw、`net` は `error` イベント) |
| 4a | close せず `process.exit()` | 残る | 残る | 残る | 残る |
| 4b | close せず、server を `unref()` して普通に終わる | 消える | 残る | 消える | 残る |
| 4c | 4a の綴りが symlink 越し (`link/s.sock`) | 残る | 残る | 残る | 残る |
| 5 | 比べる相手 (symlink を使わない 1 と 4) | 1 は消え、4a は残り、4b は Node だけ消える | 同 (4b は残る) | 同 | 同 |

つまり、close は listen に渡したパスの文字列そのものを unlink している (2a・2b の実のファイルが残る事、3 で symlink の側が消える事から)。2c のように綴りが同じ実体を指し続けていれば、結果として実のファイルが消える。

## 実用的な示唆 / ベストプラクティス

- Node.js と Bun の close は、listen に渡したパスの文字列で unlink する。close の時点でその綴りが元のソケットのファイルに辿れなければ (綴りの途中の symlink が消えた、別の場所に張り替えられた)、実のソケットのファイルは残る
- macOS で、ファイルを指す symlink を listen に渡すと、bind は最後の symlink を辿って実の場所にソケットのファイルを作る。close は symlink の側を消し、実のファイルは残る。Linux ではこの listen が `EADDRINUSE` で失敗する
- `process.exit()` では、どの実装・OS でもソケットのファイルが残る
- close せずに普通に終わった時は、Node.js は消し、Bun は残す (macOS・Linux とも)

## 検証の詳細

### 環境

| 項目 | 中身 |
|---|---|
| macOS | macOS 26 (Darwin 25.5.0、arm64)。Node.js v26.13.1、Bun 1.4.4 |
| Linux | OrbStack の docker の `node:latest` (Node.js v26.13.1) と `oven/bun:latest` (Bun 1.4.5)。カーネル 7.2.12-orbstack-00394 |
| 実験物の置き場 | シナリオごとに `mktemp -d` したディレクトリ (macOS は `$TMPDIR` の下、Linux はコンテナの `/tmp`)。スクリプトは `$TMPDIR/w` に置き、コンテナへは `-v $TMPDIR/w:/s` で渡した |

### 指示と実物の違い

- Linux の Bun は 1.4.5 で、macOS の 1.4.4 と版が違う
- `Bun.listen` の `stop()` にはコールバックがないため、`stop(true)` の後に `setTimeout(cb, 0)` で 1 回だけ譲ってから `ls` した (時間待ちのループではない)
- 3 は「実のファイルが既にある」ケースを別には測っていない。macOS の bind は symlink を辿るため、先の listen が `real/s.sock` を作る形になっている
- 各シナリオは別プロセス。パスは相対 (`process.chdir` した後の `real/s.sock`、`link/s.sock`、`link.sock`) で渡した

### 手順

`t.mjs` が 1 つのシナリオを 1 つのプロセスで流し、listen の後・symlink の変更の後・close の後 (または終了の直前) の `lstat` を出す。`run.sh` が 8 つのシナリオを `mktemp -d` ごとに流し、終了後の最終状態を `ls -ldF` で出す。

```sh
bash run.sh node net
bash run.sh bun net
bash run.sh bun bunlisten
```

`t.mjs`:

```js
// usage: <runtime> t.mjs <impl: net|bunlisten> <scenario> <dir>
import net from "node:net";
import fs from "node:fs";
import path from "node:path";
const [impl, sc, dir] = process.argv.slice(2);
const ls = (label) => {
  console.log(`-- ${label}`);
  for (const d of [dir, path.join(dir, "real"), path.join(dir, "other")]) {
    if (!fs.existsSync(d)) continue;
    const out = fs.readdirSync(d).sort().map((n) => {
      const p = path.join(d, n); const st = fs.lstatSync(p);
      return `  ${path.relative(dir, p)} ${st.isSymbolicLink() ? "symlink->" + fs.readlinkSync(p) : st.isSocket() ? "socket" : st.isDirectory() ? "dir" : "file"}`;
    });
    console.log(out.join("\n"));
  }
};
fs.mkdirSync(path.join(dir, "real")); fs.mkdirSync(path.join(dir, "other"));
let target, before = () => {}, exitMode = "close";
switch (sc) {
  case "plain-close": target = "real/s.sock"; break;
  case "plain-exit": target = "real/s.sock"; exitMode = "exit"; break;
  case "plain-natural": target = "real/s.sock"; exitMode = "natural"; break;
  case "symdir-rm": fs.symlinkSync("real", path.join(dir, "link")); target = "link/s.sock";
    before = () => fs.unlinkSync(path.join(dir, "link")); break;
  case "symdir-repoint": fs.symlinkSync("real", path.join(dir, "link")); target = "link/s.sock";
    before = () => { fs.unlinkSync(path.join(dir, "link")); fs.symlinkSync("other", path.join(dir, "link")); }; break;
  case "symdir-close-nochange": fs.symlinkSync("real", path.join(dir, "link")); target = "link/s.sock"; break;
  case "symdir-exit": fs.symlinkSync("real", path.join(dir, "link")); target = "link/s.sock"; exitMode = "exit"; break;
  case "symfile-dangling": fs.symlinkSync("real/s.sock", path.join(dir, "link.sock")); target = "link.sock"; break;
  case "symfile-existing": // real socket made by another process first
    fs.symlinkSync("real/s.sock", path.join(dir, "link.sock")); target = "link.sock"; break;
}
process.chdir(dir);
const done = (stage) => { ls(stage); };
const onListen = (closeFn) => {
  ls("after listen");
  before();
  if (before.toString() !== "() => {}") ls("after symlink change");
  if (exitMode === "exit") { ls("(exit now)"); process.exit(); }
  else if (exitMode === "natural") { /* unref'd; process ends */ process.on("exit", () => ls("at natural exit")); }
  else closeFn(() => { ls("after close"); });
};
try {
  if (impl === "net") {
    const s = net.createServer();
    s.on("error", (e) => { console.log("ERROR", e.code, e.message); ls("after error"); });
    s.listen(target, () => {
      if (exitMode === "natural") s.unref();
      onListen((cb) => s.close(cb));
    });
  } else {
    const l = Bun.listen({ unix: target, socket: { data() {} } });
    queueMicrotask(() => { if (exitMode === "natural") l.unref();
      onListen((cb) => { l.stop(true); setTimeout(cb, 0); }); }); // setTimeout: stop() has no callback
  }
} catch (e) { console.log("THROW", e.code, e.message); ls("after throw"); }
```

`run.sh`:

```sh
rt=$1; impl=$2
for sc in plain-close plain-exit plain-natural symdir-rm symdir-repoint symdir-close-nochange symdir-exit symfile-dangling; do
  d=$(mktemp -d); echo "=== $rt $impl $sc"; $rt t.mjs $impl $sc $d 2>&1 | grep -v '^$'; echo "[exit=${PIPESTATUS[0]}]"
  echo "-- final (find)"; (cd $d; find real other link link.sock -maxdepth 1 \( -name 's.sock' -o -name link -o -name link.sock \) -exec ls -ldF {} \; 2>/dev/null | awk '{print "  "$1, $(NF-2), $(NF-1), $NF}')
  rm -rf $d
done
```

Linux は `run.sh` の `cd`・スクリプトのパス・`awk` の列だけを変えた版 (`/s` にマウント) を、`docker run --rm -v $TMPDIR/w:/s <イメージ> bash /s/runl.sh <実行系> <実装>` で流した。

### 決め手になった実出力

macOS・Node.js、2a (symlink を消してから close):

```
=== node net symdir-rm
-- after listen
  link symlink->real
  other dir
  real dir
  real/s.sock socket
-- after symlink change
  other dir
  real dir
  real/s.sock socket
-- after close
  other dir
  real dir
  real/s.sock socket
-- final (find)
  srwx------ 25 08:41 real/s.sock=
```

macOS・Node.js、2b (別ディレクトリへ張り替え。`other` には何も作られない):

```
-- after symlink change
  link symlink->other
  other dir
  real dir
  real/s.sock socket
-- after close
  link symlink->other
  other dir
  real dir
  real/s.sock socket
```

macOS・Node.js、3 (ファイルの symlink):

```
=== node net symfile-dangling
-- after listen
  link.sock symlink->real/s.sock
  other dir
  real dir
  real/s.sock socket
-- after close
  other dir
  real dir
  real/s.sock socket
```

Linux・Node.js、3:

```
=== node net symfile-dangling
ERROR EADDRINUSE listen EADDRINUSE: address already in use link.sock
-- final (find)
  lrwxrwxrwx real/s.sock
```

Linux・Bun の `Bun.listen`、3:

```
THROW EADDRINUSE Failed to listen at link.sock
```

4b (close せず `unref()` して普通に終わる) の最終状態: macOS・Node.js と Linux・Node.js は `final (find)` が空 (消えた)。macOS・Bun と Linux・Bun は `srwx------ ... real/s.sock=` (macOS) / `srwxr-xr-x real/s.sock=` (Linux) が残った。

## 未確認

- Windows
- `Bun.listen` の `stop(false)` (接続が残る場合の閉じ方)。`stop(true)` だけ測った
- 接続中のクライアントがいる状態での close
- Node.js と Bun の別の版。Linux・macOS のそれぞれで 1 つの版だけ
- 実のファイルを別のプロセスが先に作っていた状態での 3 (macOS)
- 4b で Node.js が消す仕組み (実装のどこで unlink しているか) は読んでいない。観測だけ
