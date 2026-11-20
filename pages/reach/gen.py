"""届く範囲の表を model.json から計算して、README.md と data/*.json を作る。

python3 -I pages/reach/gen.py          # 生成物を書く
python3 -I pages/reach/gen.py --check  # 生成物と正本がずれていないか、lacks が適合試験の言語の一覧とずれていないかを確かめる

Python の標準ライブラリだけを使う。
"""

import argparse
import itertools
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HUB = HERE.parent.parent
MODEL = HERE / "model.json"
LANGS_JSON = HUB / "conformance" / "langs.json"
README = HERE / "README.md"
DATA_DIR = HERE / "data"

TOKEN = re.compile(r"<(\w+)>")
BIND_OPS = ("bind", "bind_ex", "resolve_for_bind")
# 畳む時に次元を見る順 (先に畳んだ次元ほど「全部」になりやすい)。
DIM_ORDER = ["lang", "cross_uid", "private_tmp", "follows", "sockdir", "xdg", "tmpdir", "tmp",
             "proc", "thread_cwd", "relpath", "filename"]
FORK_DOC = "../fork-cwd.md"


# ---------- 正本の読み込みと、OS ごとの条件の値 ----------

class Model:
    def __init__(self, raw):
        self.raw = raw
        self.params = {k: v["value"] for k, v in raw["params"].items()}
        self.oses = raw["oses"]
        self.os_by_id = {o["id"]: o for o in self.oses}
        self.langs = raw["langs"]
        self.places = raw["places"]
        self.conditions = raw["conditions"]
        self.cond_by_id = {c["id"]: c for c in self.conditions}
        self.ops = raw["ops"]
        self.routes = raw["routes"]
        self.orders = raw["orders"]
        self.fork = raw["fork"]

    def place_profiles(self, place, os):
        p = self.places[place]
        if "os" in p and os["id"] not in p["os"]:
            return [{"id": "none", "label": "無い", "usable": False}]
        if "profiles_by_family" in p:
            by = p["profiles_by_family"]
            return by.get(os["family"], by["*"])
        return p["profiles"]

    def place_len(self, prof, os, which="len"):
        v = prof.get(which, prof.get("len"))
        if v == "os.tmp_realpath":
            return len(os["tmp_realpath"])
        return v

    def limit(self, name, os):
        if name == "sockaddr":
            return os["sockaddr"]
        return self.params[name]

    def route_in_os(self, r, os):
        if "os" in r and os["id"] not in r["os"]:
            return False
        if "os_attr" in r and not os.get(r["os_attr"]):
            return False
        return True

    def dims(self, op, os):
        """この操作と OS で値が変わりうる条件の次元と、その値 (id の並び)。"""
        out = {}
        out["lang"] = [l["id"] for l in self.langs]
        out["filename"] = None  # 帯は後で計算する
        order = [self.routes[rid] for rid in self.orders[op] if self.route_in_os(self.routes[rid], os)]
        if op == "connect" and any(r["spelling"] == "<rel>" for r in order):
            out["relpath"] = None
        if os.get("thread_cwd"):
            out["thread_cwd"] = [True, False]
        if os.get("proc"):
            out["proc"] = [True, False]
        if os["bind_follows_symlink"] == "probe" and op in BIND_OPS:
            out["follows"] = [True, False]
        for place in ("xdg", "tmpdir", "tmp", "sockdir"):
            c = self.cond_by_id[place]
            if op not in c["ops"]:
                continue
            profs = self.place_profiles(place, os)
            if len(profs) > 1:
                out[place] = [p["id"] for p in profs]
        for cid in ("private_tmp", "cross_uid"):
            c = self.cond_by_id[cid]
            if op in c["ops"] and ("os" not in c or os["id"] in c["os"]):
                out[cid] = [True, False]
        return out


def spelling_parts(spelling):
    """綴りの雛形を、決まった長さと、変数 (F・rel・place) に分ける。"""
    variables = []
    const_text = TOKEN.sub(lambda m: (variables.append(m.group(1)), "")[1], spelling)
    return len(const_text), variables


def spelling_len(model, spelling, env):
    const, variables = spelling_parts(spelling)
    n = const
    for v in variables:
        if v in model.params:
            n += model.params[v]
        else:
            n += env[v]
    return n


# ---------- 境目の帯 ----------

def all_routes_for_bands(model, os):
    rs = []
    for op in model.orders:
        for rid in model.orders[op]:
            r = model.routes[rid]
            if model.route_in_os(r, os):
                rs.append(r)
    rs.append(model.fork["bind"])
    fc = dict(model.fork["connect"])
    lb = fc["limit_by_family"]
    fc["limit"] = lb.get(os["family"], lb["*"])
    rs.append(fc)
    return rs


