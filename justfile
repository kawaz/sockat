# sockat (ハブ) justfile
#
# README / docs/SPEC は ja が正本、en が翻訳先。push 時に
# check-outdated-translations が「en が ja より古い」を止める。
# VCS 操作は bump-semver vcs に委譲して jj / git を透過にする。

set shell := ["bash", "-euo", "pipefail", "-c"]

set script-interpreter := ["bash", "-euo", "pipefail"]

# default: list
default: list

# show recipes
list:
    @just --list --unsorted

# ---------- gates (push の内部) ----------

# uncommitted change がない状態か確認
[private]
ensure-clean:
    bump-semver vcs is clean

# 現在の bookmark/branch が default (= main) 上にあるか確認
[private]
[script]
check-on-default-branch:
    if ! bump-semver vcs is on-default-branch; then
        bn=$(bump-semver vcs get default-branch)
        printf >&2 "default branch (%s) に合流してから push してください\n  1. just sync         # %s@origin に rebase\n  2. just promote      # %s bookmark を current commit に forward\n" "$bn" "$bn" "$bn"
        exit 1
    fi

# 翻訳ペアの鮮度 (正本 = *-ja.md、翻訳先 = 同じ場所の *.md)
[private]
check-outdated-translations: ensure-clean
    bump-semver vcs outdated 'glob:**/*-ja.md' '$1/$2.md'

# ---------- flow ----------

# 現在の worktree を default branch (= origin/<default>) に rebase
sync:
    bump-semver vcs sync --onto $(bump-semver vcs get default-branch)@origin

# default branch を現在の commit に forward (push しない)
promote:
    bump-semver vcs promote

# push (gate を全部通してから)
push: check-on-default-branch ensure-clean check-outdated-translations
    bump-semver vcs push --branch main --jj-bookmark-auto-advance

# ---------- 適合試験 ----------

# 言語によらない適合試験を流す (例: just conformance --langs rs,go --case long-connect)
conformance *ARGS:
    python3 -I conformance/run.py {{ARGS}}
