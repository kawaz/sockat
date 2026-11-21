---
title: TypeScript 版 (sockat-ts) を作る
status: open
category: task
created: 2026-11-21
origin: 他プロジェクトからの依頼 (claude-ccmsg)
---

# TypeScript 版 (sockat-ts) を作る

## 依頼 (kawaz 2026-11-21、claude-ccmsg の統括から取り次ぎ)

- 「sockat に ts 版を作ってもらうようお願いしてください」
- claude-ccmsg (Bun) の webui の実ブラウザの試験と daemon で、macOS の深い一時ディレクトリの Unix socket が sun_path を超えて起動できないことがある。TypeScript (Bun / Node) から長いパスで bind / connect したい
- リポ・対象の runtime・適合試験への載せ方は sockat 側で決める。決まったら claude-ccmsg の統括 (session 37fc4760) に知らせる

## 決まったこと

- リポは kawaz/sockat-ts、package 名は `@kawaz/sockat` (scope なしの `sockat` は registry の似た名前の検査 (socks・sockjs) で断られた) (kawaz 2026-11-21)
- 名前を押さえる 0.0.0 (コードなし) を手で公開し、tag v0.0.0 を付けた。次の版から Release (trusted publishing、environment `npm`) で出す

## 決めること

- 対象の runtime (Bun / Node / 両方。Deno は需要が弱い)
- native の部品 (flock、openat、bindat / connectat、スレッドの cwd) を Bun の FFI / Node の addon で持つか、JS だけで作れる経路に絞るか
- 標準の型 (`net.Server` / `net.Socket`、`Bun.listen` / `Bun.connect`) への載せ方
- 公開: trusted publisher の設定 (registry の package の設定画面で repo `kawaz/sockat-ts`・workflow `release.yml`・environment `npm`)

## 残り

- [ ] 実現性の調査 (runtime ごとの標準の上限と切り詰め、経路ごとに要る部品、fd を標準の型に取り込めるか)
- [ ] 設計の DR (sockat-ts の側) と、kawaz の裁定が要る点の Q
- [ ] sockat-ts のリポを作り、実装・適合試験の CLI・公開
- [ ] claude-ccmsg に知らせる

## 関連

- [他言語の調査](../research/2026-11-18-ports-to-other-languages.md) の JavaScript / TypeScript の節
- [DR-0001](../decisions/DR-0001-hub-and-per-language-repos.md)、[DR-0017](../decisions/DR-0017-resolve-through-persistent-base.md)、[SPEC](../SPEC-ja.md)
