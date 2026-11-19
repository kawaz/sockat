# sockat specification

> English | [日本語](./SPEC-ja.md)

How sockat behaves, independent of the language. Every implementation follows it. The decisions and the rejected alternatives are in [docs/decisions](decisions/INDEX.md) (Japanese); what is specific to Rust (types, where `unsafe` lives, tokio) is in [sockat-rs's MANUAL](https://github.com/kawaz/sockat-rs/blob/main/docs/MANUAL.md).

## Terms

| Term | Meaning |
|---|---|
| standard | the language's standard library bind / connect for Unix domain sockets |
| standard length | the longest path the language's standard accepts. A path up to it is handed to the standard unchanged. Usually `sun_path` − 1, `sun_path` − 2 for Java ([DR-0004](decisions/DR-0004-standard-length-per-language.md), Japanese) |
| sockaddr length | the length of `sun_path` − 1 byte (leaving room for the NUL). The longest spelling a sockaddr that is not widened carries |
| directory / file name | what precedes the last component of the path, and the last component |
| spelling | the path string handed to the kernel. A route is a way to build another spelling of the same place |
| D | a directory of sockat's own, created for each bind / connect ([D and R](#d-and-r)) |
| R | a symlink with a random name, pointing to the socket's directory. Created inside D (inside the socket's directory for [the form without D](#the-form-without-d)) |

## Scope

- bind (and listen) / connect of pathname Unix domain sockets
- Unix-like OSes. Windows is not supported

## Operations

| Operation | Rust | Python | Go | Fork | Blocks | Returns |
|---|---|---|---|---|---|---|
| bind | `bind` | `bind` | `Listen` | tried | (does not wait) | a listening standard listener |
| bind with cleanup | `bind_ex` | `bind_ex` | `ListenEx` | tried | (does not wait) | a standard listener and `discard()` |
| bind that reaches even by losing something | `bind_any` | `bind_any` | `ListenAny` | tried | (does not wait) | a standard listener, and `losses` / `route` / `skipped` |
| connect | `connect` | `connect` | `Dial` | never tried | yes | a standard stream |
| non-blocking connect | `connect_nonblocking` | `connect_nonblocking` | none | never tried | no | a non-blocking standard stream |
| connect that reaches even by losing something | `connect_any` | none | none | tried | yes | a standard stream, and `losses` / `route` / `skipped` |
| the same, non-blocking | `connect_any_nonblocking` | none | none | tried | no | as above (the stream is non-blocking) |

- The names are provisional. Other languages follow their own naming conventions. The behavior follows the table above
- The listener / stream returned is of the same type the standard returns, so it is a drop-in replacement for the standard
- `_ex` exists for bind only. It remembers the realpath and `(st_dev, st_ino)` of the bound socket file; `discard()` removes the file only when that path still has the same `(st_dev, st_ino)`. `discard()` does not close the listener (the user does) ([DR-0014](decisions/DR-0014-discard-removes-only.md), Japanese)
  - It remembers them right after the bind succeeds (inside the route, before returning the listener). If they cannot be remembered, it closes the listener, leaves the file, and returns an error (it does not hand back a `discard()` that cannot remove anything as a success)
  - The path argument is turned into a string once at the entry, and that value is used for remembering, binding and returning alike (so that a path type that can return a different value on each call never makes the remembered file differ from the bound one)
  - `discard()` succeeds when the file is already gone and when it has been replaced by another file and is left alone. It fails when the check cannot be made (`lstat` fails with something other than `ENOENT` / `ENOTDIR`) and when the removal itself fails (it does not report success when it cannot tell whether anything was removed)
  - Someone who can write to the socket's directory swapping the file between the check and the removal, or between the bind and the remembering, cannot be prevented (POSIX has no way to remove by inode)
- The any family (`bind_any`, the `connect_any` variants) reaches even by losing something when none of the default routes can be used ([DR-0013](decisions/DR-0013-any-means-reach-at-any-cost.md), Japanese). `bind_any` tries the base's [symlink](#symlink) last, the `connect_any` variants [fork-direct](#fork-direct) last. No pid is returned
- On success the any family returns these three ([DR-0013](decisions/DR-0013-any-means-reach-at-any-cost.md), Japanese)
  - `losses`: the names of what was lost on the route taken (the names in "[What is lost](#what-is-lost)"; empty when nothing was lost). Branch on it. The names are a promise: they are never changed, only added (the documentation says to read an unknown name only as "something was lost"). The names have no order or inclusion among them
  - `route`: the name of the route taken
  - `skipped`: the routes tried and found unusable, in the order tried. Each element is `{ name, reason }` (the route name and why it was unusable). Every route tried before `route` was unusable, so there is no "was it usable" field
  - The names in `route` and `skipped` and the `reason` are for diagnostics and promise nothing about their content (routes are added and changed)
  - The field and type names follow each language's conventions. The names of what is lost may be represented in the language's own way (an enum etc.), but as strings they equal the names in this SPEC
- When the any family fails, the error carries `skipped` too. When a route actually bound / connected and failed, its name (`route`) is attached as well (not for `ENAMETOOLONG`, where none could be used) ([DR-0013](decisions/DR-0013-any-means-reach-at-any-cost.md), Japanese)
  - How they are attached follows each language's conventions. The errno of an OS error stays readable ([Errors](#errors))
- The any family is not in the default API; it sits behind a mechanism the user opts into (an `any` feature in Rust). The `connect_any` variants are no different from the default connect in a language that cannot build the fork route, so such a language does not provide them; its README says "no fork route" in the table ([DR-0002](decisions/DR-0002-no-connect-any-without-fork.md), Japanese). `bind_any` is provided whether or not fork exists
- A language whose standard connect never blocks (Node.js etc.) provides one connect in the standard's own form ([DR-0003](decisions/DR-0003-single-connect-when-standard-never-blocks.md), Japanese)
- `connect` / `connect_nonblocking` return `ENAMETOOLONG` when they reach [fork-direct](#fork-direct)
- A non-blocking connect makes the socket non-blocking before connecting and returns it that way. When the peer's backlog is full it fails without waiting. `EINPROGRESS` is returned as an error and the socket is closed
- A socket the implementation creates itself gets the same settings as one the language's standard creates (close-on-exec, `SO_NOSIGPIPE`, the listen backlog, etc.). There is no way to specify the backlog
- When the listener is closed, the socket file is treated as the standard treats it for a short path (Go's standard removes it). For a long path it is not removed, even where the standard removes it (the spelling the kernel holds is not the original path). A language whose standard removes it says so under "differs from the standard" in its README. Removal is `_ex`'s `discard()`

## Short paths

A path up to the standard length is handed to the standard unchanged. Nothing is added and no environment variable is read. A longer path goes to the routes ([DR-0004](decisions/DR-0004-standard-length-per-language.md), Japanese).

- A path containing NUL anywhere but at the start is never handed to the standard, whatever its length; it is an invalid-argument error ([DR-0006](decisions/DR-0006-nul-is-invalid-at-any-length.md), Japanese)
- On Linux / Android a path starting with NUL (abstract namespace) is out of scope and is handed to the standard unchanged, whatever its length. A language's own abstract notation (Go's `@` etc.) likewise
- On OSes without an abstract namespace, a path starting with NUL is an invalid argument too, whatever its length
- In a language whose standard has no non-blocking connect, a non-blocking connect alone uses the implementation's own socket, connected to the same address as the standard would
- When the standard does not accept a route's spelling (a language whose standard length is shorter than the sockaddr length), the implementation's own socket is used with the same address too

| OS | sockaddr length |
|---|---|
| Linux / Android / illumos | 107 bytes |
| macOS / iOS and the other Apple OSes / FreeBSD / NetBSD / OpenBSD | 103 bytes |

## Routes for long paths and their order

A path over the standard length is tried in the order below and bound / connected on the first route that can be used ([DR-0012](decisions/DR-0012-own-directory-and-thread-cwd.md), Japanese).

- A path whose last component is not a file name (`dir/`, `dir/.`, `dir/..`, `..`) is an invalid-argument error, and nothing is created
- The socket's directory is looked up first with `stat`, and its realpath is taken. When it is missing, `ENOENT`; when it is not a directory, `ENOTDIR`; when the realpath cannot be taken, that error (all before the length is judged or D is created). Only the routes that need an fd of the socket's directory ([proc-direct](#proc-direct), [at-direct](#at-direct), [fork-direct](#fork-direct), and the routes whose names end in `-sockdir`) open it, and when it cannot be opened that route is unusable (`O_RDONLY` on other OSes cannot open a directory without read permission)
- No route changes the calling process's cwd or the calling thread's cwd
- How a directory is opened (the base, the socket's directory): `O_SEARCH` on Apple OSes (`O_RDONLY` if the kernel answers `EISDIR` / `EINVAL`), `O_PATH | O_DIRECTORY` on Linux, `O_RDONLY | O_DIRECTORY` elsewhere

### Route names

The routes are called by the names below. Each table is in the order tried. A name that appears for both bind and connect is one route; the differences are in that route's section. The names of what is lost are from "[What is lost](#what-is-lost)".

bind:

| Name | What it does | OS | What is lost |
|---|---|---|---|
| [standard](#standard) | hand the path to the standard unchanged | all | `cwd-relative` for a relative path |
| [thread-cwd](#thread-cwd) | move a throwaway thread's cwd into D, then `R/<file name>` | Linux / Android / Apple OSes | `respelled` |
| [at](#at) | `bindat(Dfd, R/<file name>)` | FreeBSD | `respelled` |
| [proc](#proc) | `/proc/self/fd/<Dfd>/R/<file name>` | Linux / Android with `/proc` usable | `respelled` |
| [fork](#fork) | a forked child `fchdir(Dfd)`s, then `R/<file name>` | all | `respelled`<br>`forked` |
| [thread-cwd-sockdir](#thread-cwd-sockdir) | thread-cwd in the form without D (R inside the socket's directory, `.sockat.XXXXXXXXXX/<file name>`) | Linux / Android / Apple OSes | `respelled` |
| [at-sockdir](#at-sockdir) | at in the form without D | FreeBSD | `respelled` |
| [proc-sockdir](#proc-sockdir) | proc in the form without D | Linux / Android with `/proc` usable | `respelled` |
| [fork-sockdir](#fork-sockdir) | fork in the form without D | all | `respelled`<br>`forked` |
| [symlink](#symlink) | create in a base a symlink to the socket's directory and use `<base>/sockat.XXXXXXXXXX/<file name>` (`bind_any` only) | all | a base only the owner can write to: `respelled`<br>a shared base: `respelled` and `recreatable-spelling` |

- The four `-sockdir` routes are tried, in the same order, only when D can be created nowhere ([the form without D](#the-form-without-d))
- Only `bind_any` tries symlink, where the default bind gives `ENAMETOOLONG`

connect:

| Name | What it does | OS | What is lost |
|---|---|---|---|
| [standard](#standard) | hand the path to the standard unchanged | all | nothing |
| [thread-cwd](#thread-cwd) | move a throwaway thread's cwd into D, then `R/<file name>` | Linux / Android / Apple OSes | nothing |
| [at](#at) | `connectat(Dfd, R/<file name>)` | FreeBSD | nothing |
| [proc](#proc) | `/proc/self/fd/<Dfd>/R/<file name>` | Linux / Android with `/proc` usable | nothing |
| [proc-direct](#proc-direct) | `/proc/self/fd/<fd>/<file name>`, without R (fallback) | Linux / Android with `/proc` usable | nothing |
| [proc-held](#proc-held) | put `s`, pointing to the socket file, in D, then `/proc/self/fd/<Dfd>/s` (fallback) | Linux / Android with `/proc` usable | nothing |
| [relative](#relative) | the path relative to the cwd (fallback) | Linux / Android with `/proc` not usable<br>Apple OSes<br>NetBSD / OpenBSD / illumos / other Unix | nothing |
| [widened](#widened) | a widened sockaddr (fallback) | Apple OSes | nothing |
| [symlink](#symlink) | a symlink in a base (fallback) | all but FreeBSD | nothing |
| [at-direct](#at-direct) | `connectat(<socket's directory fd>, <file name>)` (fallback) | FreeBSD | nothing |
| [fork-direct](#fork-direct) | a forked child connects by the file name (the `connect_any` variants only) | all | `forked` |

- The order in which each OS tries the fallback routes is in "[Fallback routes (connect variants)](#fallback-routes-connect-variants)"

### What is lost

What taking the route loses compared to the standard. The any family's `losses` returns these names (empty when nothing was lost).

| Name | What is lost | Attached when |
|---|---|---|
| `respelled` | the address the kernel reports is not the original path ("[What differs from the standard for a long path](#what-differs-from-the-standard-for-a-long-path)"). Even in a language whose standard removes the file when the listener is closed (Go's standard etc.) it is not removed; the file at the original path has to be removed by the caller (`_ex`'s `discard()` etc.). The random name (R) in the spelling has been removed, so normally it hits nothing, but the spelling may be visible to other users (Linux's `/proc/net/unix`); if the process's cwd is a place others can write to (`/tmp` etc.), after another user sees and recreates it, unlinking by that spelling may remove a same-named file in a directory that user chose. Removing by the original path hits nothing | a bind took a route other than standard |
| `cwd-relative` | the spelling the kernel keeps is relative to the cwd (the given path went to the standard unchanged). Unlinking / `stat`ing by that spelling after the cwd changes hits another place. A hazard the standard already has rather than one a route introduced, but it is reported. Removing by the original path made absolute hits nothing | a bind took [standard](#standard) with a relative path |
| `forked` | the side effects of forking ("[Side effects of the fork route](#side-effects-of-the-fork-route)") | [fork](#fork), [fork-sockdir](#fork-sockdir) or [fork-direct](#fork-direct) was taken |
| `recreatable-spelling` | the spelling the kernel reports goes through a shared base (`/tmp` etc.). The name is random, so it cannot be guessed in advance, but after the bind other users may see it (Linux's `/proc/net/unix`). If another user recreates it and then it is unlinked by that spelling, a same-named file in a directory the other user chose may be removed. Removing by the original path (`discard()` etc.) hits nothing. The name's length is not the defense (the name is visible after the bind) | `bind_any` took the [symlink](#symlink) in a shared base |

- The names are a promise: they are never changed, only added. Read an unknown name only as "something was lost"
- The names have no order or inclusion among them (`forked` and `recreatable-spelling` do not include each other)
- A connect's spelling is left nowhere on the peer ("[Order tried](#order-tried)"), so the only name a connect gets is `forked`
- The symlink in a base only the owner can write to gets `respelled` only

### Order tried

| Step | bind | `connect` / `connect_nonblocking` | `connect_any` variants |
|---|---|---|---|
| 1 | [standard](#standard) (up to the standard length) | same | same |
| 2 | [thread-cwd](#thread-cwd) ([at](#at) on FreeBSD) | as left | as left |
| 3 | [proc](#proc) | as left | as left |
| 4 | [fork](#fork) | the fallback routes | the fallback routes |
| 5 | `ENAMETOOLONG` | `ENAMETOOLONG` | [fork-direct](#fork-direct) |

- A bind's fork is tried when thread-cwd and proc cannot use the thread cwd / `/proc`, or the proc spelling does not fit. When D can be created nowhere, steps 2 to 4 are tried in the form without D ([thread-cwd-sockdir](#thread-cwd-sockdir) ([at-sockdir](#at-sockdir) on FreeBSD) → [proc-sockdir](#proc-sockdir) → [fork-sockdir](#fork-sockdir)). When the spelling does not fit the sockaddr, it is not tried and the result is `ENAMETOOLONG`
- A bind never uses [proc-direct](#proc-direct), [relative](#relative), [widened](#widened), or the [symlink](#symlink) in a base (the spelling would hit an unrelated file later, the address would be cut short and break whoever reads it, or the routes through D suffice). Only `bind_any` tries the [symlink](#symlink) last, to reach even by losing something ([DR-0013](decisions/DR-0013-any-means-reach-at-any-cost.md))
- A connect's spelling is left nowhere on the peer (the connecting socket is not bound), so the fallback routes put no random part in it
- thread-cwd and proc have no side effects (the peer pid stays the caller's, no fd is copied, and other threads' cwd is unchanged). So `connect` / `connect_nonblocking` try them too

### Routes

Numbers are in bytes.

#### standard

- How: hand the path to the standard unchanged ("[Short paths](#short-paths)")
- Usable when: the path is up to the standard length
- Not usable when: the path is over the standard length
- Reach: the whole path up to the standard length
- What is lost: for a bind, `cwd-relative` with a relative path, otherwise nothing; for a connect, nothing
- Apart from what is lost, the same for bind and connect

#### thread-cwd

- How: create D and R ([D and R](#d-and-r)), move [the throwaway thread](#the-throwaway-thread)'s cwd into D, and bind / connect by `R/<file name>`. On Linux / Android `unshare(CLONE_FS)` → `fchdir(Dfd)`; on Apple OSes `pthread_fchdir_np(Dfd)`
- Usable when: Linux / Android / Apple OSes
- Not usable when:
  - Linux / Android: a seccomp filter is in place or this cannot be told (`prctl(PR_GET_SECCOMP)` returns non-zero or fails), `unshare` is refused
  - Apple OSes: `pthread_fchdir_np` is absent or fails
  - a thread cannot be created or pinned
  - D can be created nowhere ([Where D is created](#where-d-is-created)), the spelling does not fit the sockaddr
- Reach: a file name up to the sockaddr length − 11 (96 on Linux / Android, 92 on Apple OSes)
- What is lost: `respelled` for a bind, nothing for a connect
- Apart from what is lost, the same for bind and connect

#### at

- How: create D and R ([D and R](#d-and-r)) and, without a thread, pass `R/<file name>` to `bindat(Dfd, ...)` for a bind, `connectat(Dfd, ...)` for a connect
- Usable when: FreeBSD
- Not usable when: D can be created nowhere ([Where D is created](#where-d-is-created)), the spelling does not fit the sockaddr
- Reach: a file name up to 92
- What is lost: `respelled` for a bind, nothing for a connect

#### proc

- How: create D and R ([D and R](#d-and-r)) and, without a thread, bind / connect by `/proc/self/fd/<Dfd>/R/<file name>`
- Usable when: Linux / Android with `/proc` usable
- Not usable when: `/proc/self/fd/<Dfd>` cannot be resolved, the spelling does not fit the sockaddr, D can be created nowhere ([Where D is created](#where-d-is-created))
- Reach: a file name up to about 79 (it varies with the fd's digits)
- What is lost: `respelled` for a bind, nothing for a connect
- The spelling's length depends on D's fd number, which is unknown until D is opened. Before creating D it is estimated, and it is checked again once D is open (if it does not fit, D is cleaned up and the next is tried)
- Checking whether `/proc` is usable does not need an fd of the socket's directory (use the fd of `/` or of D)
- The spelling goes through R as well, so a reused fd number later hits no unrelated file
- Apart from what is lost, the same for bind and connect

#### fork

- How: create D and R ([D and R](#d-and-r)); a forked child `fchdir(Dfd)`s and binds by `R/<file name>` ([The forked child](#the-forked-child))
- Usable when: bind only. Tried when the earlier routes cannot be used ("[Order tried](#order-tried)")
- Not usable when: D can be created nowhere ([Where D is created](#where-d-is-created)). When the spelling does not fit the sockaddr, nothing further is tried and the result is `ENAMETOOLONG`
- Reach: a file name up to the sockaddr length − 11 (96 on Linux / illumos, 92 on Apple OSes / BSD)
- What is lost: `respelled` and `forked`
- A connect never uses the fork through D (the `connect_any` variants use [fork-direct](#fork-direct))

#### thread-cwd-sockdir

- How: the same means as [thread-cwd](#thread-cwd), moving into the socket's directory instead of D and binding by `.sockat.XXXXXXXXXX/<file name>` ([the form without D](#the-form-without-d))
- Usable when: bind only. D can be created nowhere. The OSes are those of thread-cwd
- Not usable when: those of thread-cwd's "Not usable when" that do not concern D, the spelling does not fit the sockaddr
- Reach: a file name up to the sockaddr length − 19 (88 on Linux / Android, 84 on Apple OSes)
- What is lost: `respelled`

#### at-sockdir

- How: as [at](#at), passing `.sockat.XXXXXXXXXX/<file name>` to `bindat(<socket's directory fd>, ...)` ([the form without D](#the-form-without-d))
- Usable when: bind only. FreeBSD. D can be created nowhere
- Not usable when: the spelling does not fit the sockaddr
- Reach: a file name up to 84
- What is lost: `respelled`

#### proc-sockdir

- How: as [proc](#proc), binding by `/proc/self/fd/<socket's directory fd>/.sockat.XXXXXXXXXX/<file name>` ([the form without D](#the-form-without-d))
- Usable when: bind only. Linux / Android with `/proc` usable. D can be created nowhere
- Not usable when: `/proc/self/fd/<fd>` cannot be resolved, the spelling does not fit the sockaddr
- Reach: a file name up to about 72 (it varies with the fd's digits)
- What is lost: `respelled`

#### fork-sockdir

- How: a forked child `fchdir(<socket's directory fd>)`s and binds by `.sockat.XXXXXXXXXX/<file name>` ([the form without D](#the-form-without-d), [The forked child](#the-forked-child))
- Usable when: bind only. D can be created nowhere, and the earlier routes cannot be used ([the form without D](#the-form-without-d))
- Not usable when: when the spelling does not fit the sockaddr, `ENAMETOOLONG`
- Reach: a file name up to the sockaddr length − 19 (88 on Linux / illumos, 84 on Apple OSes / BSD)
- What is lost: `respelled` and `forked`

#### proc-direct

- How: open the socket's directory and connect by `/proc/self/fd/<fd>/<file name>`
- Usable when: a fallback of the connect variants. Linux / Android with `/proc` usable
- Not usable when: the socket's directory cannot be opened, `/proc/self/fd/<fd>` cannot be stat'ed, the spelling does not fit the sockaddr
- Reach: a file name up to about 90 (it varies with the fd's digits)
- What is lost: nothing
- A bind never uses it ("[Order tried](#order-tried)")

#### proc-held

- How: create D (steps 1, 2 and 5 of [D and R](#d-and-r)), create the symlink `s` in it with `symlinkat`, pointing to the socket file, and connect by `/proc/self/fd/<Dfd>/s`. `s` is removed only if this call created it
- Usable when: a fallback of the connect variants. Linux / Android with `/proc` usable
- Not usable when: D or `s` cannot be created
- Reach: any file name, since the file name does not appear in the spelling
- What is lost: nothing

#### relative

- How: connect by the path relative to the cwd. Only the string is rewritten; no `chdir` ([Building the relative path](#building-the-relative-path))
- Usable when: a fallback of the connect variants. The original path is absolute
- Not usable when: the relative path is over the sockaddr length, the directory of the spelling built does not match the original by `(st_dev, st_ino)`, the cwd has already changed
- Reach: a relative path within the sockaddr length (107 on Linux / Android / illumos, 103 on Apple OSes / BSD)
- What is lost: nothing
- A bind never uses it ("[Order tried](#order-tried)")

#### widened

- How: connect with the original path, failing that the relative path, in a sockaddr whose `sun_len` and address length are `2 + path length`
- Usable when: a fallback of the connect variants. Apple OSes. The path is at most 253 bytes
- Not usable when: the kernel answers `EINVAL` / `ENAMETOOLONG`
- Reach: the original or relative path up to 253
- What is lost: nothing
- A bind never uses it ("[Order tried](#order-tried)")

#### symlink

- How, for a bind: `bind_any` only. Create in a base a symlink to the realpath of the socket's directory, bind by `<base>/sockat.XXXXXXXXXX/<file name>`, and remove it at once ([symlink base and name](#symlink-base-and-name))
- Usable when, for a bind: none of the default bind's routes can be used (where it would give `ENAMETOOLONG`)
- Not usable when, for a bind: for every candidate, the spelling does not fit the sockaddr, the base does not meet the conditions, or the symlink cannot be created. Then `ENAMETOOLONG`
- Reach, for a bind: the file name up to the length that fits the sockaddr − (the length of the base's spelling + 19)
- What is lost, for a bind: `respelled` for a base only the owner can write to (only oneself can recreate the spelling), `respelled` and `recreatable-spelling` for a shared base (other users can recreate the spelling, and if a higher layer or user unlinks by the spelling, it can make them remove a same-named file in a directory the other side chose)
- How, for a connect: create a symlink to the socket file in a safe base, connect by `<base>/sockat.XXXXXXXXXX`, and remove it at once ([symlink base and name](#symlink-base-and-name))
- Usable when, for a connect: a fallback of the connect variants. All but FreeBSD
- Not usable when, for a connect: for every candidate, the spelling does not fit the sockaddr, the base is unsafe, or the symlink cannot be created
- Reach, for a connect: any file name, since the file name does not appear in the spelling (the spelling `<base>/sockat.XXXXXXXXXX` within the sockaddr length)
- What is lost, for a connect: nothing (a connect's spelling is left nowhere on the peer)

#### at-direct

- How: open the socket's directory and connect with `connectat(fd, <file name>)`. Not through D
- Usable when: a fallback of the connect variants. FreeBSD
- Not usable when: the socket's directory cannot be opened, the file name is over 103 bytes
- Reach: a file name up to 103
- What is lost: nothing

#### fork-direct

- How: a forked child `fchdir(<socket's directory fd>)`s and connects by the file name ([The forked child](#the-forked-child)). Not through D. On Apple OSes the widened sockaddr is used when the kernel takes it
- Usable when: the `connect_any` variants only. No other route can be used
- Not usable when: when the spelling does not fit the sockaddr (the widened sockaddr on Apple OSes), `ENAMETOOLONG`
- Reach: a file name up to 107 on Linux / Android / illumos, 253 on Apple OSes, 103 on BSD
- What is lost: `forked`
- `connect` / `connect_nonblocking` return `ENAMETOOLONG` when they reach it

### D and R

Used by the routes through D ([thread-cwd](#thread-cwd), [at](#at), [proc](#proc), [fork](#fork)). [proc-held](#proc-held) uses steps 1, 2 and 5.

1. Open the base ([Where D is created](#where-d-is-created)) and hold its fd; inside it, `mkdirat` D with mode 0700. The name is `sockat.` (`.sockat.` in the socket's directory) + 10 characters from 62 alphanumerics (the OS's secure random source). Draw a new name on `EEXIST`; give up after 16
2. Open D (`O_PATH | O_DIRECTORY | O_NOFOLLOW` on Linux, `O_SEARCH | O_DIRECTORY | O_NOFOLLOW` on Apple OSes (`O_RDONLY` if the kernel answers `EISDIR` / `EINVAL`), `O_RDONLY | O_DIRECTORY | O_NOFOLLOW` on other OSes. `O_PATH` and `O_SEARCH` open even when the umask removed the owner's read permission). `fstat` that it is a directory, owned by the effective uid, with no permission for group or other, then settle it to 0700
   - An `O_PATH` fd: `chmod("/proc/self/fd/<fd>", 0700)` if `/proc` is usable. Otherwise reopen D by name with `O_RDONLY | O_DIRECTORY | O_NOFOLLOW`, confirm its `(st_dev, st_ino)` equals the first fd's, and `fchmod` (`fchmod` on an `O_PATH` fd fails with `EBADF`)
   - Any other fd: `fchmod`
   - If, after the check passed, D cannot be reopened or settled, it counts as "cannot create" and step 5 cleans D up
3. Create R inside D: `symlinkat(<realpath of the socket's directory>, Dfd, R)`. R's name is 10 characters from 62 alphanumerics (no `sockat.`). Draw a new name on `EEXIST`; give up after 16
4. Bind / connect by `R/<file name>` relative to D's fd (the means are in each route's section)
5. Cleanup: remove R with `unlinkat(Dfd, R)` only if this call created it. Remove D with `unlinkat(base fd, D's name, AT_REMOVEDIR)` only when the check in step 2 passed and `fstatat(base fd, D's name, AT_SYMLINK_NOFOLLOW)` gives the same `(st_dev, st_ino)` as the fd. Close the fds. This happens on success and on failure. A failure to remove is ignored

- The spelling `R/<file name>` is 11 bytes + the file name
- R has a random name to prevent accidents (so that the spelling, resolved later, does not hit something that happens to have the same name in the cwd etc.). It is not a defense against other users (the spelling may be visible to them; `respelled` in "[What is lost](#what-is-lost)")
- After cleanup R exists nowhere, so the spelling the kernel reports, resolved later in another context such as the process's cwd, hits no unrelated file
- A D that failed the check is someone else's; it and its contents are left alone
- When D just created cannot be opened (the umask removed the owner's permission; on OSes that open with `O_SEARCH` / `O_RDONLY`), if `fstatat(base fd, D's name, AT_SYMLINK_NOFOLLOW)` meets the same conditions as step 2 (a directory, owned by the effective uid, no permission for group and other), remove it with `unlinkat(base fd, D's name, AT_REMOVEDIR)` and go to the next base as "cannot create". Even if it is swapped between the check by name and the removal, `AT_REMOVEDIR` removes only an empty directory ([DR-0012](decisions/DR-0012-own-directory-and-thread-cwd.md), Japanese)
- The length, and whether a way can be used (as far as can be told), are checked before D is created. If not usable, nothing is created and the next is tried
- The caller creates the socket and holds D's fd. For a non-blocking connect it makes the socket non-blocking first. The listen after a bind is done by the caller

### Where D is created

| Order | Base | Condition |
|---|---|---|
| 1 | `${TMPDIR:-/tmp}` | a relative path is fine too (opened once and held by fd) |
| 2 | `/tmp` | only when 1 fails. Skipped when spelled the same as 1 |
| 3 | the socket's directory | only when 2 fails too. The name is `.sockat.XXXXXXXXXX` (it is the user's directory, so a leftover is recognizable as sockat's and stays inconspicuous). A bind should be able to write there; a connect not necessarily |

- "Fails" means: the base cannot be opened, D cannot be created, names are exhausted, no random bytes, the check in step 2 of [D and R](#d-and-r) fails, or R cannot be created
- When D can be created nowhere, a bind goes on to [the form without D](#the-form-without-d)
- When D can be created nowhere, the connect variants go on to the fallback routes ([Fallback routes (connect variants)](#fallback-routes-connect-variants))
- Neither the base's safety (sticky etc.) nor its length matters. D is held by fd, and the base does not appear in the spelling

### The form without D

Used by a bind when D can be created nowhere. [thread-cwd-sockdir](#thread-cwd-sockdir), [at-sockdir](#at-sockdir), [proc-sockdir](#proc-sockdir) and [fork-sockdir](#fork-sockdir) take this form.

- Create an R in the socket's directory (named `.sockat.XXXXXXXXXX`, pointing to the socket's directory's realpath) and, resolving against the socket's directory fd instead of D's, bind by `.sockat.XXXXXXXXXX/<file name>`
- The means are tried in the same order as with D (thread-cwd-sockdir (at-sockdir on FreeBSD) → proc-sockdir → fork-sockdir)
- The spelling is 19 bytes + the file name
- Cleanup: `unlinkat(<socket's directory fd>, R)` only if this call created R. On success and on failure. A failure to remove is ignored (as in step 5 of [D and R](#d-and-r))
- If the socket's directory cannot be opened or R cannot be created either, `ENAMETOOLONG`

### The throwaway thread

Used by [thread-cwd](#thread-cwd) and [thread-cwd-sockdir](#thread-cwd-sockdir).

- The caller waits until the throwaway thread finishes before cleaning up R and D and closing the fd. Even if the wait is interrupted (Python's `KeyboardInterrupt` and the like), nothing is cleaned up until the thread finishes (if an fd closed early has its number reused, the thread moves into an unrelated directory and binds there)
- The thread is a throwaway one sockat creates, discarded after use. The caller's thread's cwd is never touched (restoring with `pthread_fchdir_np(-1)` could drop a per-thread cwd the caller set)
- On Linux, `unshare` is not called while a seccomp filter is in place. Some filters refuse it by killing the process (SIGSYS) (systemd's `SystemCallFilter=` by default)
- A failing `fchdir` after `unshare` (`EACCES` etc.) is a real failure and is returned
- `pthread_fchdir_np` is a private libSystem API (the `__pthread_fchdir` syscall). It is looked up at run time

### The forked child

Used by [fork](#fork), [fork-sockdir](#fork-sockdir) and [fork-direct](#fork-direct). The fd the child `fchdir`s into and the spelling are in each route's section.

1. The parent creates the socket, holds the fd and builds the sockaddr before forking. For a non-blocking connect it makes the socket non-blocking before the fork
2. The child does `fchdir(fd)` → `bind` / `connect` by the spelling → `_exit(result)` (0 is success, 1–255 an errno)
3. The parent `waitpid`s for that pid only, then cleans up R and D. The listen after a bind is always done by the parent ([DR-0010](decisions/DR-0010-fork-bind-listen-by-parent.md), Japanese)

- The child's section uses async-signal-safe calls only (no allocation, locks, or the language's cleanup)
- If `waitpid` fails with `ECHILD` (someone else reaped the status), read the result from the socket: for a bind whether `getsockname` holds a path, for a connect whether `getpeername` succeeds. A failure is a generic error

### Fallback routes (connect variants)

Tried when the routes through D cannot be used (no means, D cannot be created, the spelling does not fit).

| OS | Order tried |
|---|---|
| Linux / Android (`/proc` usable) | [proc-direct](#proc-direct) → [proc-held](#proc-held) → [symlink](#symlink) |
| Linux / Android (`/proc` not usable) | [relative](#relative) → [symlink](#symlink) |
| macOS / iOS and the other Apple OSes | [relative](#relative) → [widened](#widened) → [symlink](#symlink) |
| FreeBSD | [at-direct](#at-direct) |
| NetBSD / OpenBSD / illumos / other Unix | [relative](#relative) → [symlink](#symlink) |

- The target of proc-held's `s` and of symlink's symlink is the socket file as spelled (a relative path gets the cwd prepended)

### Building the relative path

Used by [relative](#relative).

1. If the path starts with a spelling of the cwd (`getcwd`, or `$PWD` when its `stat` `(st_dev, st_ino)` matches that of `.`), strip it, comparing whole components
2. Only when 1 is not within the sockaddr length, resolve the socket's directory and the cwd with `realpath` and build a spelling that climbs with `..`
3. Use the shorter. Before using it, check that the relative directory and the original directory have the same `(st_dev, st_ino)`, and that the cwd's `(st_dev, st_ino)` is the same as before 1. Otherwise the route is not usable
4. If the cwd's `(st_dev, st_ino)` has changed after the connect, discard the result and return a generic error

### symlink base and name

Used by [symlink](#symlink).

| Item | Specification |
|---|---|
| base candidates | connect: `TMPDIR` (when a non-empty absolute path), then `/tmp`<br>bind (`bind_any`): `XDG_RUNTIME_DIR` (when a non-empty absolute path), `TMPDIR` (same), then `/tmp`<br>A candidate with the same spelling is tried once |
| base only the owner can write to | stat'ed following symlinks; a directory, owned by the effective uid, with `mode & 0o022 == 0` |
| shared base | stat'ed following symlinks; a directory, sticky bit set, owned by root or the effective uid |
| safe base | a base only the owner can write to, or a shared base. A connect uses either, candidates in order |
| how a bind tries | among the candidates, the bases only the owner can write to in order; if none, the shared bases in order |
| symlink target | connect: the socket file<br>bind: the realpath of the socket's directory |
| name | `sockat.` + 10 characters from 62 alphanumerics, taken from the OS's secure random source |
| collision | on `EEXIST` draw a new name. Give up after 16 attempts and treat the candidate as not usable |
| cleanup | removed whether the bind / connect succeeds or fails. A failure to remove is ignored |

- For each candidate, check the spelling's length and the base's safety before creating anything. A candidate that does not fit, is unsafe, or where nothing can be created gets nothing and the next is tried

## How a failing route is treated

- When a route actually binds / connects and fails (`ENOENT`, `EADDRINUSE`, `ECONNREFUSED`, etc.), that error is returned and no later route or base is tried
- The next one is tried only when the route itself cannot be used ("Not usable when" in each route's section)
  - the spelling does not fit
  - D or R cannot be created in a base for D (the next base is tried)
  - the means of thread-cwd, at, proc and their `-sockdir` forms cannot be used
  - `/proc` not usable
  - in proc-held, D or `s` cannot be created
  - in widened, the kernel refuses the widened sockaddr
  - in symlink, the base is unsafe or the symlink cannot be created
  - in relative, the directory of the spelling built does not match the original by `(st_dev, st_ino)`, or the cwd has already changed
- A missing directory is `ENOENT` on every OS. The directory is looked up first, so this is settled before the length is judged
- `connect` / `connect_nonblocking` return `ENAMETOOLONG` just before [fork-direct](#fork-direct)

## Where a path stops being reached

When a path over the standard length becomes `ENAMETOOLONG` (the directory exists and D can be created; numbers in bytes).

| OS | `bind` | `connect` variants | `connect_any` variants |
|---|---|---|---|
| Linux / Android (`/proc` present) | file name > 96 | always reached ([proc-held](#proc-held)) | always reached |
| Linux / Android (no `/proc`) | file name > 96 | [thread-cwd](#thread-cwd) is not usable (file name > 96 or no thread cwd), [relative](#relative) > 107, and no [symlink](#symlink) | file name > 107, and no symlink |
| FreeBSD | file name > 92 | file name > 103 | file name > 103 |
| macOS / iOS and the other Apple OSes | file name > 92 | [thread-cwd](#thread-cwd) is not usable (file name > 92 or no thread cwd), both the original and the relative path > 253, and no symlink | file name > 253, and no symlink |
| NetBSD / OpenBSD / other BSD | file name > 92 | relative > 103, and no symlink | file name > 103, and no symlink |
| illumos | file name > 96 | relative > 107, and no symlink | file name > 107, and no symlink |

- On Linux without thread-cwd, a bind uses [proc](#proc) for a file name up to about 79 bytes, and [fork](#fork) beyond that up to 96
- `bind_any` reaches even where the bind's routes give `ENAMETOOLONG`, as long as the [symlink](#symlink) spelling (`<base>/sockat.XXXXXXXXXX/<file name>`) fits the sockaddr
- When D can be created nowhere, a bind reaches a file name of 88 (84 on Apple OSes / BSD, about 72 with [proc-sockdir](#proc-sockdir) alone) through the `-sockdir` routes (when R can be created in the socket's directory). The connect variants reach as far as the fallback routes do (proc-held is not usable)
- Full paths are passed when looking up the directory and so on, so a path over PATH_MAX (1024 on macOS, 4096 on Linux) is `ENAMETOOLONG`. That is outside sockat's responsibility

## Side effects of the fork route

| Scope | Side effect |
|---|---|
| visible to the peer (`connect_any` variants only) | the peer pid the server sees is that of the exited child. uid / gid are the caller's<br>Linux's `SO_PEERCRED` keeps the child's pid<br>macOS's `LOCAL_PEERPID` turns into the caller's pid once the caller sends |
| not visible to the peer (`bind` and the `connect_any` variants) | until it exits, the child holds copies of every fd. A socket or pipe another thread closes meanwhile stays open<br>the parent gets `SIGCHLD`<br>`pthread_atfork` handlers run<br>monitoring tools see a short-lived child<br>another thread's `waitpid(-1)` may reap the child |

- A bind has no side effect visible to the peer. The child only binds and the parent listens, so the server's peer information a client sees (macOS's `LOCAL_PEERPID` / `LOCAL_PEEREPID` / the audit token's pid and pidversion, Linux's `SO_PEERCRED` / `SO_PEERPIDFD`) is the parent's from before any send (measured 2026-11-18 on macOS 26.5.2 and Linux) ([DR-0010](decisions/DR-0010-fork-bind-listen-by-parent.md), Japanese)

## What differs from the standard for a long path

| Point | Detail |
|---|---|
| address the kernel reports | the bound side's `getsockname` and the connecting side's `getpeername` return `R/<file name>` (`/proc/self/fd/<fd>/R/<file name>` for [proc](#proc)). R no longer exists, so normally it hits nothing when resolved later (if the process's cwd is a place others can write to, other users can see and recreate the spelling; `respelled` in "[What is lost](#what-is-lost)"). The [symlink](#symlink) of `bind_any` returns `<base>/sockat.XXXXXXXXXX/<file name>`, which in a shared base other users can recreate. In a language where the address accessors of the standard types can be replaced (Python), they return the original path (Python's asyncio `stat`s / unlinks the listener's `getsockname` spelling). Where they cannot be replaced, the caller keeps the original path |
| directory looked up first | the routes that use R (those through D and the form without D) resolve the socket's directory with realpath when they create R. [proc-direct](#proc-direct), [relative](#relative), [at-direct](#at-direct) and [fork-direct](#fork-direct) look up the directory, then pass the file name. A rename or symlink swap in between is not reflected. [widened](#widened) and [symlink](#symlink) behave as the standard |
| another thread's chdir | relative returns a generic error if the cwd stayed changed in between. A change and change back is not seen |
| a socket's directory others can write to | in a socket's directory that is not sticky and that others can write to, the R of the form without D can be replaced between its creation and the bind, so the bind may land in another directory (if that name already exists there, `EADDRINUSE`; nothing is overwritten). The R inside D cannot be replaced, since D is 0700 |
| leftovers | if the process dies before removing D, R or a base's symlink, `sockat.XXXXXXXXXX` is left in the base, and `.sockat.XXXXXXXXXX` (D, or the R of the form without D) in the socket's directory. |

- NUL anywhere but at the start is an invalid argument even in a short path. A language whose standard silently truncates at NUL (Go etc.) says so under "differs from the standard" in its README

## Errors

| Situation | Error |
|---|---|
| no directory / nothing to connect to | `ENOENT` |
| something other than a directory where the directory should be | `ENOTDIR` |
| a file already exists where bind would create the socket | `EADDRINUSE` |
| a socket file nobody listens on | `ECONNREFUSED` |
| backlog full | Linux: `EAGAIN` for a non-blocking connect (a blocking one waits); macOS: `ECONNREFUSED` |
| fits no route; for the `connect` variants also when only fork-direct would reach it | `ENAMETOOLONG` |
| path over the standard length that does not end with a name | invalid argument |
| path containing NUL anywhere but at the start (at any length) | invalid argument |
| the cwd changed during relative | generic error |
| the forked child did not exit normally, or its status was reaped elsewhere and the socket was not bound / connected | generic error |

- OS errors are returned so that the errno can be read in the language's usual way
- Each implementation chooses the types for "invalid argument" and "generic error"

## What each implementation must do

- Follow the routes and order above. Skip a route the language cannot build (treat it as not usable and go on), and show it in the README as an OS × route table
- In a language that brings a socket it created into the standard type, check that a socket connected through widened does not break that step or the address lookups. If it breaks, treat widened as a route the language cannot build and skip it
- Keep the routes out of the public API. Tests force each route by calling it directly from inside the package
- Make the parts that read the environment (where D is created, the symlink base candidates, the location of `/proc/self/fd`, whether an Apple OS takes the widened sockaddr, whether the thread cwd can be used) replaceable from tests
- Link this specification from the README and manual. Before introducing behavior that differs from it, change this specification first

## What implementations test

| Aspect | What to check |
|---|---|
| short path boundary | exactly the standard length goes to the standard unchanged; one byte more goes to the routes (check the boundary with the standard itself) |
| routes through D | with one forced, neither the process's cwd nor the calling thread's cwd changes, the socket is created at the original path and data flows, the peer pid is the caller's, and nothing remains in the base after cleanup |
| returned spelling | after a bind, unlinking / stat'ing the returned spelling (`getsockname`) as is hits no unrelated file (a same-named file in the cwd, a same-named file in another directory that got the reused fd number) |
| swapped directory | a directory swapped between creating and opening D (another owner, or permission for group / other) is neither used nor emptied |
| where D is created | when D cannot be created in `TMPDIR`, `/tmp` is used, and failing that the socket's directory with a `.sockat.` name. A relative or deep `TMPDIR` works. When it can be created nowhere, a bind takes the form without D (thread-cwd-sockdir → proc-sockdir → fork-sockdir) and the connect variants the fallback routes |
| ways not usable | with thread-cwd made unusable, Linux with `/proc` goes on to proc. When that is not usable either, a bind goes on to fork (the peer is the parent) and the connect variants to the fallback routes |
| fallback routes | with each forced, the socket is reached and nothing remains in the base. For symlink, an unsafe base is skipped, a too deep `TMPDIR` falls back to `/tmp`, colliding names are skipped and the attempts stop at 16 |
| no retry on failure | `ENOENT` / `EADDRINUSE` / `ECONNREFUSED` are returned and nothing is created on later routes or bases |
| connect and fork | the `connect` variants return `ENAMETOOLONG` when only fork-direct reaches; the `connect_any` variants reach and `losses` is `forked` only |
| `bind_any` | where the default bind gives `ENAMETOOLONG` it reaches through symlink. With a base only the owner can write to, that base is used and `losses` is `respelled` only; with only a shared base, `losses` is `respelled` and `recreatable-spelling`. Nothing remains in the base. Where a default route reaches, `losses` is that route's |
| D that cannot be opened | when the umask removed the owner's permission and D just created cannot be opened, nothing remains in the base |
| relative and cwd | a cwd change during relative is a generic error |
| fork | a client connected to a server bound through fork or fork-sockdir sees the parent as the peer (before and after any send); the peer pid behavior of fork-direct; reading the result with `SIGCHLD` set to `SIG_IGN` |
| macOS | a 253-byte path goes through widened for the connect variants. A bind never uses widened |
| non-blocking connect | a full backlog fails without waiting |
| path not ending with a name, NUL anywhere but at the start | invalid argument, nothing created. NUL even for a short path. A leading NUL (abstract) goes to the standard |
| address the kernel reports | reading it does not fail for a long path. Where the accessors can be replaced, the listener, accepted and connected sockets return the original path, and the language's usual higher layers (Python's asyncio `start_unix_server(sock=...)` etc.) behave as for a short path without extra arguments |
| `_ex` | `discard()` removes the file and does not close the listener. If another file has replaced it in between, it is not removed |

- The routes differ per OS, so run at least on macOS and Linux. Other Unixes run in CI VMs
- Tests that change process-wide settings such as the cwd or signal handling run inside a child process
- The fork route's child briefly holds copies of every fd, so create "a socket nobody listens on" in a separate process

## Open questions

- Android and the Apple OSes other than macOS are not checked at all
- NetBSD / OpenBSD / illumos: the peer credentials are not checked
- That a non-blocking connect never answers `EINPROGRESS` is checked only on Linux and macOS
