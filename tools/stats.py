"""3 言語のパッケージの利用の統計をまとめて表示する (python3 標準ライブラリだけ + gh)。

使い方: python3 -I tools/stats.py [--json]
取れない欄は「無し」と理由、取得に失敗した欄は「取得失敗: 理由」を出す。
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = "sockat-stats"
TIMEOUT = 20

LANGS = [
    {"lang": "Rust", "registry": "crates.io", "name": "sockat", "repo": "kawaz/sockat-rs"},
    {"lang": "Python", "registry": "PyPI", "name": "sockat", "repo": "kawaz/sockat-py"},
    {"lang": "Go", "registry": "pkg.go.dev", "name": "github.com/kawaz/sockat-go", "repo": "kawaz/sockat-go"},
]


class NotFound(Exception):
    pass


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/html"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise NotFound(url)
        raise


def get_json(url):
    return json.loads(http_get(url))


def attempt(fn):
    """成功なら値、失敗なら {"error": 理由}。"""
    try:
        return fn()
    except NotFound as e:
        return {"error": f"404 {e}"}
    except Exception as e:  # 1 つの取得の失敗で全体を止めない
        return {"error": f"{type(e).__name__}: {e}"}


def none(reason):
    return {"none": reason}


# ---------- 版 ----------

def latest_crates():
    c = get_json("https://crates.io/api/v1/crates/sockat")
    ver = c["crate"]["max_stable_version"] or c["crate"]["max_version"]
    published = next((v["created_at"] for v in c["versions"] if v["num"] == ver), None)
    return {"version": ver, "published": published}


def latest_pypi():
    d = get_json("https://pypi.org/pypi/sockat/json")
    ver = d["info"]["version"]
    times = [f["upload_time_iso_8601"] for f in d["urls"]]
    return {"version": ver, "published": min(times) if times else None}


def latest_go():
    d = get_json("https://proxy.golang.org/github.com/kawaz/sockat-go/@latest")
    return {"version": d["Version"], "published": d["Time"]}


# ---------- ダウンロード数 ----------

def dl_crates():
    c = get_json("https://crates.io/api/v1/crates/sockat")["crate"]
    return {"total": c["downloads"], "recent_90d": c["recent_downloads"]}


def dl_pypi():
    d = get_json("https://pypistats.org/api/packages/sockat/recent")["data"]
    return {"last_day": d["last_day"], "last_week": d["last_week"], "last_month": d["last_month"]}


# ---------- 依存元の数 ----------

def dependents_crates_io():
    return get_json("https://crates.io/api/v1/crates/sockat/reverse_dependencies")["meta"]["total"]


def dependents_depsdev(system, name, version):
    """deps.dev の dependents (v3alpha、版ごと)。404 は未収録 (依存元が無い or まだ取り込まれていない)。"""
    url = "https://api.deps.dev/v3alpha/systems/%s/packages/%s/versions/%s:dependents" % (
        system, urllib.parse.quote(name, safe=""), urllib.parse.quote(version, safe=""))
    try:
        return get_json(url)["dependentCount"]
    except NotFound:
        return {"none": "deps.dev に未収録 (依存元 0 か、まだ取り込まれていない)"}


def dependents_pkgsite():
    html = http_get("https://pkg.go.dev/github.com/kawaz/sockat-go?tab=importedby")
    m = re.search(r'Imported by:\s*</span>\s*([\d,]+)', html)
    if not m:
        raise ValueError("Imported by の数が HTML から見つからない (ページの形が変わった)")
    return int(m.group(1).replace(",", ""))


# ---------- GitHub ----------

def gh_api(path):
    p = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip().splitlines()[-1] if p.stderr.strip() else f"gh 終了コード {p.returncode}")
    return json.loads(p.stdout)


def github(repo):
    r = gh_api(f"repos/{repo}")
    return {"stars": r["stargazers_count"], "forks": r["forks_count"]}


def traffic(repo, kind):
    d = gh_api(f"repos/{repo}/traffic/{kind}")
    return {"count": d["count"], "uniques": d["uniques"]}


# ---------- 集計 ----------

def collect():
    out = []
    for L in LANGS:
        lang, repo = L["lang"], L["repo"]
        e = {"lang": lang, "registry": L["registry"], "name": L["name"], "repo": repo}
        if lang == "Rust":
            e["latest"] = attempt(latest_crates)
            e["downloads"] = attempt(dl_crates)
            e["dependents"] = {
                "crates.io": attempt(dependents_crates_io),
                "deps.dev": attempt(lambda: dependents_depsdev("cargo", "sockat", e["latest"]["version"]))
                if "version" in e["latest"] else {"error": "最新の版が取れないので問えない"},
            }
        elif lang == "Python":
            e["latest"] = attempt(latest_pypi)
            e["downloads"] = attempt(dl_pypi)
            e["dependents"] = {
                "deps.dev": attempt(lambda: dependents_depsdev("pypi", "sockat", e["latest"]["version"]))
                if "version" in e["latest"] else {"error": "最新の版が取れないので問えない"},
            }
        else:
            e["latest"] = attempt(latest_go)
            e["downloads"] = none("モジュールプロキシがダウンロード数を出さない")
            e["dependents"] = {
                "pkg.go.dev": attempt(dependents_pkgsite),
                "deps.dev": attempt(lambda: dependents_depsdev("go", L["name"], e["latest"]["version"]))
                if "version" in e["latest"] else {"error": "最新の版が取れないので問えない"},
            }
        e["github"] = attempt(lambda: github(repo))
        e["traffic"] = {
            "clones_14d": attempt(lambda: traffic(repo, "clones")),
            "views_14d": attempt(lambda: traffic(repo, "views")),
        }
        out.append(e)
    return out


# ---------- 表示 ----------

def fmt(v, render):
    if isinstance(v, dict) and "error" in v:
        return "取得失敗: " + v["error"]
    if isinstance(v, dict) and "none" in v:
        return "無し (" + v["none"] + ")"
    return render(v)


def n(v):
    return str(v)


def show(data):
    for e in data:
        print(f"■ {e['lang']}  ({e['registry']}: {e['name']} / GitHub: {e['repo']})")
        print("  最新の版・公開日    : " + fmt(e["latest"], lambda v: f"{v['version']}  ({v['published']})"))
        if e["lang"] == "Rust":
            dl = fmt(e["downloads"], lambda v: f"累計 {v['total']} / 直近 90 日 {v['recent_90d']}")
        elif e["lang"] == "Python":
            dl = fmt(e["downloads"], lambda v: f"昨日 {v['last_day']} / 直近 1 週 {v['last_week']} / 直近 1 月 {v['last_month']}")
        else:
            dl = fmt(e["downloads"], n)
        print("  ダウンロード数      : " + dl)
        for src, v in e["dependents"].items():
            print(f"  依存元の数 ({src}) : " + fmt(v, n))
        print("  GitHub              : " + fmt(e["github"], lambda v: f"star {v['stars']} / fork {v['forks']}"))
        for key, label in (("clones_14d", "clone"), ("views_14d", "view")):
            print(f"  traffic {label} 14 日  : " + fmt(e["traffic"][key], lambda v: f"{v['count']} (unique {v['uniques']})"))
        print()
    print("注: ダウンロード数はミラー・CI・クローラーを含み人の利用数ではない。依存元の数の方が目安。")


def main():
    ap = argparse.ArgumentParser(description="sockat の 3 言語のパッケージの利用の統計を表示する")
    ap.add_argument("--json", action="store_true", help="機械向けの JSON で出す")
    args = ap.parse_args()
    data = collect()
    if args.json:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        show(data)


if __name__ == "__main__":
    main()