def place_lens(model, os, r):
    if "place" not in r or r["place"].get("in_spelling") is False:
        return [0]
    which = r["place"].get("spell_len", "len")
    lens = set()
    for place in r["place"]["from"]:
        for prof in model.place_profiles(place, os):
            if prof.get("usable", True) is False:
                continue
            v = model.place_len(prof, os, which)
            if v is not None:
                lens.add(v)
    return sorted(lens) or [0]


def bands_for(model, os):
    name_max = model.params["name_max"]
    f_cuts, rel_cuts = set(), set()
    for r in all_routes_for_bands(model, os):
        const, variables = spelling_parts(r["spelling"])
        limit = model.limit(r["limit"], os)
        fixed = const + sum(model.params[v] for v in variables if v in model.params)
        if "F" in variables:
            for pl in place_lens(model, os, r):
                fmax = limit - fixed - (pl if "place" in variables else 0)
                if 1 <= fmax < name_max:
                    f_cuts.add(fmax)
        if "rel" in variables:
            rel_cuts.add(limit - fixed)
    fb, lo = [], 1
    for cut in sorted(f_cuts):
        fb.append((lo, cut))
        lo = cut + 1
    fb.append((lo, name_max))
    rb, lo = [], 1
    for cut in sorted(rel_cuts):
        rb.append((lo, cut))
        lo = cut + 1
    rb.append((lo, None))
    return fb, rb


def band_id(b):
    lo, hi = b
    return f"{lo}-{hi}" if hi is not None else f"{lo}-"


def band_label(b):
    lo, hi = b
    if hi is None:
        return f"{lo} 以上"
    return f"{lo}" if lo == hi else f"{lo}–{hi}"


# ---------- 1 つの組み合わせの計算 ----------

def requires_ok(model, op, os, cond, token):
    if token == "thread_cwd":
        return bool(os.get("thread_cwd")) and cond.get("thread_cwd", False), "スレッドの cwd を使えない"
    if token == "proc":
        return bool(os.get("proc")) and cond.get("proc", False), "/proc を使えない"
    if token == "!proc":
        return not (os.get("proc") and cond.get("proc", False)), None
    if token == "follows":
        if op == "connect":
            return True, None
        f = os["bind_follows_symlink"]
        if f == "probe":
            return cond["follows"], "bind が symlink を辿らない"
        return f, None
    raise ValueError(token)


def usable_places(model, op, os, cond, r, cross_uid_filter):
    out = []
    for place in r["place"]["from"]:
        if place == "sockdir" and op in BIND_OPS:
            pid = model.places["sockdir"]["bind_fixed"]
        else:
            profs = model.place_profiles(place, os)
            pid = cond.get(place, profs[0]["id"])
        prof = next(p for p in model.place_profiles(place, os) if p["id"] == pid)
        if prof.get("usable", True) is False:
            continue
        if cross_uid_filter and not prof.get("traversable", False):
            continue
        out.append((place, prof))
    return out


def try_route(model, op, os, lang, cond, F, rel, r):
    """経路を 1 つ試す。(使えたか, 使えない理由, 選んだ置き場の profile)。理由が None なら列に無い (試さない)。"""
    if r["route"] in lang["lacks"]:
        return False, "この言語に無い", None
    for token in r.get("requires", []):
        ok, why = requires_ok(model, op, os, cond, token)
        if not ok:
            return False, why, None
    cross = op in ("bind_ex", "resolve_for_bind") and cond.get("cross_uid", False)
    if cross and r.get("cross_uid") == "skip":
        return False, "別の uid の指定で使わない", None
    limit = model.limit(r["limit"], os)
    env = {"F": F, "rel": rel}
    place_prof = None
    if "place" in r:
        filt = cross and r.get("cross_uid") == "if_traversable"
        cands = usable_places(model, op, os, cond, r, filt)
        if not cands:
            return False, ("別の uid が辿れる書ける置き場が無い" if filt else "書ける置き場が無い"), None
        pick = r["place"]["pick"]
        which = r["place"].get("spell_len", "len")
        if pick == "shortest":
            cands = [min(cands, key=lambda c: model.place_len(c[1], os, which))]
        elif pick == "first":
            cands = cands[:1]
        last = None
        for place, prof in cands:
            env["place"] = model.place_len(prof, os, which) or 0
            n = spelling_len(model, r["spelling"], env)
            if n <= limit:
                return True, None, prof
            last = n
        return False, too_long_reason(model, r, limit, env, last), None
    n = spelling_len(model, r["spelling"], env)
    if n <= limit:
        return True, None, None
    return False, too_long_reason(model, r, limit, env, n), None


