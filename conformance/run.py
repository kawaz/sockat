#!/usr/bin/env python3
"""sockat の適合試験を流す。

決まりの正本は docs/design/conformance.md。場面 (cases.json) ごとに環境を作り、
各言語の試験用 CLI (langs.json) を起こし、結果と CLI の後の状態を言語どうしと
expect で比べる。差があれば場面 x 言語の表を出して終了コード 1。
`linux` の条件を持つ場面は docker の Linux コンテナの中で条件を作って流す。

    python3 -I conformance/run.py [--langs rs,py,go] [--case NAME[,NAME...]] [--on all|host|linux] [--keep]

標準ライブラリだけで書く (どの言語のリポにも依らずに流せるように)。
"""

import argparse
import ctypes
import errno
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
CONFORMANCE = HUB / "conformance"

# Linux の場面を流すコンテナ。rs の Linux 向けの CLI を作るイメージと同じにする (glibc をそろえるため。
# langs.json の rs の linux.build もこれを使う)。python3 (3.11 以上) が入っていて、run.py と py の CLI もこれで動く。
LINUX_IMAGE = "rust:1"
# 各言語の Linux 向けの CLI を置く docker の volume。コンテナの中では /out (読み取り専用)。
LINUX_OUT_VOLUME = "sockat-conformance-out"
# コンテナの中の置き場。tmpfs にし、TMPDIR に向ける (場面の {root} 等はこの下。/tmp を書けなくしても巻き込まない)。
LINUX_WORK = "/work"
LINUX_HUB = "/hub/conformance"
LINUX_LANGS = "/langs"
# seccomp の条件 -> (docker run のオプション, コンテナの中の prctl(PR_GET_SECCOMP) の期待値)。
SECCOMP = {
    "default": ([], 2),
    "unconfined": (["--security-opt", "seccomp=unconfined"], 0),
    "kill-unshare": (["--security-opt", f"seccomp={CONFORMANCE / 'linux' / 'seccomp-kill-unshare.json'}"], 2),
}
# 書けなくする場所に書ける placeholder (それ以外は絶対パス)。
READONLY_PLACEHOLDERS = ("{tmpdir}", "{xdg}", "{root}", "{long}")
MS_RDONLY, MS_REMOUNT, MS_BIND = 1, 32, 4096
PR_GET_SECCOMP = 21

# {long} はパス全体がこのバイト数以上になるまで深くする。
# sun_path (macOS 104、Linux 108) を超え、ファイル名を足しても PATH_MAX には遠い長さ。
LONG_MIN_BYTES = 150
LONG_SEGMENT = "d" * 16

# CLI が返ってこない時に打ち切るまでの秒数。CLI の 1 回の bind / connect は即座に終わるので、
# これに当たるのは CLI が固まった時だけ (その言語は「壊れた」として表に出す)。
CLI_TIMEOUT_SEC = 120

FIELDS = ["ok", "error", "route", "base", "spelling", "skipped", "file", "created", "left", "residue", "received"]
CLI_FIELDS = {"ok": bool, "error": (str, type(None)), "route": (str, type(None)), "base": (str, type(None)),
              "spelling": (dict, type(None)), "skipped": list}
# 綴りの性質 (SPEC の Spelling) を JSON にした形。kind ごとに持つ属性と、その型。
SPELLING_ATTRS = {
    "Original": {},
    "CwdRelative": {},
    "Linked": {"removable": bool, "until": str, "usable_cross_uid": bool, "usable_with_private_tmp": bool},
    "Dangling": {},
}
SPELLING_UNTIL = ("Process", "Cleanup")

# 置き場の中の B の名前 (SPEC-routes の「B の作り方」)。<uid> と乱数の部分は表示で記号に置き換える。
B_NAME_TMP = re.compile(r"^sockat-(\d+)$")
B_NAME_RUNTIME = "sockat"
B_NAME_SOCKDIR = re.compile(r"^\.sockat\.[0-9A-Za-z]{10}$")
# /tmp の中で、スクリプトが作る物 ({short} の symlink)。
SHORT_PREFIX = "sockat-conformance-"

# 待ち受けの手伝い。ソケットのディレクトリに chdir してファイル名だけで bind する (sockat に頼らない)。
# listen: listen して "ready" を出し、標準入力が閉じられたら (= CLI が終わったら)、届いていた接続を 1 つ
#         受けて中身を JSON で出す。
# stale:  bind してすぐ閉じる (ファイルだけ残る、誰も listen していないソケット)。
HELPER = r"""
import json, os, select, socket, sys
directory, name, mode = sys.argv[1:4]
os.chdir(directory)
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.bind(name)
if mode == "stale":
    s.close()
    sys.exit(0)
s.listen(8)
print("ready", flush=True)
select.select([sys.stdin], [], [])
sys.stdin.read()
got = b""
readable, _, _ = select.select([s], [], [], 0)
if readable:
    c, _ = s.accept()
    while True:
        b = c.recv(64)
        if not b:
            break
        got += b
    c.close()
s.close()
print(json.dumps({"received": got.decode("latin-1")}), flush=True)
"""


class SetupError(Exception):
    pass


def fail_usage(msg):
    print(f"run.py: {msg}", file=sys.stderr)
    sys.exit(2)


