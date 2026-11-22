# sockat リファレンス

> [English](./reference.md) | 日本語

関数と型の詳しい説明は、言語ごとの API リファレンスにあります。

| 言語 | API リファレンス |
|---|---|
| Rust | [docs.rs/sockat](https://docs.rs/sockat) |
| Python | [sockat-py のマニュアル](https://github.com/kawaz/sockat-py/blob/main/docs/MANUAL-ja.md#関数の一覧) |
| Go | [pkg.go.dev](https://pkg.go.dev/github.com/kawaz/sockat-go) |
| JavaScript / TypeScript | [sockat-ts のマニュアル](https://github.com/kawaz/sockat-ts/blob/main/docs/MANUAL-ja.md#関数の一覧) |

## どんな API があるか

次の API があります。名前は Rust の物で、他の言語はその言語の慣習の名前です。

| API | すること |
|---|---|
| `bind(path)` | 長いパスでも bind して、listen 済みの標準の listener を返す |
| `connect(path)` | 長いパスでも connect して、標準の stream を返す |
| `connect_nonblocking(path)` | 待たずに connect する (async ランタイム向け) |
| `datagram::bind(path)`<br>`datagram::unbound()`<br>`datagram::connect(&sock, path)` | DGRAM のソケットを bind / connect する |
| `bind_ex(path, options)`<br>`connect_ex(path, options)` 等 | 上と同じことをして、ソケットのファイルを消す口と、どう届いたかの情報も返す |
| `resolve_for_bind(path, options)`<br>`resolve_for_connect(path, options)` | bind / connect はせず、短いパスだけを返す |
| `sweep()`<br>`sweep_base(path)` | sockat が裏で作った物のうち、使われていない物を片付ける (`sweep_base` は `base` で指定した置き場の物) |

言語によって無い物があります (TypeScript の DGRAM 等)。その言語のリファレンスで確かめてください。

## 仕様

どの言語の実装も従う約束は、[仕様](../docs/SPEC-ja.md) にあります。