def too_long_reason(model, r, limit, env, n):
    const, variables = spelling_parts(r["spelling"])
    if "F" in variables:
        fixed = n - env["F"]
        if limit - fixed < 1:
            return f"置き場が長い (ファイル名の他で {fixed} > {limit})"
        return f"ファイル名 > {limit - fixed}"
    if "rel" in variables:
        return f"元のパスも相対パスも > {limit}" if r["limit"] == "widened" else f"相対パス > {limit}"
    return f"置き場が長い (綴り {n} > {limit})"


def route_label(r):
    return f"{r['route']} ({r['base']})" if r.get("base") else r["route"]


def spelling_of(r, prof):
    if r.get("kind") is None:
        return None
    if r["kind"] == "Dangling":
        return {"kind": "Dangling"}

    def val(v):
        if isinstance(v, bool):
            return v
        if v == "place.traversable":
            return bool(prof and prof.get("traversable"))
        if v == "not place.under_tmp":
            return not (prof and prof.get("under_tmp"))
        raise ValueError(v)
    return {"kind": "Linked", "removable": r["removable"], "until": r["until"],
            "usable_cross_uid": val(r["usable_cross_uid"]),
            "usable_with_private_tmp": val(r["usable_with_private_tmp"])}


def peer_view(sp, cond):
    if sp["kind"] == "Dangling":
        return "辿れない (片付け済み)"
    problems = []
    if cond.get("cross_uid") and not sp["usable_cross_uid"]:
        problems.append("別の uid")
    if cond.get("private_tmp") and not sp["usable_with_private_tmp"]:
        problems.append("PrivateTmp")
    if problems:
        return "辿れない (" + "・".join(problems) + ")"
    return "辿れる (プロセスが終わるまで)" if sp["until"] == "Process" else "辿れる (cleanup まで)"


def fork_reaches(model, op, os, cond, F):
    if op == "connect":
        fc = model.fork["connect"]
        lb = fc["limit_by_family"]
        limit = model.limit(lb.get(os["family"], lb["*"]), os)
        return spelling_len(model, fc["spelling"], {"F": F}) <= limit
    fb = model.fork["bind"]
    return spelling_len(model, fb["spelling"], {"F": F}) <= model.limit(fb["limit"], os)


def fork_scenario(model, op, os):
    for s in model.fork["scenarios"]:
        if op in s["ops"] and os["id"] in s["os"]:
            return s["id"]
    raise ValueError((op, os["id"]))


def evaluate(model, op, os, lang, cond, F, rel):
    tried = []
    for rid in model.orders[op]:
        r = model.routes[rid]
        if not model.route_in_os(r, os):
            continue
        ok, why, prof = try_route(model, op, os, lang, cond, F, rel, r)
        if ok:
            res = {"reach": True, "route": r["route"], "base": r.get("base"), "label": route_label(r)}
            notes = []
            unc = r.get("unconfirmed")
            if unc and os["id"] in unc["os"]:
                notes.append(unc["note"])
            if op in BIND_OPS:
                sp = spelling_of(r, prof)
                res["spelling"] = sp
                res["peer"] = peer_view(sp, cond)
            res["notes"] = notes
            res["unchanged"] = bool(r.get("unchanged"))
            return res
        if why is not None:
            tried.append(f"{route_label(r)}: {why}")
    if not tried:
        tried = ["この OS で試す経路が無い"]
    res = {"reach": False, "why": tried, "notes": []}
    if fork_reaches(model, op, os, cond, F):
        res["fork"] = fork_scenario(model, op, os)
    return res


def result_key(res):
    return json.dumps(res, ensure_ascii=False, sort_keys=True)


# ---------- 組み合わせを作って畳む ----------

def enumerate_rows(model, op, os):
    dims = model.dims(op, os)
    fb, rb = bands_for(model, os)
    dims["filename"] = [band_id(b) for b in fb]
    band_of = {band_id(b): b for b in fb}
    if "relpath" in dims:
        dims["relpath"] = [band_id(b) for b in rb]
        band_of.update({band_id(b): b for b in rb})
    names = list(dims)
    lang_by_id = {l["id"]: l for l in model.langs}
    rows = []
    for combo in itertools.product(*(dims[n] for n in names)):
        cond = dict(zip(names, combo))
        flo, fhi = band_of[cond["filename"]]
        corners = [(flo, None), (fhi, None)]
        if "relpath" in cond:
            rlo, rhi = band_of[cond["relpath"]]
            if rhi is not None and rhi < flo:
                continue  # 相対パスはファイル名より短くならない
            rtop = rhi if rhi is not None else 4096
            # ファイル名 ≤ 相対パス の範囲の両端
            corners = [(flo, max(rlo, flo)), (min(fhi, rtop), rtop)]
        lang = lang_by_id[cond["lang"]]
        res = evaluate(model, op, os, lang, cond, *corners[0])
        # 帯の反対の端でも同じ結果になることを確かめる (帯の作り方の誤りを拾う)。
        hi_res = evaluate(model, op, os, lang, cond, *corners[1])
        if result_key(res) != result_key(hi_res):
            raise SystemExit(f"帯の中で結果が変わる: {op} {os['id']} {cond} {res} {hi_res}")
        rows.append(({n: frozenset([cond[n]]) for n in names}, result_key(res)))
    return dims, rows