def load_cases():
    cases = json.loads((CONFORMANCE / "cases.json").read_text(encoding="utf-8"))
    names = set()
    for c in cases:
        for key in ("name", "op", "path", "cwd", "setup", "expect"):
            if key not in c:
                fail_usage(f"cases.json: 場面 {c.get('name')!r} に {key} が無い")
        if c["op"] not in ("bind", "connect"):
            fail_usage(f"cases.json: 場面 {c['name']!r} の op は bind か connect")
        if not isinstance(c.get("usable_cross_uid", False), bool):
            fail_usage(f"cases.json: 場面 {c['name']!r} の usable_cross_uid は true か false")
        b = c.get("base")
        if b is not None and not (isinstance(b, str) and (b.startswith("/") or b.startswith("{"))):
            fail_usage(f"cases.json: 場面 {c['name']!r} の base は絶対パスか placeholder で始めたパス")
        unknown = set(c["expect"]) - set(FIELDS)
        if unknown:
            fail_usage(f"cases.json: 場面 {c['name']!r} の expect に知らない項目 {sorted(unknown)}")
        if c["name"] in names:
            fail_usage(f"cases.json: 場面の名前 {c['name']!r} が重複")
        names.add(c["name"])
        if "linux" in c:
            check_linux_conditions(c)
    return cases


def check_linux_conditions(c):
    where = f"cases.json: 場面 {c['name']!r} の linux"
    lx = c["linux"]
    if not isinstance(lx, dict):
        fail_usage(f"{where} はオブジェクト")
    unknown = set(lx) - {"seccomp", "proc", "readonly"}
    if unknown:
        fail_usage(f"{where} に知らない項目 {sorted(unknown)}")
    if lx.get("seccomp") not in SECCOMP:
        fail_usage(f"{where} の seccomp は {' か '.join(SECCOMP)}")
    if not isinstance(lx.get("proc", True), bool):
        fail_usage(f"{where} の proc は true か false")
    ro = lx.get("readonly", [])
    if not isinstance(ro, list) or not all(isinstance(p, str) for p in ro):
        fail_usage(f"{where} の readonly はパスの並び")
    for p in ro:
        if not (p.startswith("/") or any(p == h or p.startswith(h + "/") for h in READONLY_PLACEHOLDERS)):
            fail_usage(f"{where} の readonly {p!r} は絶対パスか {', '.join(READONLY_PLACEHOLDERS)} で始める")
    # 書けなくする・/proc を隠すには SYS_ADMIN が要り、docker は SYS_ADMIN を足すと既定の seccomp の
    # profile を緩める (unshare が通る)。default のまま組むと「既定の seccomp」でなくなるので断る。
    if lx["seccomp"] == "default" and (ro or not lx.get("proc", True)):
        fail_usage(f"{where}: seccomp の default は proc・readonly と組めない (SYS_ADMIN で profile が緩むため。kill-unshare を使う)")


def load_langs():
    langs = json.loads((CONFORMANCE / "langs.json").read_text(encoding="utf-8"))
    for name, spec in langs.items():
        lacks = spec.get("lacks") if isinstance(spec, dict) else None
        if not isinstance(lacks, list) or not all(isinstance(r, str) for r in lacks):
            fail_usage(f"langs.json: 言語 {name!r} の lacks は経路の名前の並び")
        lx = spec.get("linux")
        if lx is not None:
            if not isinstance(lx, dict) or set(lx) - {"cmd", "build"}:
                fail_usage(f"langs.json: 言語 {name!r} の linux は cmd と build のオブジェクト")
            for key in ("cmd", "build"):
                v = lx.get(key)
                if v is not None and (not isinstance(v, list) or not all(isinstance(a, str) for a in v)):
                    fail_usage(f"langs.json: 言語 {name!r} の linux.{key} は文字列の並びか null")
    return langs


