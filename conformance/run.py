#!/usr/bin/env python3
"""sockat の適合試験を流す。

決まりの正本は docs/design/conformance.md。場面 (cases.json) ごとに環境を作り、
各言語の試験用 CLI (langs.json) を起こし、結果と CLI の後の状態を言語どうしと
expect で比べる。差があれば場面 x 言語の表を出して終了コード 1。

    python3 -I conformance/run.py [--langs rs,py,go] [--case NAME[,NAME...]] [--keep]

標準ライブラリだけで書く (どの言語のリポにも依らずに流せるように)。
"""

import argparse
import json
import os
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

# {long} はパス全体がこのバイト数以上になるまで深くする。
# sun_path (macOS 104、Linux 108) を超え、ファイル名を足しても PATH_MAX には遠い長さ。
LONG_MIN_BYTES = 150
LONG_SEGMENT = "d" * 16

# CLI が返ってこない時に打ち切るまでの秒数。CLI の 1 回の bind / connect は即座に終わるので、
# これに当たるのは CLI が固まった時だけ (その言語は「壊れた」として表に出す)。
CLI_TIMEOUT_SEC = 120

FIELDS = ["ok", "error", "route", "losses", "skipped", "file", "created", "residue", "received"]
CLI_FIELDS = {"ok": bool, "error": (str, type(None)), "route": (str, type(None)), "losses": list, "skipped": list}

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
        unknown = set(c["expect"]) - set(FIELDS)
        if unknown:
            fail_usage(f"cases.json: 場面 {c['name']!r} の expect に知らない項目 {sorted(unknown)}")
        if c["name"] in names:
            fail_usage(f"cases.json: 場面の名前 {c['name']!r} が重複")
        names.add(c["name"])
    return cases


def load_langs():
    return json.loads((CONFORMANCE / "langs.json").read_text(encoding="utf-8"))


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
        long = self.root
        while len(os.fsencode(str(long))) < LONG_MIN_BYTES:
            long = long / LONG_SEGMENT
        self.long = long
        # {short}: {root} を指す /tmp の短い symlink。{root} は $TMPDIR の下で長くなりうるので、
        # 短い絶対パスの場面はこれを通す (名前は /tmp の sockat.* の残骸の確かめに掛からない形)。
        while True:
            short = Path("/tmp") / f"sockat-conformance-{secrets.token_hex(4)}"
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
                 .replace("{short}", str(self.short)))

    def render(self, p):
        """スクリプトが作った場所を placeholder に戻す (言語ごとに場所が違っても比べられるように)。"""
        p = str(p)
        for prefix, name in ((str(self.long), "{long}"), (str(self.root), "{root}"),
                             (str(self.tmp), "{tmpdir}"), (str(self.xdg), "{xdg}")):
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


def tmp_sockat_entries():
    try:
        return {str(Path("/tmp") / n) for n in os.listdir("/tmp") if n.startswith("sockat.")}
    except OSError:
        return set()


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
    for key in ("losses", "skipped"):
        if not all(isinstance(x, str) for x in out[key]):
            return None, f"出力の {key} が文字列の並びでない: {out[key]!r}"
    return out, None