def fold(dims, rows):
    """畳む。次元を見る順で結果の行数が変わるので、いくつかの順で畳んで一番少ない物を使う。"""
    base = [d for d in DIM_ORDER if d in dims]
    orders = [base, base[::-1], base[-1:] + base[:-1], base[-2:] + base[:-2]]
    best = None
    for order in orders:
        out = fold_in_order(order, rows)
        if best is None or len(out) < len(best):
            best = out
    return best


def fold_in_order(order, rows):
    changed = True
    while changed:
        changed = False
        for d in order:
            groups = {}
            for cond, rk in rows:
                key = (tuple((n, cond[n]) for n in order if n != d), rk)
                groups.setdefault(key, set()).update(cond[d])
            if len(groups) < len(rows):
                changed = True
            new = []
            for (others, rk), vals in groups.items():
                cond = dict(others)
                cond[d] = frozenset(vals)
                new.append((cond, rk))
            rows = new
    return rows


# ---------- 実測の根拠 ----------

def evidence_for(model, op, os, cond, res, fb, rb):
    """行に当たる実測を探す。(根拠の文字列の並び, 食い違いの並び)。"""
    refs, mismatches = [], []
    lang_ids = [l["id"] for l in model.langs]
    for ev in model.raw["evidence"]["cases"]:
        if ev["op"] != op or ev["os"] != os["id"]:
            continue
        ok = True
        for d, values in cond.items():
            if d in ("lang", "filename", "relpath"):
                continue
            full = set(model.dims(op, os)[d])
            if d in ev["when"]:
                if ev["when"][d] not in values:
                    ok = False
            elif set(values) != full:
                ok = False
        if not ok:
            continue
        if not any(lo <= ev["filename"] <= hi for lo, hi in (parse_band(b) for b in cond["filename"])):
            continue
        if "relpath" in cond:
            want = ev.get("relpath")
            if want is None:
                if len(cond["relpath"]) != len(rb):
                    continue
                want = 1
            s = os["sockaddr"]
            rng = {"fits-sockaddr": (1, s), "over-sockaddr-within-widened": (s + 1, model.params["widened"])}.get(want, (want, want))
            bands = [parse_band(b) for b in cond["relpath"]]
            if not all(any(lo <= x <= (hi if hi is not None else 10**9) for lo, hi in bands) for x in rng):
                continue
        langs = [l for l in lang_ids if l in cond["lang"]]
        matched = []
        for l in langs:
            obs = ev["observed"].get(l, "")
            if obs is None:
                if op == "bind" and not res["reach"]:
                    matched.append(l)
                elif op == "bind" and res["reach"]:
                    mismatches.append(f"{ev['case']} ({l}): 実測は届かない、計算は {res['label']}")
                continue
            if obs not in {model.routes[rid]["route"] for rid in model.orders[op] if model.routes[rid].get("unchanged")}:
                continue
            if res["reach"] and res["route"] == obs:
                matched.append(l)
            else:
                got = res["label"] if res["reach"] else "届かない"
                mismatches.append(f"{ev['case']} ({l}): 実測は {obs}、計算は {got}")
        if matched:
            who = "" if matched == langs else " (" + "・".join(matched) + ")"
            refs.append(f"{ev['case']}{who}")
    return refs, mismatches


def parse_band(bid):
    lo, hi = bid.split("-")
    return int(lo), (int(hi) if hi else None)


# ---------- 生成 ----------

def value_label(model, os, dim, v):
    if dim == "lang":
        return v
    if dim in ("filename", "relpath"):
        return band_label(parse_band(v))
    if dim in ("xdg", "tmpdir", "tmp", "sockdir"):
        return next(p["label"] for p in model.place_profiles(dim, os) if p["id"] == v)
    return "○" if v else "×"