class Env:
    """1 つの場面 x 1 つの言語の環境。言語ごとに作り直す (bind がファイルを残すので)。"""

    def __init__(self, base):
        self.case_dir = Path(tempfile.mkdtemp(prefix="case.", dir=base))
        self.root = self.case_dir / "root"
        self.tmp = self.case_dir / "tmp"
        self.xdg = self.case_dir / "xdg"
        self.root.mkdir()
        self.tmp.mkdir()
        self.xdg.mkdir(mode=0o700)
        # {long} は必ず {root} から 1 段以上降りる ($TMPDIR が深いと {root} だけで長さを満たし、
        # {long} が既にある {root} と同じになって「ディレクトリが無い」場面が作れなくなるため)。
        long = self.root / LONG_SEGMENT
        while len(os.fsencode(str(long))) < LONG_MIN_BYTES:
            long = long / LONG_SEGMENT
        self.long = long
        # {short}: {root} を指す /tmp の短い symlink。{root} は $TMPDIR の下で長くなりうるので、
        # 短い絶対パスの場面はこれを通す (名前は /tmp の sockat.* の残骸の確かめに掛からない形)。
        while True:
            short = Path("/tmp") / f"{SHORT_PREFIX}{secrets.token_hex(4)}"
            try:
                os.symlink(self.root, short)
                break
            except FileExistsError:
                continue
        self.short = short
        self.listeners = []

    def subst(self, s):
        return (s.replace("{long}", str(self.long))
                 .replace("{root}", str(self.root))
                 .replace("{short}", str(self.short))
                 .replace("{tmpdir}", str(self.tmp))
                 .replace("{xdg}", str(self.xdg)))

    def render(self, p):
        """スクリプトが作った場所を placeholder に戻す (言語ごとに場所が違っても比べられるように)。
        symlink の先は実パスで書かれうるので、実パスの形も戻す。"""
        p = str(p)
        pairs = []
        for d, name in ((self.long, "{long}"), (self.root, "{root}"), (self.tmp, "{tmpdir}"), (self.xdg, "{xdg}")):
            pairs.append((str(d), name))
            if os.path.realpath(d) != str(d):
                pairs.append((os.path.realpath(d), name))
        for prefix, name in sorted(pairs, key=lambda x: -len(x[0])):
            if p == prefix or p.startswith(prefix + "/"):
                return name + p[len(prefix):]
        return p

    def resolve(self, cwd, p):
        return p if os.path.isabs(p) else os.path.join(cwd, p)

    def run_setup(self, cwd, steps):
        for step in steps:
            parts = self.subst(step).split()
            if not parts:
                raise SetupError(f"空の setup: {step!r}")
            verb, args = parts[0], [self.resolve(cwd, a) for a in parts[1:]]
            if verb == "mkdir" and len(args) == 1:
                os.makedirs(args[0], exist_ok=True)
            elif verb == "touch" and len(args) == 1:
                with open(args[0], "a"):
                    pass
            elif verb in ("listen", "stale-socket") and len(args) == 1:
                self.start_helper(args[0], "listen" if verb == "listen" else "stale")
            else:
                raise SetupError(f"知らない setup: {step!r}")

    def start_helper(self, path, mode):
        directory, name = os.path.split(path)
        proc = subprocess.Popen([sys.executable, "-I", "-c", HELPER, directory, name, mode],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if mode == "stale":
            _, err = proc.communicate()
            if proc.returncode != 0:
                raise SetupError(f"stale-socket {path} に失敗: {err.strip()}")
            return
        line = proc.stdout.readline()
        if line.strip() != "ready":
            proc.kill()
            _, err = proc.communicate()
            raise SetupError(f"listen {path} に失敗: {err.strip()}")
        self.listeners.append(proc)

    def collect_received(self):
        """待ち受けに届いた中身。待ち受けが無い場面は None。"""
        if not self.listeners:
            return None
        got = ""
        for proc in self.listeners:
            out, err = proc.communicate(input="")
            if proc.returncode != 0:
                raise SetupError(f"待ち受けが失敗した: {err.strip()}")
            got += json.loads(out.strip().splitlines()[-1])["received"]
        self.listeners = []
        return got

    def tree(self):
        entries = set()
        for dirpath, dirnames, filenames in os.walk(self.root):
            for n in dirnames + filenames:
                entries.add(os.path.join(dirpath, n))
        return entries

    def cleanup(self, keep):
        for proc in self.listeners:
            proc.kill()
            proc.communicate()
        try:
            os.unlink(self.short)
        except FileNotFoundError:
            pass
        if not keep:
            shutil.rmtree(self.case_dir, ignore_errors=True)


class Conditions:
    """コンテナの中で CLI の間だけ作る条件 (書けなくする場所、/proc を隠す)。seccomp は docker run で掛ける。

    mount はコンテナの mount 名前空間全体に効くので、CLI が終わったら release で外す
    (待ち受けの手伝いや残骸の確かめは条件の外で動く)。
    """

    def __init__(self, env, linux):
        self.readonly = [env.subst(p) for p in linux.get("readonly", [])]
        self.hide_proc = not linux.get("proc", True)
        self.mounted = []
        self.libc = ctypes.CDLL(None, use_errno=True)

    def _mount(self, src, target, fstype, flags, data):
        enc = lambda s: None if s is None else os.fsencode(s)
        if self.libc.mount(enc(src), enc(target), enc(fstype), ctypes.c_ulong(flags), enc(data)) != 0:
            e = ctypes.get_errno()
            raise SetupError(f"mount {target} に失敗: {os.strerror(e)}")

    def apply(self):
        # 書けなくする方を先に (後で隠す /proc に頼らないが、順を決めておく)。
        for p in self.readonly:
            self._mount(p, p, None, MS_BIND, None)
            self.mounted.append(p)
            self._mount(None, p, None, MS_BIND | MS_REMOUNT | MS_RDONLY, None)
        if self.hide_proc:
            self._mount("sockat-noproc", "/proc", "tmpfs", MS_RDONLY, "size=4k")
            self.mounted.append("/proc")
        # 条件が本当に効いているかを確かめる (経路の名前に依らず、環境だけを見る)。
        for p in self.readonly:
            probe = os.path.join(p, ".conformance-probe")
            try:
                os.mkdir(probe)
            except OSError as e:
                if e.errno != errno.EROFS:
                    raise SetupError(f"{p} を書けなくできたか確かめられない: {e}")
            else:
                os.rmdir(probe)
                raise SetupError(f"{p} がまだ書ける")
        if self.hide_proc and os.path.exists("/proc/self"):
            raise SetupError("/proc がまだ見える")

    def release(self):
        for p in reversed(self.mounted):
            if self.libc.umount2(os.fsencode(p), 0) != 0:
                raise SetupError(f"umount {p} に失敗: {os.strerror(ctypes.get_errno())}")
        self.mounted = []


def seccomp_mode():
    return ctypes.CDLL(None, use_errno=True).prctl(PR_GET_SECCOMP, 0, 0, 0, 0)


def walk_all(top):
    """top の中の全部のパス (top 自身は含まない)。symlink は辿らない。"""
    out = set()
    for dirpath, dirnames, filenames in os.walk(top):
        for n in dirnames + filenames:
            out.add(os.path.join(dirpath, n))
    return out


class Places:
    """CLI の前後で、置き場とソケットのディレクトリに増えた物を見る。

    B の中に増えた物 (D と E) は left、B の外に増えた物は residue に分ける。{root} の木の中で B の外に
    増えた物は created (ソケットのファイル等) で、run_one が別に見る。
    """

    def __init__(self, env, sockdir, base):
        self.env = env
        self.sockdir = sockdir
        self.base = base

    def b_dirs(self):
        """今ある B の (実パス, 表示)。"""
        out = []
        env = self.env
        try:
            for n in os.listdir("/tmp"):
                if B_NAME_TMP.match(n):
                    out.append((os.path.join("/tmp", n), "/tmp/sockat-<uid>"))
        except OSError:
            pass
        for n in os.listdir(env.tmp):
            if B_NAME_TMP.match(n):
                out.append((str(env.tmp / n), "{tmpdir}/sockat-<uid>"))
        if os.path.isdir(env.xdg / B_NAME_RUNTIME):
            out.append((str(env.xdg / B_NAME_RUNTIME), "{xdg}/" + B_NAME_RUNTIME))
        if self.sockdir and os.path.isdir(self.sockdir):
            for n in os.listdir(self.sockdir):
                if B_NAME_SOCKDIR.match(n):
                    out.append((os.path.join(self.sockdir, n), env.render(self.sockdir) + "/.sockat.<rand>"))
        if self.base and os.path.isdir(self.base):
            out.append((self.base, env.render(self.base)))
        return out

    def snapshot(self):
        """(B の中の全部, B の外の、置き場の直下の全部)。/tmp は sockat の名前の物だけを見る。"""
        inside = set()
        bs = self.b_dirs()
        for b, _ in bs:
            inside |= walk_all(b)
        outside = set()
        try:
            outside |= {os.path.join("/tmp", n) for n in os.listdir("/tmp")
                        if n.startswith("sockat") and not n.startswith(SHORT_PREFIX)}
        except OSError:
            pass
        outside |= {str(self.env.tmp / n) for n in os.listdir(self.env.tmp)}
        outside |= {str(self.env.xdg / n) for n in os.listdir(self.env.xdg)}
        outside -= {b for b, _ in bs}
        return inside, outside

    def diff(self, before):
        """(left, residue, 増えた B の中の物の実パス)。"""
        inside, outside = self.snapshot()
        new_inside = sorted(inside - before[0])
        left = []
        for b, shown in self.b_dirs():
            for p in new_inside:
                if p.startswith(b + "/"):
                    left.append(self.render_left(shown, os.path.relpath(p, b), p))
        residue = sorted(self.env.render(p) for p in outside - before[1])
        return sorted(left), residue, new_inside

    def render_left(self, shown, rel, p):
        parts = rel.split("/")
        if os.path.islink(p):
            target = self.env.render(os.readlink(p))
            if len(parts) == 1:
                return f"{shown}/<E> -> {target}"
            if len(parts) == 2:
                return f"{shown}/<D>/<E> -> {target}"
        elif os.path.isdir(p) and len(parts) == 1:
            return f"{shown}/<D>/"
        return f"{shown}/{rel}"

    @staticmethod
    def remove(paths):
        """B の中に増えた物を消す (B は残す。/tmp の B に場面ごとの D が溜まらないように)。"""
        for p in sorted(paths, key=len, reverse=True):
            try:
                if os.path.islink(p) or not os.path.isdir(p):
                    os.unlink(p)
                else:
                    shutil.rmtree(p, ignore_errors=True)
            except OSError:
                pass


def is_socket(path):
    try:
        return stat.S_ISSOCK(os.lstat(path).st_mode)
    except (OSError, ValueError):
        return False


def lang_command(spec):
    """CLI の argv か、起こせない理由の文字列。"""
    if not isinstance(spec, dict) or spec.get("cmd") is None:
        return "langs.json に cmd が無い"
    repo = (HUB / spec.get("cwd", ".")).resolve()
    if not repo.is_dir():
        return f"リポが無い: {repo}"
    cmd = [str(a).replace("{repo}", str(repo)) for a in spec["cmd"]]
    if not cmd:
        return "langs.json の cmd が空"
    if "/" in cmd[0] and not os.path.isabs(cmd[0]):
        cmd[0] = str(repo / cmd[0])
    return cmd


def validate_cli_output(stdout):
    try:
        out = json.loads(stdout)
    except json.JSONDecodeError as e:
        return None, f"出力が JSON でない ({e})"
    if not isinstance(out, dict):
        return None, "出力が JSON のオブジェクトでない"
    for key, typ in CLI_FIELDS.items():
        if key not in out:
            return None, f"出力に {key} が無い"
        if not isinstance(out[key], typ):
            return None, f"出力の {key} の型が違う: {out[key]!r}"
    if not all(isinstance(x, str) for x in out["skipped"]):
        return None, f"出力の skipped が文字列の並びでない: {out['skipped']!r}"
    sp = out["spelling"]
    if sp is not None:
        attrs = SPELLING_ATTRS.get(sp.get("kind"))
        if attrs is None:
            return None, f"出力の spelling.kind が {' / '.join(SPELLING_ATTRS)} でない: {sp!r}"
        if set(sp) != {"kind"} | set(attrs):
            return None, f"出力の spelling の項目が kind {sp['kind']} の形と違う: {sp!r}"
        for key, typ in attrs.items():
            if not isinstance(sp[key], typ):
                return None, f"出力の spelling.{key} の型が違う: {sp!r}"
        if sp["kind"] == "Linked" and sp["until"] not in SPELLING_UNTIL:
            return None, f"出力の spelling.until が {' / '.join(SPELLING_UNTIL)} でない: {sp!r}"
    return out, None


def run_one(case, argv, base, keep):
    """1 つの場面を 1 つの言語で流す。戻り値は {"status": "result"|"broken"|"unimplemented", ...}。"""
    env = Env(base)
    try:
        cwd = env.subst(case["cwd"])
        path = env.subst(case["path"])
        base = env.subst(case["base"]) if case.get("base") is not None else None
        places = Places(env, os.path.dirname(env.resolve(cwd, path)), base)
        try:
            env.run_setup(cwd, case["setup"])
        except (SetupError, OSError) as e:
            return {"status": "setup-error", "message": str(e)}
        child_env = dict(os.environ)
        child_env["TMPDIR"] = str(env.tmp)
        child_env["XDG_RUNTIME_DIR"] = str(env.xdg)
        child_env["PWD"] = cwd
        before_tree = env.tree()
        before_places = places.snapshot()
        conditions = Conditions(env, case["linux"]) if "linux" in case else None
        try:
            try:
                if conditions:
                    conditions.apply()
                request = {"op": case["op"], "path": path}
                if "usable_cross_uid" in case:
                    request["usable_cross_uid"] = case["usable_cross_uid"]
                if base is not None:
                    request["base"] = base
                proc = subprocess.run(argv, input=json.dumps(request),
                                      cwd=cwd, env=child_env, umask=0o022, capture_output=True,
                                      text=True, timeout=CLI_TIMEOUT_SEC)
            finally:
                if conditions:
                    conditions.release()
        except SetupError as e:
            return {"status": "setup-error", "message": str(e)}
        except (FileNotFoundError, PermissionError) as e:
            return {"status": "unimplemented", "message": f"起こせない: {e}"}
        except subprocess.TimeoutExpired:
            return {"status": "broken", "message": f"{CLI_TIMEOUT_SEC} 秒で終わらない"}
        try:
            received = env.collect_received()
        except SetupError as e:
            return {"status": "setup-error", "message": str(e)}
        if proc.returncode < 0:
            return {"status": "broken", "message": f"シグナル {-proc.returncode} で終わった: {proc.stderr.strip()[-500:]}"}
        if proc.returncode != 0:
            return {"status": "broken", "message": f"終了コード {proc.returncode}: {proc.stderr.strip()[-500:]}"}
        out, err = validate_cli_output(proc.stdout)
        if err:
            return {"status": "broken", "message": f"{err}: {proc.stderr.strip()[-500:]}"}
        left, residue, new_in_b = places.diff(before_places)
        b_paths = {b for b, _ in places.b_dirs()}
        created = sorted(env.render(p) for p in env.tree() - before_tree
                         if p not in b_paths and not any(p.startswith(b + "/") for b in b_paths))
        Places.remove(new_in_b)
        result = {
            "ok": out["ok"],
            "error": out["error"],
            "route": out["route"],
            "base": out["base"],
            "spelling": out["spelling"],
            "skipped": out["skipped"],
            "file": is_socket(env.resolve(cwd, path)),
            "created": created,
            "left": left,
            "residue": residue,
            "received": received,
        }
        return {"status": "result", "result": result}
    finally:
        env.cleanup(keep)


def implicit_expect(case, result):
    """docs/design/conformance.md の「スクリプトが確かめること」を、場面の expect に無くても確かめる。"""
    exp = {"residue": []}
    if result["ok"] and case["op"] == "bind":
        exp["file"] = True
    if result["ok"] and case["op"] == "connect" and result["received"] is not None:
        exp["received"] = "x"
    if not result["ok"] or case["op"] == "connect":
        exp["spelling"] = None
    if case["op"] == "connect":
        exp["left"] = []
        exp["base"] = None
    exp.update(case["expect"])
    return exp


def rule_violations(case, result):
    """値が場面によらず 1 つに決まらないが、満たすべき決まり。戻り値は {項目: 期待の説明} (破った物だけ)。"""
    out = {}
    sp = result["spelling"]
    if case["op"] == "bind" and result["ok"]:
        es = [x for x in result["left"] if "<E> -> " in x]
        if sp is not None and sp["kind"] == "Linked" and len(es) != 1:
            out["left"] = "Linked の bind は E を 1 つ残す"
        if sp is not None and sp["kind"] in ("Original", "CwdRelative", "Dangling") and es:
            out["left"] = f"{sp['kind']} の bind は E を残さない"
    if case.get("usable_cross_uid") and sp is not None and sp["kind"] == "Linked" and not sp["usable_cross_uid"]:
        out["spelling"] = "usable_cross_uid を指定した bind は Linked なら usable_cross_uid が true"
    return out


def lack_groups(outcomes, lacks):
    """比べる組。ある言語の route が別の言語の lacks に入っている場面だけ組を分ける。

    戻り値: (組の並び, 組分けのきっかけになった経路の集まり)。分けない時は全言語で 1 組。
    組は「lacks のうちきっかけの経路に当たる部分」が同じ言語どうし (それ以外の作れない経路は
    この場面の結果に効かないので、組を分ける理由にしない)。
    """
    results = {l: o["result"] for l, o in outcomes.items() if o["status"] == "result"}
    used = {r["route"] for l, r in results.items()
            if any(r["route"] in lacks[m] for m in results if m != l)}
    if not used:
        return [set(results)], used
    groups = {}
    for l in results:
        groups.setdefault(frozenset(lacks[l] & used), set()).add(l)
    return list(groups.values()), used


def odd_in(encoded):
    """値の並びで、多数派と違う言語。多数派が決まらなければ全部。"""
    distinct = set(encoded.values())
    if len(distinct) <= 1:
        return set()
    counts = {v: list(encoded.values()).count(v) for v in distinct}
    top = max(counts.values())
    majority = [v for v, n in counts.items() if n == top]
    if len(majority) == 1 and top > 1:
        return {l for l, v in encoded.items() if v != majority[0]}
    return set(encoded)


def judge(case, outcomes, lacks):
    """場面の判定。戻り値: (言語ごとの状態, 項目ごとの詳細の行, 分けた組 (分けなければ None))。

    組を分けた時、場面の expect はきっかけの経路を作れる言語にだけ当て、作れない言語には
    暗黙の期待と「作れないきっかけの経路が skipped に入っている」ことを当てる。
    自分の lacks に入った経路を route にした言語は、どの場面でも期待違い。
    """
    cells = {}
    detail = {}
    results = {l: o["result"] for l, o in outcomes.items() if o["status"] == "result"}
    for lang, o in outcomes.items():
        if o["status"] == "unimplemented":
            cells[lang] = "未実装"
        elif o["status"] == "broken":
            cells[lang] = "壊れた"
        elif o["status"] == "setup-error":
            cells[lang] = "準備失敗"
        else:
            cells[lang] = "一致"
    groups, used = lack_groups(outcomes, lacks)
    expects = {}
    for l, r in results.items():
        if lacks[l] & used:
            expects[l] = implicit_expect({**case, "expect": {}}, r)
        else:
            expects[l] = implicit_expect(case, r)
    for field in FIELDS:
        values = {l: r[field] for l, r in results.items()}
        encoded = {l: json.dumps(v, ensure_ascii=False) for l, v in values.items()}
        odd = set()
        for g in groups:
            odd |= odd_in({l: encoded[l] for l in g})
        for l in odd:
            if cells[l] == "一致":
                cells[l] = "差"
        mismatch = set()
        exp_values = set()
        for l, r in results.items():
            exp = expects[l]
            if field in exp:
                exp_values.add(json.dumps(exp[field], ensure_ascii=False))
                if r[field] != exp[field]:
                    mismatch.add(l)
            if field == "route" and r["route"] in lacks[l]:
                exp_values.add(f"{l} の lacks に無い経路")
                mismatch.add(l)
            rule = rule_violations(case, r).get(field)
            if rule:
                exp_values.add(f"{l}: {rule}")
                mismatch.add(l)
            missing = lacks[l] & used
            if field == "skipped" and missing:
                exp_values.add(f"{l}: {' と '.join(sorted(missing))} を含む")
                if not missing <= set(r["skipped"]):
                    mismatch.add(l)
        for l in mismatch:
            cells[l] = "期待違い"
        if odd or mismatch:
            detail[field] = (encoded, odd, mismatch, exp_values)
    if used:
        # きっかけの経路に来るまでの経過は、組によらず同じはず。組をまたいで比べる。
        encoded = {l: json.dumps(skipped_before(r["skipped"], used), ensure_ascii=False) for l, r in results.items()}
        odd = odd_in(encoded)
        for l in odd:
            if cells[l] == "一致":
                cells[l] = "差"
        if odd:
            detail[SKIPPED_BEFORE] = (encoded, odd, set(), set())
    return cells, detail, (groups if used else None)


# 詳細の表で、組をまたいで比べた「きっかけの経路より前の skipped」の行の名前。
SKIPPED_BEFORE = "skipped (きっかけより前、組をまたいで)"


def skipped_before(skipped, used):
    """skipped のうち、最初のきっかけの経路より前。きっかけの経路を作れずに skipped に入れた言語は
    そこで切り、作れて route にした言語は skipped 全部 (どれも route より前に試したもの)。"""
    for i, r in enumerate(skipped):
        if r in used:
            return skipped[:i]
    return list(skipped)


def width(s):
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def pad(s, n):
    return s + " " * max(0, n - width(s))


def print_table(rows, header):
    widths = [max(width(r[i]) for r in [header] + rows) for i in range(len(header))]
    for r in [header] + rows:
        print("  ".join(pad(c, w) for c, w in zip(r, widths)).rstrip())


def build_cmd(build, repo):
    """build の argv を、{repo} を手元のリポの場所にして走らせる。失敗したら終了コード 1 で止める。"""
    build = [a.replace("{repo}", str(repo)) for a in build]
    r = subprocess.run(build, cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        print(f"build に失敗した ({' '.join(build)})\n{r.stderr[-2000:]}", file=sys.stderr)
        sys.exit(1)


def lang_repo(spec):
    repo = (HUB / spec["cwd"]).resolve() if spec.get("cwd") else None
    return repo if repo is not None and repo.is_dir() else None


def linux_command(lang, spec):
    """コンテナの中の CLI の argv か、起こせない理由の文字列。{repo} はコンテナの中のリポの場所。"""
    lx = spec.get("linux") or {}
    if lx.get("cmd") is None:
        return "langs.json に linux.cmd が無い"
    if lang_repo(spec) is None:
        return f"リポが無い: {(HUB / spec.get('cwd', '.')).resolve()}"
    cmd = [a.replace("{repo}", f"{LINUX_LANGS}/{lang}") for a in lx["cmd"]]
    return cmd or "langs.json の linux.cmd が空"


def prepare_linux(langs, build):
    """Linux の場面を流せるようにする。戻り値は飛ばす理由 (流せる時は None)。

    docker が無い・動かない・コンテナのイメージを取れない時は飛ばす (失敗にしない)。
    イメージがあって各言語の Linux 向けの build が失敗した時は、コードの誤りでありうるので止める。
    """
    if shutil.which("docker") is None:
        return "docker が無い"
    try:
        r = subprocess.run(["docker", "info", "--format", "{{.OSType}}"], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return "docker が応えない"
    if r.returncode != 0:
        return f"docker が動いていない: {r.stderr.strip()[-300:]}"
    if r.stdout.strip() != "linux":
        return f"docker が Linux のコンテナを動かせない (OSType: {r.stdout.strip()})"
    if subprocess.run(["docker", "image", "inspect", LINUX_IMAGE], capture_output=True).returncode != 0:
        r = subprocess.run(["docker", "pull", "-q", LINUX_IMAGE], capture_output=True, text=True)
        if r.returncode != 0:
            return f"イメージ {LINUX_IMAGE} を取れない: {r.stderr.strip()[-300:]}"
    if build:
        for l, spec in langs.items():
            b = (spec.get("linux") or {}).get("build")
            repo = lang_repo(spec)
            if b and isinstance(linux_command(l, spec), list) and repo is not None:
                print(f"{l}: Linux 向けの CLI を作る", file=sys.stderr)
                build_cmd(b, repo)
    return None


def run_linux_case(case, commands, langs):
    """1 つの場面を、条件を作ったコンテナの中で全言語流す。戻り値は言語ごとの outcome。"""
    lx = case["linux"]
    runnable = {l: c for l, c in commands.items() if isinstance(c, list)}
    argv = ["docker", "run", "--rm", "-i", "--network", "none", *SECCOMP[lx["seccomp"]][0]]
    if lx.get("readonly") or not lx.get("proc", True):
        argv += ["--cap-add", "SYS_ADMIN"]
    argv += ["--tmpfs", f"{LINUX_WORK}:rw,size=64m", "-e", f"TMPDIR={LINUX_WORK}",
             "-v", f"{CONFORMANCE}:{LINUX_HUB}:ro", "-v", f"{LINUX_OUT_VOLUME}:/out:ro"]
    for l in runnable:
        argv += ["-v", f"{lang_repo(langs[l])}:{LINUX_LANGS}/{l}:ro"]
    argv += [LINUX_IMAGE, "python3", "-I", f"{LINUX_HUB}/run.py", "--inside"]
    timeout = CLI_TIMEOUT_SEC * max(1, len(runnable)) + 60
    try:
        r = subprocess.run(argv, input=json.dumps({"case": case, "langs": runnable}),
                           capture_output=True, text=True, timeout=timeout)
        got = json.loads(r.stdout)["outcomes"] if r.returncode == 0 else None
        err = None if r.returncode == 0 else f"コンテナが終了コード {r.returncode}: {r.stderr.strip()[-500:]}"
    except subprocess.TimeoutExpired:
        got, err = None, f"コンテナが {timeout} 秒で終わらない"
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        got, err = None, f"コンテナの出力が読めない ({e}): {r.stderr.strip()[-500:]}"
    outcomes = {}
    for l, c in commands.items():
        if isinstance(c, str):
            outcomes[l] = {"status": "unimplemented", "message": c}
        elif got is None or l not in got:
            outcomes[l] = {"status": "setup-error", "message": err or "コンテナの出力にこの言語が無い"}
        else:
            outcomes[l] = got[l]
    return outcomes


def inside():
    """コンテナの中で、標準入力の {"case", "langs"} を流して {"outcomes"} を標準出力に出す。"""
    req = json.load(sys.stdin)
    case, cmds = req["case"], req["langs"]
    want = SECCOMP[case["linux"]["seccomp"]][1]
    got = seccomp_mode()
    base = tempfile.mkdtemp(prefix="conformance.", dir=LINUX_WORK)
    outcomes = {}
    for lang, cmd in cmds.items():
        if got != want:
            outcomes[lang] = {"status": "setup-error", "message": f"seccomp の mode が {got} (条件 {case['linux']['seccomp']} は {want})"}
        else:
            outcomes[lang] = run_one(case, cmd, base, False)
    print(json.dumps({"outcomes": outcomes}))
    return 0


def describe_options(case):
    parts = []
    if case.get("usable_cross_uid"):
        parts.append(" usable_cross_uid")
    if case.get("base") is not None:
        parts.append(f" base={case['base']}")
    return "".join(parts)


def describe_spelling(sp):
    if sp is None:
        return "-"
    attrs = [f"{k}={json.dumps(v)}" for k, v in sp.items() if k != "kind"]
    return sp["kind"] + (f"({','.join(attrs)})" if attrs else "")


def describe_linux(lx):
    parts = [f"seccomp={lx['seccomp']}"]
    if not lx.get("proc", True):
        parts.append("/proc 無し")
    if lx.get("readonly"):
        parts.append("書けない: " + ",".join(lx["readonly"]))
    return " ".join(parts)


def main():
    ap = argparse.ArgumentParser(description="sockat の適合試験 (決まりは docs/design/conformance.md)")
    ap.add_argument("--langs", help="流す言語 (カンマ区切り。既定は langs.json の全部)")
    ap.add_argument("--case", action="append", help="流す場面の名前 (カンマ区切り、繰り返し可。既定は全部)")
    ap.add_argument("--on", choices=["all", "host", "linux"], default="all",
                    help="流す場面: host は手元で流す場面、linux は Linux のコンテナで流す場面 (linux の条件を持つもの)。既定は両方")
    ap.add_argument("--keep", action="store_true", help="手元で流す場面の一時ディレクトリを消さずに残す")
    ap.add_argument("--no-build", action="store_true", help="流す前に各言語の CLI を作り直さない (langs.json の build と linux.build を走らせない)")
    ap.add_argument("--verbose", action="store_true", help="差が無くても、場面ごとに各言語の route・base・error・spelling・skipped を出す")
    ap.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.inside:
        return inside()

    cases = load_cases()
    langs = load_langs()
    if args.langs:
        wanted = [l for l in args.langs.split(",") if l]
        unknown = [l for l in wanted if l not in langs]
        if unknown:
            fail_usage(f"langs.json に無い言語: {', '.join(unknown)}")
        langs = {l: langs[l] for l in wanted}
    if args.case:
        wanted = [n for arg in args.case for n in arg.split(",") if n]
        known = {c["name"] for c in cases}
        unknown = [n for n in wanted if n not in known]
        if unknown:
            fail_usage(f"cases.json に無い場面: {', '.join(unknown)}")
        cases = [c for c in cases if c["name"] in wanted]
    if args.on == "host":
        cases = [c for c in cases if "linux" not in c]
    elif args.on == "linux":
        cases = [c for c in cases if "linux" in c]

    host_cases = [c for c in cases if "linux" not in c]
    linux_cases = [c for c in cases if "linux" in c]
    if not args.no_build and host_cases:
        # 各言語の CLI を流す前に作り直す (古いビルドのまま比べると、言語の差でなく作り忘れが差に出るため)。
        for l, spec in langs.items():
            repo = lang_repo(spec)
            if spec.get("build") and spec.get("cmd") is not None and repo is not None:
                build_cmd(spec["build"], repo)
    linux_skip = prepare_linux(langs, not args.no_build) if linux_cases else None

    commands = {"host": {l: lang_command(spec) for l, spec in langs.items()},
                "linux": {l: linux_command(l, spec) for l, spec in langs.items()}}
    lacks = {l: set(spec["lacks"]) for l, spec in langs.items()}
    base = tempfile.mkdtemp(prefix="conformance.", dir=os.environ.get("TMPDIR") or None)
    rows = []
    details = []
    failed = False
    messages = []
    splits = []
    verbose = []
    try:
        for case in cases:
            where = "linux" if "linux" in case else "host"
            if where == "linux" and linux_skip:
                continue
            cmds = commands[where]
            if where == "linux":
                outcomes = run_linux_case(case, cmds, langs)
            else:
                outcomes = {}
                for lang, cmd in cmds.items():
                    if isinstance(cmd, str):
                        outcomes[lang] = {"status": "unimplemented", "message": cmd}
                        continue
                    outcomes[lang] = run_one(case, cmd, base, args.keep)
            cells, detail, groups = judge(case, outcomes, lacks)
            if groups:
                splits.append((case["name"], groups))
            for lang, o in outcomes.items():
                if o["status"] == "unimplemented":
                    cmds[lang] = o["message"]
                elif o["status"] in ("broken", "setup-error"):
                    messages.append(f"{case['name']} / {lang}: {o['message']}")
            if any(c in ("差", "期待違い", "壊れた", "準備失敗") for c in cells.values()):
                failed = True
            rows.append([case["name"], where] + [cells[l] for l in langs])
            if detail:
                details.append((case, detail))
            if args.verbose:
                verbose.append((case, outcomes))
    finally:
        if not args.keep:
            shutil.rmtree(base, ignore_errors=True)

    if rows:
        print_table(rows, ["場面", "環境"] + list(langs))
    if linux_skip:
        print(f"\nLinux の場面を飛ばした ({len(linux_cases)} 場面): {linux_skip}")
    ran = {row[1] for row in rows}
    unimplemented = [f"  {lang} ({where}): {cmd}" for where, cmds in commands.items() if where in ran
                     for lang, cmd in cmds.items() if isinstance(cmd, str)]
    if unimplemented:
        print("\n未実装 (差の判定から外した):")
        print("\n".join(unimplemented))
    if splits:
        print("\n作れない経路で組を分けて比べた場面:")
        for name, groups in splits:
            print(f"  {name}: " + " / ".join(",".join(l for l in langs if l in g) for g in groups))
    for case, detail in details:
        lr = describe_options(case)
        env = f"  [linux: {describe_linux(case['linux'])}]" if "linux" in case else ""
        print(f"\n== {case['name']}  ({case['op']}{lr} {json.dumps(case['path'], ensure_ascii=False)}){env}")
        header = ["項目"] + list(langs) + ["期待"]
        drows = []
        for field, (encoded, odd, mismatch, exp_values) in detail.items():
            row = [field]
            for l in langs:
                v = encoded.get(l, "-")
                mark = " !期待" if l in mismatch else (" !差" if l in odd else "")
                row.append(v + mark)
            row.append(" / ".join(sorted(exp_values)) if exp_values else "-")
            drows.append(row)
        print_table(drows, header)
    if verbose:
        print("\n各言語の結果:")
        for case, outcomes in verbose:
            env = f"  [linux: {describe_linux(case['linux'])}]" if "linux" in case else ""
            print(f"  {case['name']}{env}")
            for l, o in outcomes.items():
                if o["status"] != "result":
                    print(f"    {l}: {o['status']}")
                    continue
                r = o["result"]
                print(f"    {l}: ok={json.dumps(r['ok'])} error={r['error']} route={r['route']} base={r['base']} "
                      f"spelling={describe_spelling(r['spelling'])} skipped={','.join(r['skipped']) or '-'}")
    for m in messages:
        print(f"\n{m}")
    if args.keep:
        print(f"\n一時ディレクトリ: {base}")
    if rows and not any(not isinstance(c, str) for w in ran for c in commands[w].values()):
        print("\n比べた言語が無い (全部未実装)")
    print("\n結果: " + ("差あり" if failed else "差なし"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
