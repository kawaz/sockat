# 深い cwd で相対パスに bind した DGRAM の送り手に、受け手が返信できるか

- Date: 2026-11-22 (測定日)

126 バイトの cwd にいる DGRAM の送り手が、相対パスか絶対パスで bind して受け手に送り、別の cwd にいる受け手が `recvfrom` のアドレスへ返信する。標準と sockat-py (作業コピー) で比べた。

## 判明した事実

- 相対パス (`./bind.sock`) で bind すると、受け手に見える送り手のアドレスは `./bind.sock` のままで、別の cwd にいる受け手の返信は `ENOENT` で失敗する。標準でも sockat でも同じ (sockat は短いパスを標準にそのまま渡すため)
- 絶対パス (137 バイト) は、標準では bind できない (`AF_UNIX path too long`)
- 絶対パスを sockat の `datagram.bind` に渡すと、受け手に見えるアドレスは `/private/tmp/sockat-501/<D>/0/bind3.sock` (47 バイト) になり、返信が届く

## 実用的な示唆 / ベストプラクティス

- 深い場所で返信を受けたい DGRAM の送り手は、絶対パスを sockat に渡して bind する。標準だけでは、絶対パスは長すぎて bind できず、相対パスは返信が届かない
- CLI の `resolve` が相対パスを絶対にしてから長さで分ける決まり ([cli.md](../design/cli.md)) は、この場面で「相手にとっても使えるアドレス」を出すことに当たる。渡した文字列より出る綴りが長くなるのは、このため

## 検証の詳細

| 送り手の bind | 受け手に見えるアドレス | 返信 |
|---|---|---|
| 標準、`./bind1.sock` | `./bind1.sock` | 失敗 (`FileNotFoundError`) |
| sockat、`./bind2.sock` | `./bind2.sock` | 失敗 (`FileNotFoundError`) |
| 標準、絶対パス (137 バイト) | bind できない (`OSError('AF_UNIX path too long')`) | — |
| sockat、絶対パス (137 バイト) | `/private/tmp/sockat-501/x3AmXcJnX8/0/bind3.sock` (47 バイト) | 届いた |

- 環境: macOS 26 (Darwin 25.5.0)、Python 3.15.2、sockat-py の作業コピー
- 手順: `/tmp/se-XXXXXX/` に受け手のソケットを置き、その下の 50 文字 × 2 段のディレクトリを送り手の cwd にする。送り手が bind して `sendto` し、受け手は `recvfrom` の後、cwd を `/tmp/se-XXXXXX/` に移してから `sendto(アドレス)` で返信する

## 未確認

- Linux では測っていない