def typical_values(model, os, dims):
    out = {}
    for d, v in model.raw["typical"]["values"].items():
        if d not in dims:
            continue
        if isinstance(v, dict):
            v = v.get(os["family"], v["*"])
        out[d] = v
    return out


def summarize(model, os, dims, rows):
    """ファイル名の帯ごとに、どの条件でも届く・条件しだい・どの条件でも届かない、普段の環境で届くかを言語ごとに分ける。"""
    typ = typical_values(model, os, dims)
    per_lang = {}
    for lang in dims["lang"]:
        cls = {}
        for b in dims["filename"]:
            here = [(cond, json.loads(rk)["reach"]) for cond, rk in rows if lang in cond["lang"] and b in cond["filename"]]
            rs = [r for _, r in here]
            k = "always" if all(rs) else ("never" if not any(rs) else "some")
            t = all(r for cond, r in here if all(v in cond[d] for d, v in typ.items()))
            cls[b] = [k, t]
        per_lang[lang] = cls
    groups = {}
    for lang, cls in per_lang.items():
        groups.setdefault(json.dumps(cls, sort_keys=True), []).append(lang)
    out = []
    for key, langs in groups.items():
        cls = json.loads(key)
        entry = {"langs": langs}
        for kind in ("always", "some", "never"):
            entry[kind] = merge_bands("filename", [b for b in dims["filename"] if cls[b][0] == kind])
        entry["typical"] = merge_bands("filename", [b for b in dims["filename"] if cls[b][1]])
        out.append(entry)
    return out


def build(model):
    tables = {}
    summary = {}
    mismatches = []
    os_meta = []
    for os in model.oses:
        fb, rb = bands_for(model, os)
        meta = {"id": os["id"], "label": os["label"], "sockaddr": os["sockaddr"],
                "proc": bool(os.get("proc")), "thread_cwd": bool(os.get("thread_cwd")),
                "follows": os["bind_follows_symlink"], "values": {}, "dims": {}}
        for op in model.ops:
            dims, rows = enumerate_rows(model, op["id"], os)
            meta["dims"][op["id"]] = list(dims)
            for d, vals in dims.items():
                meta["values"].setdefault(d, [{"id": v, "label": value_label(model, os, d, v)} for v in vals])
            summary.setdefault(op["id"], {})[os["id"]] = summarize(model, os, dims, rows)
            folded = fold(dims, rows)
            out = []
            for cond, rk in folded:
                res = json.loads(rk)
                refs, mm = evidence_for(model, op["id"], os, cond, res, fb, rb)
                mismatches += mm
                res["basis"] = {"measured": refs, "notes": res.pop("notes")}
                res.pop("unchanged", None)
                c = {}
                for d in dims:
                    if set(cond[d]) != set(dims[d]):
                        c[d] = [v for v in dims[d] if v in cond[d]]
                out.append({"os": os["id"], "c": c, "res": res})
            out.sort(key=lambda row: sort_key(dims, row))
            tables.setdefault(op["id"], []).extend(out)
        os_meta.append(meta)
    return tables, summary, os_meta, sorted(set(mismatches))


def sort_key(dims, row):
    key = []
    for d in ["filename"] + [d for d in dims if d != "filename"]:
        vals = dims[d]
        sel = row["c"].get(d)
        if sel is None:
            key.append((0, 0))
        else:
            key.append((1, min(vals.index(v) for v in sel)))
    return key


def page_data(model, tables, os_meta):
    results, index = [], {}
    packed = {}
    for op, rows in tables.items():
        packed[op] = []
        for row in rows:
            k = result_key(row["res"])
            if k not in index:
                index[k] = len(results)
                results.append(row["res"])
            packed[op].append([row["os"], row["c"], index[k]])
    return {
        "source": "pages/reach/model.json (gen.py が生成。手で直さない)",
        "conditions": [{"id": c["id"], "label": c["label"], "kind": c["kind"]} for c in model.conditions],
        "ops": [{"id": o["id"], "label": o["label"], "note": o["note"]} for o in model.ops],
        "langs": [{"id": l["id"], "label": l["label"]} for l in model.langs],
        "oses": os_meta,
        "fork_doc": FORK_DOC,
        "results": results,
        "rows": packed,
    }


def md_cell_result(res):
    return "○" if res["reach"] else "×"


def md_spelling(sp):
    if sp is None:
        return ""
    if sp["kind"] == "Dangling":
        return "Dangling"
    return "<br>".join([
        "Linked",
        f"removable: {str(sp['removable']).lower()}",
        f"until: {sp['until']}",
        f"usable_cross_uid: {str(sp['usable_cross_uid']).lower()}",
        f"usable_with_private_tmp: {str(sp['usable_with_private_tmp']).lower()}",
    ])