def run_one(case, argv, base, keep):
    """1 つの場面を 1 つの言語で流す。戻り値は {"status": "result"|"broken"|"unimplemented", ...}。"""
    env = Env(base)
    try:
        cwd = env.subst(case["cwd"])
        path = env.subst(case["path"])
        try:
            env.run_setup(cwd, case["setup"])
        except (SetupError, OSError) as e:
            return {"status": "setup-error", "message": str(e)}
        child_env = dict(os.environ)
        child_env["TMPDIR"] = str(env.tmp)
        child_env["XDG_RUNTIME_DIR"] = str(env.xdg)
        child_env["PWD"] = cwd
        before_tree = env.tree()
        before_tmp = tmp_sockat_entries()
        try:
            proc = subprocess.run(argv, input=json.dumps({"op": case["op"], "path": path}),
                                  cwd=cwd, env=child_env, umask=0o022, capture_output=True,
                                  text=True, timeout=CLI_TIMEOUT_SEC)
        except (FileNotFoundError, PermissionError) as e:
            return {"status": "unimplemented", "message": f"起こせない: {e}"}
        except subprocess.TimeoutExpired:
            return {"status": "broken", "message": f"{CLI_TIMEOUT_SEC} 秒で終わらない"}
        try:
            received = env.collect_received()
        except SetupError as e:
            return {"status": "setup-error", "message": str(e)}
        if proc.returncode != 0:
            return {"status": "broken", "message": f"終了コード {proc.returncode}: {proc.stderr.strip()[-500:]}"}
        out, err = validate_cli_output(proc.stdout)
        if err:
            return {"status": "broken", "message": f"{err}: {proc.stderr.strip()[-500:]}"}
        created_abs = sorted(env.tree() - before_tree)
        residue = sorted(env.render(p) for p in created_abs if os.path.basename(p).startswith(".sockat."))
        created = sorted(env.render(p) for p in created_abs if not os.path.basename(p).startswith(".sockat."))
        residue += sorted(env.render(env.tmp / n) for n in os.listdir(env.tmp))
        residue += sorted(env.render(env.xdg / n) for n in os.listdir(env.xdg))
        residue += sorted(tmp_sockat_entries() - before_tmp)
        result = {
            "ok": out["ok"],
            "error": out["error"],
            "route": out["route"],
            "losses": out["losses"],
            "skipped": out["skipped"],
            "file": is_socket(env.resolve(cwd, path)),
            "created": created,
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
    if not result["ok"]:
        exp["losses"] = []
    exp.update(case["expect"])
    return exp


def judge(case, outcomes):
    """場面の判定。戻り値: (言語ごとの状態, 項目ごとの詳細の行)。"""
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
    for field in FIELDS:
        values = {l: r[field] for l, r in results.items()}
        encoded = {l: json.dumps(v, ensure_ascii=False) for l, v in values.items()}
        distinct = set(encoded.values())
        odd = set()
        if len(distinct) > 1:
            counts = {v: list(encoded.values()).count(v) for v in distinct}
            top = max(counts.values())
            majority = [v for v, n in counts.items() if n == top]
            if len(majority) == 1 and top > 1:
                odd = {l for l, v in encoded.items() if v != majority[0]}
            else:
                odd = set(values)
            for l in odd:
                if cells[l] == "一致":
                    cells[l] = "差"
        mismatch = set()
        for l, r in results.items():
            exp = implicit_expect(case, r)
            if field in exp and r[field] != exp[field]:
                mismatch.add(l)
                cells[l] = "期待違い"
        if odd or mismatch:
            exp_values = {json.dumps(implicit_expect(case, r).get(field), ensure_ascii=False)
                          for r in results.values() if field in implicit_expect(case, r)}
            detail[field] = (encoded, odd, mismatch, exp_values)
    return cells, detail


def width(s):
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def pad(s, n):
    return s + " " * max(0, n - width(s))


def print_table(rows, header):
    widths = [max(width(r[i]) for r in [header] + rows) for i in range(len(header))]
    for r in [header] + rows:
        print("  ".join(pad(c, w) for c, w in zip(r, widths)).rstrip())


def main():
    ap = argparse.ArgumentParser(description="sockat の適合試験 (決まりは docs/design/conformance.md)")
    ap.add_argument("--langs", help="流す言語 (カンマ区切り。既定は langs.json の全部)")
    ap.add_argument("--case", action="append", help="流す場面の名前 (カンマ区切り、繰り返し可。既定は全部)")
    ap.add_argument("--keep", action="store_true", help="場面の一時ディレクトリを消さずに残す")
    args = ap.parse_args()

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

    commands = {l: lang_command(spec) for l, spec in langs.items()}
    base = tempfile.mkdtemp(prefix="conformance.", dir=os.environ.get("TMPDIR") or None)
    rows = []
    details = []
    failed = False
    messages = []
    try:
        for case in cases:
            outcomes = {}
            for lang, cmd in commands.items():
                if isinstance(cmd, str):
                    outcomes[lang] = {"status": "unimplemented", "message": cmd}
                    continue
                outcomes[lang] = run_one(case, cmd, base, args.keep)
            cells, detail = judge(case, outcomes)
            for lang, o in outcomes.items():
                if o["status"] == "unimplemented":
                    commands[lang] = o["message"]
                elif o["status"] in ("broken", "setup-error"):
                    messages.append(f"{case['name']} / {lang}: {o['message']}")
            if any(c in ("差", "期待違い", "壊れた", "準備失敗") for c in cells.values()):
                failed = True
            rows.append([case["name"]] + [cells[l] for l in langs])
            if detail:
                details.append((case, detail))
    finally:
        if not args.keep:
            shutil.rmtree(base, ignore_errors=True)

    print_table(rows, ["場面"] + list(langs))
    unimplemented = [f"  {lang}: {cmd}" for lang, cmd in commands.items() if isinstance(cmd, str)]
    if unimplemented:
        print("\n未実装 (差の判定から外した):")
        print("\n".join(unimplemented))
    for case, detail in details:
        print(f"\n== {case['name']}  ({case['op']} {json.dumps(case['path'], ensure_ascii=False)})")
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
    for m in messages:
        print(f"\n{m}")
    if args.keep:
        print(f"\n一時ディレクトリ: {base}")
    if not any(not isinstance(c, str) for c in commands.values()):
        print("\n比べた言語が無い (全部未実装)")
    print("\n結果: " + ("差あり" if failed else "差なし"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