REQUIRES_LABEL = {"thread_cwd": "スレッドの cwd", "proc": "/proc", "!proc": "/proc を使えない時だけ",
                  "follows": "bind が symlink を辿る (connect はいつも辿る)"}
PLACE_LABEL = {"xdg": "$XDG_RUNTIME_DIR", "tmpdir": "$TMPDIR", "tmp": "/tmp", "sockdir": "ソケットのディレクトリ"}
PICK_LABEL = {"first": "書ける最初の物", "shortest": "書ける物のうち実パスの短い方", "first_fit": "綴りが収まる最初の物"}
CROSS_LABEL = {"skip": "別の uid の指定で飛ばす", "if_traversable": "別の uid の指定では、途中が other に x の置き場だけ"}


def mark(prof, key, place):
    if place == "sockdir":
        return "—"
    return "○" if prof.get(key) else "×"


def reach_formula(model, r):
    const, variables = spelling_parts(r["spelling"])
    fixed = const + sum(model.params[v] for v in variables if v in model.params)
    limit = "253" if r["limit"] == "widened" else "sockaddr"
    if "F" in variables:
        return limit + (f" − {fixed}" if fixed else "") + (" − 置き場" if "place" in variables else "")
    if "rel" in variables:
        return f"よらない (相対パス ≤ {limit})"
    return "よらない" + (f" (置き場 ≤ sockaddr − {fixed})" if "place" in variables else "")


def route_spelling_desc(r):
    if not r.get("kind"):
        return ""
    if r["kind"] == "Dangling":
        return "Dangling"
    words = {"place.traversable": "置き場までの途中が other に x なら true",
             "not place.under_tmp": "置き場が /tmp・/var/tmp の下でなければ true"}

    def show(v):
        return str(v).lower() if isinstance(v, bool) else words[v]
    return "<br>".join([
        "Linked",
        f"removable: {show(r['removable'])}",
        f"until: {r['until']}",
        f"usable_cross_uid: {show(r['usable_cross_uid'])}",
        f"usable_with_private_tmp: {show(r['usable_with_private_tmp'])}",
    ])


def md_basis(res):
    b = res["basis"]
    parts = []
    if b["measured"]:
        parts.append("実測: " + "、".join(b["measured"]))
    else:
        parts.append("見積もり")
    parts += b["notes"]
    return "<br>".join(parts)


def esc(s):
    return s.replace("|", "\\|")


def render_md(model, tables, summary, os_meta):
    p = model.raw["params"]
    L = []
    w = L.append
    w("# 届く範囲 (作り直しの案)")
    w("")
    w("sockat で長いパスに届くか、どの経路で届くか、届かなければなぜかを、条件の組み合わせごとに並べた表。[resolve と置き場 B で経路を組み直す案](../../docs/issue/2026-11-20-resolve-and-persistent-base.md) (fork なし、最終手段なし) に対して作る。未実装の設計なので、数字は綴りの長さからの見積もり。")
    w("")
    w("- 選んで絞り込むページ: [index.html](index.html) (JS の無い環境ではこの README を読む)")
    w("- 正本: [model.json](model.json)。このファイルと `data/` は [gen.py](gen.py) が生成する (`just reach`)。手で直さない。ずれは `just reach-check` が拾う")
    w("- fork-cwd の手法と、それなら届く場面: [fork-cwd.md](../fork-cwd.md)")
    w("")
    w("## 畳み方")
    w("")
    w("- 表は操作ごと、OS ごとに分ける。行は条件の組み合わせ、列は条件と結果")
    w("- 全部の組み合わせを計算し、結果 (届くか・経路・綴り・理由・根拠) が同じで 1 つの条件の値だけが違う行を 1 行にまとめる。まとまらなくなるまで繰り返す")
    w("- ファイル名と、元のパスと相対パスの短い方の長さは、どれかの経路の綴りが収まるか収まらないかが変わる境目で帯に分ける。帯の中では結果が変わらない (gen.py が帯の両端で確かめる)")
    w("- 表の中のどの行でも「全部」になる条件は列に出さず、表の上に「効かない条件」として書く")
    w("- 置き場の長さは代表値で計算する (「条件」の置き場の表)。パス全体の長さは、ディレクトリが標準に渡す長さを超えるほど深い前提で、PATH_MAX まで効かない")
    w("- 言語は、作れない経路 (lacks) で結果が変わる所だけ分かれる")
    w("")
    w("## 見積もりと実測")
    w("")
    w("- 根拠の列が「見積もり」のセルは、model.json の綴りの式と代表値から計算しただけ")
    w("- 「実測」のセルは、今の実装を適合試験 ([conformance/cases.json](../../conformance/cases.json)) に流した結果が、計算と同じ経路・同じ結果だった場面の名前。当てるのは作り直しで変わらない経路 (" + "・".join(sorted({r["route"] for r in model.routes.values() if r.get("unchanged")})) + ") と、fork を持たない言語 (py・go) の既定の bind の届かない行だけ。条件が全部分かる場面だけを当てる")
    w("- 入力のうち実測したもの: bind が symlink を辿る OS ([findings](../../docs/findings/2026-11-19-bind-through-file-symlink.md))、0700 の親の下の 0711 は別の uid が辿れないこと (issue の「実測」)、docker の seccomp で `unshare` が断られること ([conformance.md](../../docs/design/conformance.md))")
    w("")
    w("見積もりの前提:")
    w("")
    w("| 値 | バイト | 中身 |")
    w("|---|---|---|")
    for k, v in p.items():
        w(f"| `{k}` | {v['value']} | {esc(v['note'])} |")
    w("")
    w("## 条件")
    w("")
    w("| 条件 | 効く操作 | 中身 |")
    w("|---|---|---|")
    op_label = {o["id"]: o["label"] for o in model.ops}
    for c in model.conditions:
        ops = "<br>".join(op_label[o] for o in c["ops"]) if "ops" in c else "全部"
        w(f"| {c['label']} | {ops} | {esc(c.get('note', c.get('uses', '')))} |")
    w("")
    w("置き場 (代表値。長さは実パスのバイト数、symlink-file は `$TMPDIR`・`/tmp` をそのままの綴りで使う):")
    w("")
    w("| 置き場 | OS | 値 | 長さ | 別の uid が辿れる | /tmp・/var/tmp の下 |")
    w("|---|---|---|---|---|---|")
    for place, spec in model.places.items():
        groups = {}
        for os in model.oses:
            key = json.dumps(model.place_profiles(place, os), sort_keys=True)
            groups.setdefault(key, []).append(os)
        for key, oses in groups.items():
            for prof in json.loads(key):
                if prof.get("usable", True) is False:
                    continue
                lens = sorted({model.place_len(prof, o) for o in oses if model.place_len(prof, o) is not None})
                ln = "、".join(str(x) for x in lens) if lens else "—"
                w(f"| {spec['label']} | {'<br>'.join(o['label'] for o in oses)} | {esc(prof['label'])} | {ln} | {mark(prof, 'traversable', place)} | {mark(prof, 'under_tmp', place)} |")
    w("")
    w("## 経路")
    w("")
    w("| 操作 | 順 | 経路 | 綴り | 届くファイル名 | OS | 要る物 | 綴りの性質 (bind) |")
    w("|---|---|---|---|---|---|---|---|")
    for op in model.ops:
        for i, rid in enumerate(model.orders[op["id"]], 1):
            r = model.routes[rid]
            oses = [o["label"] for o in model.oses if model.route_in_os(r, o)]
            oses_cell = "全部" if len(oses) == len(model.oses) else "<br>".join(oses)
            need = [REQUIRES_LABEL[t] for t in r.get("requires", [])]
            if "place" in r:
                need.append("置き場: " + " → ".join(PLACE_LABEL[x] for x in r["place"]["from"]) + f" の{PICK_LABEL[r['place']['pick']]}")
            if r.get("cross_uid"):
                need.append(CROSS_LABEL[r["cross_uid"]])
            sp = route_spelling_desc(r) if op["id"] in BIND_OPS else ""
            w(f"| {op['label']} | {i} | {route_label(r)} | `{r['spelling']}` | {reach_formula(model, r)} | {oses_cell} | {esc('<br>'.join(need)) or '—'} | {sp} |")
    w("")
    w("綴りの記号: `<F>` はファイル名、`<rel>` は元のパスと相対パスの短い方、`<place>` は置き場の実パス (symlink-file はそのままの綴り)、それ以外は「見積もりの前提」の値。sockaddr は sockaddr に入る長さ (Linux / illumos 107、他 103)")
    w("")
    w("## まとめ: ファイル名の長さごとに届くか")
    w("")
    w("表の全部の条件の組み合わせを、ファイル名の帯ごとにまとめた物。「条件しだい」はスレッドの cwd・`/proc`・置き場・別の uid・相対パスの長さ等で届いたり届かなかったりする帯。「普段の環境で届く」の条件: " + model.raw["typical"]["note"])
    w("")
    w("| 操作 | OS | 言語 | 普段の環境で届く | どの条件でも届く | 条件しだい | どの条件でも届かない |")
    w("|---|---|---|---|---|---|---|")
    all_langs = [l["id"] for l in model.langs]
    for op in model.ops:
        for os in model.oses:
            for e in summary[op["id"]][os["id"]]:
                langs = "全部" if e["langs"] == all_langs else "<br>".join(e["langs"])
                cell = lambda bs: "<br>".join(band_label(parse_band(b)) for b in bs) or "—"
                w(f"| {op['label']} | {os['label']} | {langs} | {cell(e['typical'])} | {cell(e['always'])} | {cell(e['some'])} | {cell(e['never'])} |")
    w("")
    w("## 表")
    w("")
    meta_by = {m["id"]: m for m in os_meta}
    for op in model.ops:
        w(f"### {op['label']}")
        w("")
        w(op["note"])
        w("")
        for os in model.oses:
            rows = [r for r in tables[op["id"]] if r["os"] == os["id"]]
            meta = meta_by[os["id"]]
            dims = meta["dims"][op["id"]]
            shown = [d for d in dims if any(d in r["c"] for r in rows)]
            silent = [d for d in dims if d not in shown]
            w(f"#### {op['label']} / {os['label']}")
            w("")
            if silent:
                w("効かない条件: " + "、".join(model.cond_by_id[d]["label"] for d in silent))
                w("")
            head = [model.cond_by_id[d]["label"] for d in shown] + ["届く", "経路"]
            if op["id"] in BIND_OPS:
                head += ["綴り", "綴りを相手が辿れるか"]
            head += ["届かない理由", "fork-cwd なら", "根拠"]
            w("| " + " | ".join(head) + " |")
            w("|" + "---|" * len(head))
            for r in rows:
                res = r["res"]
                cells = []
                for d in shown:
                    if d in r["c"]:
                        cells.append("<br>".join(esc(value_label(model, os, d, v)) for v in merge_bands(d, r["c"][d])))
                    else:
                        cells.append("全部")
                cells.append(md_cell_result(res))
                cells.append(res.get("label", "—"))
                if op["id"] in BIND_OPS:
                    cells.append(md_spelling(res.get("spelling")) or "—")
                    cells.append(res.get("peer", "—"))
                cells.append("<br>".join(esc(x) for x in res.get("why", [])) or "—")
                cells.append(f"[届く]({FORK_DOC}#{res['fork']})" if res.get("fork") else "—")
                cells.append(md_basis(res))
                w("| " + " | ".join(cells) + " |")
            w("")
    return "\n".join(L) + "\n"


def merge_bands(dim, values):
    if dim not in ("filename", "relpath"):
        return values
    bands = sorted(parse_band(v) for v in values)
    out = []
    for lo, hi in bands:
        if out and out[-1][1] is not None and out[-1][1] + 1 == lo:
            out[-1] = (out[-1][0], hi)
        else:
            out.append((lo, hi))
    return [band_id(b) for b in out]


def outputs(model):
    tables, summary, os_meta, mismatches = build(model)
    files = {README: render_md(model, tables, summary, os_meta)}
    data = page_data(model, tables, os_meta)
    files[DATA_DIR / "reach.json"] = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
    return files, mismatches


def check_lacks(model):
    langs = json.loads(LANGS_JSON.read_text())
    outside = set(model.raw["routes_outside_table"]["routes"])
    problems = []
    for l in model.langs:
        want = set(langs[l["id"]]["lacks"]) - outside
        if want != set(l["lacks"]):
            problems.append(f"{l['id']}: model.json の lacks {sorted(l['lacks'])} が conformance/langs.json の {sorted(want)} (表に出ない経路を除く) と違う")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="書かずに、生成物と正本のずれを確かめる")
    args = ap.parse_args()
    model = Model(json.loads(MODEL.read_text()))
    files, mismatches = outputs(model)
    problems = check_lacks(model)
    problems += [f"実測と計算の食い違い: {m}" for m in mismatches]
    if args.check:
        for path, text in files.items():
            if not path.exists() or path.read_text() != text:
                problems.append(f"{path.relative_to(HUB)} が model.json から作った物と違う (just reach で作り直す)")
        for path in DATA_DIR.glob("*.json"):
            if path not in files:
                problems.append(f"{path.relative_to(HUB)} は生成物に無い")
    else:
        DATA_DIR.mkdir(exist_ok=True)
        for path in DATA_DIR.glob("*.json"):
            if path not in files:
                path.unlink()
        for path, text in files.items():
            path.write_text(text)
            print(f"wrote {path.relative_to(HUB)} ({len(text.encode())} bytes)", file=sys.stderr)
    for p in problems:
        print(p, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
