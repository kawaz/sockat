# sockat specification

> English | [日本語](./SPEC-ja.md)

How sockat behaves, independent of the language. Every implementation follows it. The decisions and the rejected alternatives are in [docs/decisions](decisions/INDEX.md) (Japanese); what is specific to a language (types, runtime integration, memory safety) is in the README and manual of each language's repository ([sockat-rs](https://github.com/kawaz/sockat-rs), [sockat-py](https://github.com/kawaz/sockat-py), [sockat-go](https://github.com/kawaz/sockat-go)).

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
| bind with cleanup and diagnostics | `bind_ex` | `sockat.ex.bind` | `ListenEx` | tried | (does not wait) | a standard listener, and `discard()` / `losses` / `route` / `skipped` |
| connect | `connect` | `connect` | `Dial` | never tried | yes (Go's `Dial` does not wait) | a standard stream |
| non-blocking connect | `connect_nonblocking` | `connect_nonblocking` | none (`Dial` does not wait) | never tried | no | a non-blocking standard stream |
| connect with diagnostics | `connect_ex` | `sockat.ex.connect` | `DialEx` | tried only with the last resort | yes (Go's `DialEx` does not wait) | a standard stream, and `losses` / `route` / `skipped` |
| the same, non-blocking | `connect_nonblocking_ex` | `sockat.ex.connect_nonblocking` | none (`DialEx` does not wait) | tried only with the last resort | no | as above (the stream is non-blocking) |

- Other languages follow their own naming conventions. The behavior follows the table above
- Python's `_ex` are `bind` / `connect` / `connect_nonblocking` in the submodule `sockat.ex`, and whether to use the last resort is chosen by the argument `last_resort` (to keep them apart from the standard `socket.connect_ex`; [DR-0015](decisions/DR-0015-ex-with-last-resort-and-diagnostics.md), Japanese)
- Go's `Dial` / `DialEx`, like the standard `net.DialUnix`, never wait (when the backlog is full, Linux gives `EAGAIN` at once and macOS `ECONNREFUSED`). This is the case of [DR-0003](decisions/DR-0003-single-connect-when-standard-never-blocks.md) (Japanese), and there is no separate non-blocking connect
- The listener / stream returned is of the same type the standard returns, so it is a drop-in replacement for the standard
- `_ex` (`bind_ex`, `connect_ex`, `connect_nonblocking_ex`) is provided once for each default operation. `connect_ex` and `connect_nonblocking_ex` together are called the `connect_ex` variants ([DR-0015](decisions/DR-0015-ex-with-last-resort-and-diagnostics.md), Japanese)
- The default operations (`bind`, `connect`, `connect_nonblocking`) never use the last resort and return no diagnostics
- `bind_ex` remembers the realpath and `(st_dev, st_ino)` of the bound socket file; `discard()` removes the file only when that path still has the same `(st_dev, st_ino)`. `discard()` does not close the listener (the user does) ([DR-0015](decisions/DR-0015-ex-with-last-resort-and-diagnostics.md), Japanese)
  - It remembers them right after the bind succeeds (inside the route, before returning the listener). If they cannot be remembered, it closes the listener, leaves the file, and returns an error (it does not hand back a `discard()` that cannot remove anything as a success)
  - For a relative path, compare the process's cwd `(st_dev, st_ino)` before anything about the path is looked up and after both the bind and the realpath taken for remembering; if they differ, treat it like the case where they cannot be remembered (if another thread changes the cwd in between, the bind lands under the new cwd while the remembered file is under the old one, so an unrelated same-named file under the old cwd could be remembered and removed by `discard()`. A change and change back is not seen)
  - The path argument is turned into a string once at the entry, and that value is used for remembering, binding and returning alike (so that a path type that can return a different value on each call never makes the remembered file differ from the bound one)
  - `discard()` succeeds when the file is already gone and when it has been replaced by another file and is left alone. It fails when the check cannot be made (`lstat` fails with something other than `ENOENT` / `ENOTDIR`) and when the removal itself fails (it does not report success when it cannot tell whether anything was removed)
  - A replacement is told apart when it happens while the listener is open (while open, the kernel keeps holding the socket file, so its number is not reused). Something removed and recreated after the listener is closed can get the same `(st_dev, st_ino)` on a filesystem that reuses numbers at once (ext4, BSD UFS / FFS), and `discard()` may remove it (the same as removing by the original path). Each language's docs recommend calling `discard()` before closing the listener ([findings](findings/2026-11-19-inode-reuse-after-close.md), Japanese)
  - Someone who can write to the socket's directory swapping the file between the check and the removal, or between the bind and the remembering, cannot be prevented (POSIX has no way to remove by inode)
- The only thing an argument of `_ex` chooses is whether to use the last resort. By default it is not used. There is no way to combine routes freely ([DR-0015](decisions/DR-0015-ex-with-last-resort-and-diagnostics.md), Japanese). Without the last resort, `_ex` tries the same routes in the same order as the default operation
- The last resort reaches even by losing something when none of the default routes can be used. No pid is returned
  - `bind_ex`: when none of the default bind's order ("[Order tried](#order-tried)") can be used, [symlink-dir](#symlink-dir) (a base only the owner can write to first; if none, a shared base)
  - the `connect_ex` variants: when none of the default connect's order ("[Connect order](#connect-order)") can be used, [fork-cwd-direct](#fork-cwd-direct). Only in a language that can build the fork routes. A language that cannot puts fork-cwd-direct into `skipped` with the reason and goes on
  - a bind's [fork-cwd](#fork-cwd) and [symlink-file](#symlink-file) are default routes, not the last resort
- On success `_ex` returns these three ([DR-0015](decisions/DR-0015-ex-with-last-resort-and-diagnostics.md), Japanese)
  - `losses`: the names of what was lost on the route taken (the names in "[What is lost](#what-is-lost)"; empty when nothing was lost). Branch on it. The names are a promise: they are never changed, only added (the documentation says to read an unknown name only as "something was lost"). The names have no order or inclusion among them
  - `route`: the name of the route taken
  - `skipped`: the routes tried and found unusable, in the order tried. Each element is `{ name, reason }` (the route name and why it was unusable). Every route tried before `route` was unusable, so there is no "was it usable" field
  - `skipped` holds every unusable route among those this call tries in order ("[Order tried](#order-tried)" and, for a connect, the one row of "[Connect order](#connect-order)" chosen by the OS and run-time state such as whether `/proc` is usable; with the last resort, the last resort's route at its end). For a long path [standard](#standard) is included (the reason being that the path is too long). When D can be created nowhere and the `-sockdir` routes are taken, both the routes through D and the `-sockdir` routes are included. Routes not in that OS's or state's row are not included. A route that tried several base candidates is one element
  - The names in `route` and `skipped` and the `reason` are for diagnostics and promise nothing about their content (routes are added and changed)
  - The field and type names follow each language's conventions. The names of what is lost may be represented in the language's own way (an enum etc.), but as strings they equal the names in this SPEC
- When `_ex` fails, the error carries `skipped` too. When a route actually bound / connected and failed, its name (`route`) is attached as well (`standard` when the standard fails on a short path; none for a failure before any route is tried, such as a missing directory, nor for `ENAMETOOLONG`, where none could be used). On a failure before any route is tried, `skipped` is empty too (the length is judged after the socket's directory is looked up, so `standard` has not been tried yet) ([DR-0015](decisions/DR-0015-ex-with-last-resort-and-diagnostics.md), Japanese)
  - How they are attached follows each language's conventions. The errno of an OS error stays readable ([Errors](#errors))
- A language whose standard connect never blocks (Node.js, Go, etc.) provides one connect in the standard's own form ([DR-0003](decisions/DR-0003-single-connect-when-standard-never-blocks.md), Japanese)
- `connect` / `connect_nonblocking` and the `connect_ex` variants without the last resort never try [fork-cwd-direct](#fork-cwd-direct); they return `ENAMETOOLONG` where none of "[Connect order](#connect-order)" can be used
- A non-blocking connect makes the socket non-blocking before connecting and returns it that way. When the peer's backlog is full it fails without waiting. `EINPROGRESS` is returned as an error and the socket is closed
- A socket the implementation creates itself gets the same settings as one the language's standard creates (close-on-exec, `SO_NOSIGPIPE`, the listen backlog, etc.). There is no way to specify the backlog
- When the listener is closed, the socket file is treated as the standard treats it for a short path (Go's standard removes it). For a long path it is not removed, even where the standard removes it (the spelling the kernel holds is not the original path). A language whose standard removes it says so under "differs from the standard" in its README. Removal is `bind_ex`'s `discard()`
  - The listener of `bind_ex` does not remove the file when closed, even for a short path (only `discard()` removes it; Go's form in [DR-0015](decisions/DR-0015-ex-with-last-resort-and-diagnostics.md), Japanese)

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
- How a directory is opened (the base, the socket's directory): `O_SEARCH` on Apple OSes (`O_RDONLY` if the kernel answers `EISDIR` / `EINVAL`), `O_PATH | O_DIRECTORY` on Linux, `O_RDONLY | O_DIRECTORY` elsewhere
- The socket's directory is looked up first with `stat`, and its realpath is taken. When it is missing, `ENOENT`; when it is not a directory, `ENOTDIR`; when the realpath cannot be taken, that error (all before the length is judged or D is created). Only the routes that need an fd of the socket's directory ([proc-direct](#proc-direct), [at-direct](#at-direct), [fork-cwd-direct](#fork-cwd-direct), and the routes whose names end in `-sockdir`) open it, and when it cannot be opened that route is unusable (`O_RDONLY` on other OSes cannot open a directory without read permission)
- No route changes the calling process's cwd or the calling thread's cwd

### Route names

The routes are called by the names below. A name is "means + what it is about"; the means are thread-cwd, fork-cwd, proc, at, symlink-file, symlink-dir, relative and widened. The suffix `-sockdir` is the form that puts R in the socket's directory ([the form without D](#the-form-without-d)), and `-direct` the form that passes the file name without going through R.

The bind table is in the order tried. The connect table is in an order from which each OS's order ("[Connect order](#connect-order)") is obtained by dropping the routes that OS does not try. A name that appears for both bind and connect is one route; the differences are in that route's section. The names of what is lost are from "[What is lost](#what-is-lost)".

bind:

| Name | What it does | OS | What is lost |
|---|---|---|---|
| [standard](#standard) | hand the path to the standard unchanged | all | `cwd-relative` for a relative path |
| [symlink-file](#symlink-file) | create in a base a symlink to the socket file and use `<base>/sockat.XXXXXXXXXX` | Apple OSes, NetBSD, OSes not yet checked (measured to follow a symlink in the last component on bind: macOS and NetBSD. Not tried on the OSes measured not to follow (Linux / Android, FreeBSD, OpenBSD, illumos). On OSes not yet checked it is told apart at run time) | `respelled` |
| [thread-cwd](#thread-cwd) | move a throwaway thread's cwd into D, then `R/<file name>` | Linux / Android / Apple OSes | `respelled` |
| [at](#at) | `bindat(Dfd, R/<file name>)` | FreeBSD | `respelled` |
| [proc](#proc) | `/proc/self/fd/<Dfd>/R/<file name>` | Linux / Android with `/proc` usable | `respelled` |
| [fork-cwd](#fork-cwd) | a forked child `fchdir(Dfd)`s, then `R/<file name>` | all | `respelled`<br>`forked` |
| [thread-cwd-sockdir](#thread-cwd-sockdir) | thread-cwd in the form without D (R inside the socket's directory, `.sockat.XXXXXXXXXX/<file name>`) | Linux / Android / Apple OSes | `respelled` |
| [at-sockdir](#at-sockdir) | at in the form without D | FreeBSD | `respelled` |
| [proc-sockdir](#proc-sockdir) | proc in the form without D | Linux / Android with `/proc` usable | `respelled` |
| [fork-cwd-sockdir](#fork-cwd-sockdir) | fork-cwd in the form without D | all | `respelled`<br>`forked` |
| [symlink-dir](#symlink-dir) | create in a base a symlink to the socket's directory and use `<base>/sockat.XXXXXXXXXX/<file name>` (only `bind_ex` with the last resort) | all | a base only the owner can write to: `respelled`<br>a shared base: `respelled` and `recreatable-spelling` |

- The four `-sockdir` routes are tried, in the same order, only when D can be created nowhere ([the form without D](#the-form-without-d))
- Only `bind_ex` with the last resort tries symlink-dir, where the default bind gives `ENAMETOOLONG`

connect:

| Name | What it does | OS | What is lost |
|---|---|---|---|
| [standard](#standard) | hand the path to the standard unchanged | all | nothing |
| [proc-direct](#proc-direct) | `/proc/self/fd/<fd>/<file name>`, without R | Linux / Android with `/proc` usable | nothing |
| [relative](#relative) | the path relative to the cwd | Linux / Android with `/proc` not usable<br>Apple OSes<br>NetBSD / OpenBSD / illumos / other Unix | nothing |
| [widened](#widened) | a widened sockaddr | Apple OSes | nothing |
| [at-direct](#at-direct) | `connectat(<socket's directory fd>, <file name>)` | FreeBSD | nothing |
| [thread-cwd](#thread-cwd) | move a throwaway thread's cwd into D, then `R/<file name>` | Linux / Android / Apple OSes | nothing |
| [at](#at) | `connectat(Dfd, R/<file name>)` | FreeBSD | nothing |
| [proc](#proc) | `/proc/self/fd/<Dfd>/R/<file name>` | Linux / Android with `/proc` usable | nothing |
| [proc-held](#proc-held) | put `s`, pointing to the socket file, in D, then `/proc/self/fd/<Dfd>/s` | Linux / Android with `/proc` usable | nothing |
| [symlink-file](#symlink-file) | create in a base a symlink to the socket file and use `<base>/sockat.XXXXXXXXXX` | all but FreeBSD | nothing |
| [fork-cwd-direct](#fork-cwd-direct) | a forked child connects by the file name (only the `connect_ex` variants with the last resort) | all | `forked` |

- Which routes each OS tries, and in what order, is in "[Connect order](#connect-order)"

### What is lost

What taking the route loses compared to the standard. `_ex`'s `losses` returns these names (empty when nothing was lost).

| Name | What is lost | Attached when |
|---|---|---|
| [respelled](#respelled) | the address the kernel reports is not the original path | a bind took a route other than standard |
| [cwd-relative](#cwd-relative) | the spelling the kernel keeps is relative to the cwd | a bind took [standard](#standard) with a relative path (not an abstract name) |
| [forked](#forked) | the side effects of forking | [fork-cwd](#fork-cwd), [fork-cwd-sockdir](#fork-cwd-sockdir) or [fork-cwd-direct](#fork-cwd-direct) was taken |
| [recreatable-spelling](#recreatable-spelling) | the spelling can be recreated by other users | `bind_ex` took [symlink-dir](#symlink-dir) in a shared base as the last resort |

Each language's README / manual puts recommended code for how to avoid each, under a heading of the same name (run as a test).

#### respelled

- What happens: the bound side's `getsockname` (and the connecting side's `getpeername`) returns a spelling that is not the original path ("[What differs from the standard for a long path](#what-differs-from-the-standard-for-a-long-path)"). Even in a language whose standard removes the file when the listener is closed (Go's standard etc.) it is not removed
- Watch out for: do not unlink / `stat` the file by the spelling the kernel reports. The random name R in the spelling has been removed, so normally it hits nothing, but the spelling may be visible to other users (Linux's `/proc/net/unix`). If the process's cwd is a place others can write to (`/tmp` etc.), after another user sees and recreates it, unlinking by that spelling may remove a same-named file in a directory that user chose
- How to avoid: keep the original path and use it when removing. Use `bind_ex`'s `discard()`

#### cwd-relative

- What happens: the given relative path goes to the standard unchanged, and the kernel keeps a relative spelling
- Watch out for: unlinking / `stat`ing by that spelling (or by the given relative path) after the cwd changes hits another place. A hazard the standard already has rather than one a route introduced, but it is reported
- How to avoid: make the path absolute before the bind. Remove by the absolute path or `discard()` as well

#### forked

- What happens: a child is forked for a moment ("[Side effects of the fork route](#side-effects-of-the-fork-route)"). The child holds copies of every fd, the parent gets `SIGCHLD`, and `pthread_atfork` handlers run. In the `connect_ex` variants with the last resort the peer pid the server sees is that of the child
- Watch out for: a program that uses a `SIGCHLD` handler or `waitpid(-1)` may reap the child or mistake the result. A program that closes an fd to tell the peer EOF gets it across only after the child exits. The server on the other end of a `connect_ex` variant with the last resort cannot count on authorizing by the peer's pid
- How to avoid: do not use `waitpid(-1)` in other threads (wait by pid). For connect, not using the last resort means no fork. The fork-cwd of bind is a default route, so it cannot be avoided in a language that builds the fork routes

#### recreatable-spelling

- What happens: the spelling the kernel reports goes through a shared base (`/tmp` etc.) (`<base>/sockat.XXXXXXXXXX/<file name>`)
- Watch out for: the name is random, so it cannot be guessed in advance, but after the bind other users may see it (Linux's `/proc/net/unix`). If another user recreates it and then it is unlinked by that spelling, a same-named file in a directory the other user chose may be removed. The name's length is not the defense (the name is visible after the bind)
- How to avoid: do not remove by the spelling the kernel reports; remove by the original path or `discard()`. If you prepare a base only the owner can write to (`$XDG_RUNTIME_DIR`, or a `$TMPDIR` only the owner can write to), that base is used first and this name is not attached

- The names are a promise: they are never changed, only added. Read an unknown name only as "something was lost"
- The names have no order or inclusion among them (`forked` and `recreatable-spelling` do not include each other)
- A connect's spelling is left nowhere on the peer ("[Order tried](#order-tried)"), so the only name a connect gets is `forked`
- symlink-dir in a base only the owner can write to gets `respelled` only. A bind through symlink-file gets `respelled` only, whatever the base ([symlink-file](#symlink-file))

### Order tried

bind:

| Step | bind |
|---|---|
| 1 | [standard](#standard) (up to the standard length) |
| 2 | [symlink-file](#symlink-file) (Apple OSes, NetBSD, OSes not yet checked) |
| 3 | [thread-cwd](#thread-cwd) ([at](#at) on FreeBSD) |
| 4 | [proc](#proc) |
| 5 | [fork-cwd](#fork-cwd) |
| 6 | `ENAMETOOLONG` |

- A bind's symlink-file is not tried on the OSes measured not to follow (Linux / Android, FreeBSD, OpenBSD, illumos) (measured 2026-11-19: macOS and NetBSD follow). On the other OSes, when the bind fails, `lstat` the original path: if something is there, return that error (`EADDRINUSE` etc.); if nothing is there or it cannot be checked, take it that the bind did not follow, treat this route as unusable and try the next (if it was a real failure, the next route fails the same way and that is what is returned) ([DR-0016](decisions/DR-0016-bind-through-file-symlink.md), Japanese). The bind order on macOS is standard → symlink-file → thread-cwd → fork-cwd
- A bind's fork-cwd is tried when thread-cwd and proc cannot use the thread cwd / `/proc`, or the proc spelling does not fit. When D can be created nowhere, steps 3 to 5 are tried in the form without D ([thread-cwd-sockdir](#thread-cwd-sockdir) ([at-sockdir](#at-sockdir) on FreeBSD) → [proc-sockdir](#proc-sockdir) → [fork-cwd-sockdir](#fork-cwd-sockdir)). When the spelling does not fit the sockaddr, it is not tried, and the default routes end there with `ENAMETOOLONG` (`bind_ex` with the last resort goes on to [symlink-dir](#symlink-dir))
- A bind never uses [proc-direct](#proc-direct), [relative](#relative), [widened](#widened), [at-direct](#at-direct), or [symlink-dir](#symlink-dir) (the spelling would hit an unrelated file later, the address would be cut short and break whoever reads it, or the routes through D suffice). Only `bind_ex` with the last resort tries [symlink-dir](#symlink-dir) last, to reach even by losing something ([DR-0015](decisions/DR-0015-ex-with-last-resort-and-diagnostics.md), Japanese)

connect:

| Step | `connect` / `connect_nonblocking`, the `connect_ex` variants without the last resort | the `connect_ex` variants with the last resort |
|---|---|---|
| 1 | [standard](#standard) (up to the standard length) | same |
| 2 | the order for the OS ("[Connect order](#connect-order)") | same |
| 3 | `ENAMETOOLONG` | [fork-cwd-direct](#fork-cwd-direct) |

- A connect's spelling is left nowhere on the peer (the connecting socket is not bound), so a connect also uses routes that put no R in the spelling ([proc-direct](#proc-direct), [relative](#relative), [widened](#widened), [at-direct](#at-direct), [fork-cwd-direct](#fork-cwd-direct)). The only thing a connect loses is fork-cwd-direct's `forked`
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
- Usable when: Linux / Android / Apple OSes. For a bind, after [standard](#standard); for a connect, within "[Connect order](#connect-order)" (the position differs per OS)
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
- Usable when: FreeBSD. For a bind, after [standard](#standard); for a connect, after [at-direct](#at-direct) in "[Connect order](#connect-order)"
- Not usable when: D can be created nowhere ([Where D is created](#where-d-is-created)), the spelling does not fit the sockaddr
- Reach: a file name up to 92
- What is lost: `respelled` for a bind, nothing for a connect

#### proc

- How: create D and R ([D and R](#d-and-r)) and, without a thread, bind / connect by `/proc/self/fd/<Dfd>/R/<file name>`
- Usable when: Linux / Android with `/proc` usable. After [thread-cwd](#thread-cwd), for a bind and for a connect ("[Connect order](#connect-order)") alike
- Not usable when: `/proc/self/fd/<Dfd>` cannot be resolved, the spelling does not fit the sockaddr, D can be created nowhere ([Where D is created](#where-d-is-created))
- Reach: a file name up to about 79 (it varies with the fd's digits)
- What is lost: `respelled` for a bind, nothing for a connect
- The spelling's length depends on D's fd number, which is unknown until D is opened. Before creating D it is estimated, and it is checked again once D is open (if it does not fit, this route is treated as unusable and the next is tried. D is shared with later routes, so it is cleaned up once at the end of the call)
- Checking whether `/proc` is usable does not need an fd of the socket's directory (use the fd of `/` or of D)
- The spelling goes through R as well, so a reused fd number later hits no unrelated file
- Apart from what is lost, the same for bind and connect

#### fork-cwd

- How: create D and R ([D and R](#d-and-r)); a forked child `fchdir(Dfd)`s and binds by `R/<file name>` ([The forked child](#the-forked-child))
- Usable when: bind only. Tried when the earlier routes cannot be used ("[Order tried](#order-tried)")
- Not usable when: D can be created nowhere ([Where D is created](#where-d-is-created)). When the spelling does not fit the sockaddr, the default routes end here with `ENAMETOOLONG` (`bind_ex` with the last resort goes on to [symlink-dir](#symlink-dir))
- Reach: a file name up to the sockaddr length − 11 (96 on Linux / illumos, 92 on Apple OSes / BSD)
- What is lost: `respelled` and `forked`
- A connect never uses fork-cwd (the `connect_ex` variants with the last resort use [fork-cwd-direct](#fork-cwd-direct))

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

#### fork-cwd-sockdir

- How: a forked child `fchdir(<socket's directory fd>)`s and binds by `.sockat.XXXXXXXXXX/<file name>` ([the form without D](#the-form-without-d), [The forked child](#the-forked-child))
- Usable when: bind only. D can be created nowhere, and the earlier routes cannot be used ([the form without D](#the-form-without-d))
- Not usable when: when the spelling does not fit the sockaddr, the default routes end here with `ENAMETOOLONG` (`bind_ex` with the last resort goes on to [symlink-dir](#symlink-dir))
- Reach: a file name up to the sockaddr length − 19 (88 on Linux / illumos, 84 on Apple OSes / BSD)
- What is lost: `respelled` and `forked`

#### proc-direct

- How: open the socket's directory and connect by `/proc/self/fd/<fd>/<file name>`
- Usable when: the connect variants. Linux / Android with `/proc` usable. First in "[Connect order](#connect-order)" (after [standard](#standard))
- Not usable when: the socket's directory cannot be opened, `/proc/self/fd/<fd>` cannot be stat'ed, the spelling does not fit the sockaddr
- Reach: a file name up to about 90 (it varies with the fd's digits)
- What is lost: nothing
- A bind never uses it ("[Order tried](#order-tried)")

#### proc-held

- How: create D (steps 1, 2 and 5 of [D and R](#d-and-r)), create the symlink `s` in it with `symlinkat`, pointing to the socket file, and connect by `/proc/self/fd/<Dfd>/s`. `s` is removed only if this call created it
- Usable when: the connect variants. Linux / Android with `/proc` usable. After [proc](#proc) in "[Connect order](#connect-order)"
- Not usable when: D or `s` cannot be created
- Reach: any file name, since the file name does not appear in the spelling
- What is lost: nothing

#### relative

- How: connect by the path relative to the cwd. Only the string is rewritten; no `chdir` ([Building the relative path](#building-the-relative-path))
- Usable when: the connect variants. The original path is absolute. First in "[Connect order](#connect-order)" (after [standard](#standard))
- Not usable when: the relative path is over the sockaddr length, the directory of the spelling built does not match the original by `(st_dev, st_ino)`, the cwd has already changed
- Reach: a relative path within the sockaddr length (107 on Linux / Android / illumos, 103 on Apple OSes / BSD)
- What is lost: nothing
- A bind never uses it ("[Order tried](#order-tried)")

#### widened

- How: connect with the original path, failing that the relative path, in a sockaddr whose `sun_len` and address length are `2 + path length`
- Usable when: the connect variants. Apple OSes. The path is at most 253 bytes. After [relative](#relative) in "[Connect order](#connect-order)"
- Not usable when: the kernel answers `EINVAL` / `ENAMETOOLONG`
- Reach: the original or relative path up to 253
- What is lost: nothing
- A bind never uses it ("[Order tried](#order-tried)")

#### symlink-file

- How: create in a safe base a symlink `<base>/sockat.XXXXXXXXXX` pointing to the socket file as spelled (a relative path gets the cwd prepended), bind / connect by that spelling, and remove it at once, on success and on failure alike ([symlink base and name](#symlink-base-and-name))
- Usable when, for a bind: an OS whose bind follows a symlink in the last component (measured 2026-11-19: macOS and NetBSD follow; Linux / Android, FreeBSD, OpenBSD and illumos do not). Not tried on an OS measured not to follow; on other OSes it is tried after [standard](#standard) and whether it follows is told apart at run time
- Not usable when, for a bind: for every candidate, the spelling does not fit the sockaddr, the base is unsafe, or the symlink cannot be created. The kernel did not follow the symlink
- How following is told apart: not tried on the OSes measured not to follow (Linux / Android, FreeBSD, OpenBSD, illumos). On other OSes, when the bind fails (whatever the error), `lstat` the original path. If something is there, that error is returned and nothing further is tried ([How a failing route is treated](#how-a-failing-route-is-treated)). If nothing is there or it cannot be checked, the kernel is taken not to have followed it; the route is not usable and the next route is tried (it goes into `skipped`; if it was a real failure, the next route fails the same way and that is what is returned)
- Usable when, for a connect: the connect variants. All but FreeBSD. Last in "[Connect order](#connect-order)" (the `connect_ex` variants with the last resort then try [fork-cwd-direct](#fork-cwd-direct))
- Not usable when, for a connect: for every candidate, the spelling does not fit the sockaddr, the base is unsafe, or the symlink cannot be created
- Reach: any file name length, since the file name does not appear in the spelling `<base>/sockat.XXXXXXXXXX` (the spelling within the sockaddr length; the whole original path up to PATH_MAX)
- What is lost: `respelled` for a bind, nothing for a connect (a connect's spelling is left nowhere on the peer)
- For a bind, the address the kernel reports is the symlink's spelling `<base>/sockat.XXXXXXXXXX`. Unlinking by that spelling does not follow the symlink in the last component and only removes the entry in the base (in a shared sticky base, other users' entries cannot be removed). Unlike [symlink-dir](#symlink-dir) it never makes anyone remove an unrelated file, so `recreatable-spelling` is not attached

#### symlink-dir

- How: only `bind_ex` with the last resort. Create in a base a symlink to the realpath of the socket's directory, bind by `<base>/sockat.XXXXXXXXXX/<file name>`, and remove it at once ([symlink base and name](#symlink-base-and-name))
- Usable when: bind only. None of the default bind's routes can be used (where it would give `ENAMETOOLONG`)
- Not usable when: for every candidate, the spelling does not fit the sockaddr, the base does not meet the conditions, or the symlink cannot be created. Then `ENAMETOOLONG`
- Reach: the file name up to the length that fits the sockaddr − (the length of the base's spelling + 19). The spelling is always longer than `R/<file name>` (11 + the file name), so symlink-dir reaches further only when a means (thread cwd, `/proc`, fork, creating D and R) is unusable, never when the file name is merely too long
- What is lost: `respelled` for a base only the owner can write to (only oneself can recreate the spelling), `respelled` and `recreatable-spelling` for a shared base (other users can recreate the spelling, and if a higher layer or user unlinks by the spelling, it can make them remove a same-named file in a directory the other side chose)

#### at-direct

- How: open the socket's directory and connect with `connectat(fd, <file name>)`. Not through D
- Usable when: the connect variants. FreeBSD. First in "[Connect order](#connect-order)" (after [standard](#standard))
- Not usable when: the socket's directory cannot be opened, the file name is over 103 bytes
- Reach: a file name up to 103
- What is lost: nothing

#### fork-cwd-direct

- How: a forked child `fchdir(<socket's directory fd>)`s and connects by the file name ([The forked child](#the-forked-child)). Not through D. On Apple OSes the widened sockaddr is used when the kernel takes it
- Usable when: only the `connect_ex` variants with the last resort. Tried last, when none of the routes in "[Connect order](#connect-order)" can be used
- Not usable when: a language that cannot build the fork routes (it goes into `skipped` with the reason). When the spelling does not fit the sockaddr (the widened sockaddr on Apple OSes), `ENAMETOOLONG`
- Reach: a file name up to 107 on Linux / Android / illumos, 253 on Apple OSes, 103 on BSD
- What is lost: `forked`
- `connect` / `connect_nonblocking` and the `connect_ex` variants without the last resort never try it and return `ENAMETOOLONG`

### D and R

Used by the routes through D ([thread-cwd](#thread-cwd), [at](#at), [proc](#proc), [fork-cwd](#fork-cwd)). [proc-held](#proc-held) uses steps 1, 2 and 5.

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
- D is created at most once per call and shared by the routes that use it ([thread-cwd](#thread-cwd), [at](#at), [proc](#proc), [fork-cwd](#fork-cwd), [proc-held](#proc-held)). If it can be created nowhere, every route that uses D is skipped as unusable (it goes into `skipped`) and D is not retried
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
- When D can be created nowhere, the connect variants treat that route as not usable and go on to the next route in "[Connect order](#connect-order)"
- Neither the base's safety (sticky etc.) nor its length matters. D is held by fd, and the base does not appear in the spelling

### The form without D

Used by a bind when D can be created nowhere. [thread-cwd-sockdir](#thread-cwd-sockdir), [at-sockdir](#at-sockdir), [proc-sockdir](#proc-sockdir) and [fork-cwd-sockdir](#fork-cwd-sockdir) take this form.

- Create an R in the socket's directory (named `.sockat.XXXXXXXXXX`, pointing to the socket's directory's realpath) and, resolving against the socket's directory fd instead of D's, bind by `.sockat.XXXXXXXXXX/<file name>`
- The means are tried in the same order as with D (thread-cwd-sockdir (at-sockdir on FreeBSD) → proc-sockdir → fork-cwd-sockdir)
- The spelling is 19 bytes + the file name
- The `-sockdir` routes are tried only when an attempt to create D failed everywhere. When no route through D was usable (by length or means) and D was not created, they are not tried (their spelling is longer, so a route unusable by length is unusable as `-sockdir` too; likewise when no means exists). `skipped` then holds no `-sockdir` route
- Cleanup: `unlinkat(<socket's directory fd>, R)` only if this call created R. On success and on failure. A failure to remove is ignored (as in step 5 of [D and R](#d-and-r))
- If the socket's directory cannot be opened or R cannot be created either, the default routes end here with `ENAMETOOLONG` (`bind_ex` with the last resort goes on to [symlink-dir](#symlink-dir))

### The throwaway thread

Used by [thread-cwd](#thread-cwd) and [thread-cwd-sockdir](#thread-cwd-sockdir).

- The caller waits until the throwaway thread finishes before cleaning up R and D and closing the fd. Even if the wait is interrupted (Python's `KeyboardInterrupt` and the like), nothing is cleaned up until the thread finishes (if an fd closed early has its number reused, the thread moves into an unrelated directory and binds there)
- The thread is a throwaway one sockat creates, discarded after use. The caller's thread's cwd is never touched (restoring with `pthread_fchdir_np(-1)` could drop a per-thread cwd the caller set)
- On Linux, `unshare` is not called while a seccomp filter is in place. Some filters refuse it by killing the process (SIGSYS) (systemd's `SystemCallFilter=` by default)
- A failing `fchdir` after `unshare` (`EACCES` etc.) is a real failure and is returned
- `pthread_fchdir_np` is a private libSystem API (the `__pthread_fchdir` syscall). It is looked up at run time

### The forked child

Used by [fork-cwd](#fork-cwd), [fork-cwd-sockdir](#fork-cwd-sockdir) and [fork-cwd-direct](#fork-cwd-direct). The fd the child `fchdir`s into and the spelling are in each route's section.

1. The parent creates the socket, holds the fd and builds the sockaddr before forking. For a non-blocking connect it makes the socket non-blocking before the fork
2. The child does `fchdir(fd)` → `bind` / `connect` by the spelling → `_exit(result)` (0 is success, 1–255 an errno)
3. The parent `waitpid`s for that pid only, then cleans up R and D. The listen after a bind is always done by the parent ([DR-0010](decisions/DR-0010-fork-bind-listen-by-parent.md), Japanese)

- The child's section uses async-signal-safe calls only (no allocation, locks, or the language's cleanup)
- If `waitpid` fails with `ECHILD` (someone else reaped the status), read the result from the socket: for a bind whether `getsockname` holds a path, for a connect whether `getpeername` succeeds. A failure is a generic error

### Connect order

A connect of a path over the standard length tries the routes in the order below, per OS. Routes that need neither writing (creating D, R or a symlink) nor a thread come first; routes that create D or start a thread come after ([DR-0012](decisions/DR-0012-own-directory-and-thread-cwd.md), Japanese). When none can be used, the `connect_ex` variants with the last resort try [fork-cwd-direct](#fork-cwd-direct), and `connect` / `connect_nonblocking` and the `connect_ex` variants without the last resort return `ENAMETOOLONG` ("[Order tried](#order-tried)").

| OS | Order tried |
|---|---|
| Linux / Android (`/proc` usable) | [proc-direct](#proc-direct) → [thread-cwd](#thread-cwd) → [proc](#proc) → [proc-held](#proc-held) → [symlink-file](#symlink-file) |
| Linux / Android (`/proc` not usable) | [relative](#relative) → [thread-cwd](#thread-cwd) → [symlink-file](#symlink-file) |
| macOS / iOS and the other Apple OSes | [relative](#relative) → [widened](#widened) → [thread-cwd](#thread-cwd) → [symlink-file](#symlink-file) |
| FreeBSD | [at-direct](#at-direct) → [at](#at) |
| NetBSD / OpenBSD / illumos / other Unix | [relative](#relative) → [symlink-file](#symlink-file) |

- The routes that need neither writing nor a thread are fast, and [relative](#relative) and [widened](#widened) sometimes reach further than the routes through D
- relative gives a generic error when the cwd changes in between (it is checked after the connect, so it never reaches another place; [Building the relative path](#building-the-relative-path))
- The target of proc-held's `s` and of symlink-file's symlink is the socket file as spelled (a relative path gets the cwd prepended)

### Building the relative path

Used by [relative](#relative).

1. If the path starts with a spelling of the cwd (`getcwd`, or `$PWD` when its `stat` `(st_dev, st_ino)` matches that of `.`), strip it, comparing whole components
2. Only when 1 is not within the sockaddr length, resolve the socket's directory and the cwd with `realpath` and build a spelling that climbs with `..`
3. Use the shorter. Before using it, check that the relative directory and the original directory have the same `(st_dev, st_ino)`, and that the cwd's `(st_dev, st_ino)` is the same as before 1. Otherwise the route is not usable
4. If the cwd's `(st_dev, st_ino)` has changed after the connect, discard the result and return a generic error

### symlink base and name

Used by [symlink-file](#symlink-file) and [symlink-dir](#symlink-dir).

| Item | Specification |
|---|---|
| base candidates | symlink-file (bind and connect): `TMPDIR` (when a non-empty absolute path), then `/tmp`<br>symlink-dir (`bind_ex` with the last resort): `XDG_RUNTIME_DIR` (when a non-empty absolute path), `TMPDIR` (same), then `/tmp`<br>A candidate with the same spelling is tried once |
| base only the owner can write to | stat'ed following symlinks; a directory, owned by the effective uid, with `mode & 0o022 == 0` |
| shared base | stat'ed following symlinks; a directory, sticky bit set, owned by root or the effective uid |
| safe base | a base only the owner can write to, or a shared base. symlink-file uses either, candidates in order |
| how symlink-dir tries | among the candidates, the bases only the owner can write to in order; if none, the shared bases in order |
| symlink target | symlink-file: the socket file as spelled (a relative path gets the cwd prepended)<br>symlink-dir: the realpath of the socket's directory |
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
  - in symlink-file and symlink-dir, the base is unsafe or the symlink cannot be created
  - in a bind through symlink-file, the bind fails and nothing is at the original path or it cannot be checked (taken as the kernel not following the symlink)
  - in relative, the directory of the spelling built does not match the original by `(st_dev, st_ino)`, or the cwd has already changed
- A missing directory is `ENOENT` on every OS. The directory is looked up first, so this is settled before the length is judged
- `connect` / `connect_nonblocking` and the `connect_ex` variants without the last resort return `ENAMETOOLONG` instead of trying [fork-cwd-direct](#fork-cwd-direct)

## Where a path stops being reached

When a path over the standard length becomes `ENAMETOOLONG` (the directory exists, D can be created, and the language builds every route; numbers in bytes). How far a language that cannot build some routes reaches is in that language's README.

| OS | `bind` | `connect` variants | `connect_ex` variants with the last resort |
|---|---|---|---|
| Linux / Android (`/proc` present) | file name > 96 | always reached ([proc-held](#proc-held)) | always reached |
| Linux / Android (no `/proc`) | file name > 96 | [thread-cwd](#thread-cwd) is not usable (file name > 96 or no thread cwd), [relative](#relative) > 107, and no [symlink-file](#symlink-file) | file name > 107, and no symlink-file |
| FreeBSD | file name > 92 | file name > 103 | file name > 103 |
| macOS / iOS and the other Apple OSes | macOS: always reached ([symlink-file](#symlink-file)); when symlink-file is not usable, file name > 92<br>the other Apple OSes: file name > 92 | [thread-cwd](#thread-cwd) is not usable (file name > 92 or no thread cwd), both the original and the relative path > 253, and no symlink-file | file name > 253, and no symlink-file |
| NetBSD | always reached ([symlink-file](#symlink-file)); when symlink-file is not usable, file name > 92 | relative > 103, and no symlink-file | file name > 103, and no symlink-file |
| OpenBSD / other BSD | file name > 92 | relative > 103, and no symlink-file | file name > 103, and no symlink-file |
| illumos | file name > 96 | relative > 107, and no symlink-file | file name > 107, and no symlink-file |

- The bind column counts [symlink-file](#symlink-file) only on macOS and NetBSD, where the bind was measured to follow the symlink (2026-11-19). Linux, FreeBSD, OpenBSD and illumos do not follow. On other OSes it is not checked, and the column does not count symlink-file
- On Linux without thread-cwd, a bind uses [proc](#proc) for a file name up to about 79 bytes, and [fork-cwd](#fork-cwd) beyond that up to 96
- When D can be created nowhere, a bind reaches a file name of 88 (84 on Apple OSes / BSD, about 72 with [proc-sockdir](#proc-sockdir) alone) through the `-sockdir` routes (when R can be created in the socket's directory). The connect variants reach as far as the routes in "[Connect order](#connect-order)" that do not use D ([proc-direct](#proc-direct), [relative](#relative), [widened](#widened), [symlink-file](#symlink-file), [at-direct](#at-direct)) do ([proc-held](#proc-held) is not usable either)
- `bind_ex` with the last resort reaches even where the bind's routes give `ENAMETOOLONG`, as long as the [symlink-dir](#symlink-dir) spelling (`<base>/sockat.XXXXXXXXXX/<file name>`) fits the sockaddr
- Full paths are passed when looking up the directory and so on, so a path over PATH_MAX (1024 on macOS, 4096 on Linux) is `ENAMETOOLONG`. That is outside sockat's responsibility

## Side effects of the fork route

| Scope | Side effect |
|---|---|
| visible to the peer (only the `connect_ex` variants with the last resort) | the peer pid the server sees is that of the exited child. uid / gid are the caller's<br>Linux's `SO_PEERCRED` keeps the child's pid<br>macOS's `LOCAL_PEERPID` turns into the caller's pid once the caller sends |
| not visible to the peer (`bind` / `bind_ex` and the `connect_ex` variants with the last resort) | until it exits, the child holds copies of every fd. A socket or pipe another thread closes meanwhile stays open<br>the parent gets `SIGCHLD`<br>`pthread_atfork` handlers run<br>monitoring tools see a short-lived child<br>another thread's `waitpid(-1)` may reap the child |

- A bind has no side effect visible to the peer. The child only binds and the parent listens, so the server's peer information a client sees (macOS's `LOCAL_PEERPID` / `LOCAL_PEEREPID` / the audit token's pid and pidversion, Linux's `SO_PEERCRED` / `SO_PEERPIDFD`) is the parent's from before any send (measured 2026-11-18 on macOS 26.5.2 and Linux) ([DR-0010](decisions/DR-0010-fork-bind-listen-by-parent.md), Japanese)

## Patterns not to use

Ways of using sockat that remove an unrelated file or fail to remove the file. Each language's README / manual lists, under a heading of the same name, the concrete form in that language (e.g. Go's `os.Remove(l.Addr().String())`).

| Pattern | Why not | Instead |
|---|---|---|
| unlinking / `stat`ing the socket file by the spelling the kernel reports (`getsockname`, the listener's address, etc.) | for a long path it is not the original path ([respelled](#respelled)). Depending on the cwd or a shared base, it may hit another file someone recreated ([cwd-relative](#cwd-relative), [recreatable-spelling](#recreatable-spelling)) | keep the original path and use it. `bind_ex`'s `discard()` |
| binding with a relative path and removing by that relative path after the cwd changes | hits a file in another place ([cwd-relative](#cwd-relative)) | make the path absolute before the bind. `discard()` |
| relying on closing the listener to remove the socket file | for a long path it is not removed, even in a language whose standard removes it (Go etc.) ([respelled](#respelled)) | `discard()`, or remove by the original path |
| relying on `discard()` to close the listener too | `discard()` only removes the file ([DR-0015](decisions/DR-0015-ex-with-last-resort-and-diagnostics.md), Japanese) | close the listener yourself |
| branching on the strings of `_ex`'s `route` / `skipped` / `reason` | they are for diagnostics and promise nothing (routes are added and changed) | branch on `losses` |
| in a program that goes through a fork in `_ex`, another thread reaping children with `waitpid(-1)` | it may reap sockat's child and confuse the result ([forked](#forked)) | wait by pid. For connect, do not use the last resort (the fork-cwd of bind is a default route) |

## What differs from the standard for a long path

| Point | Detail |
|---|---|
| address the kernel reports | the bound side's `getsockname` and the connecting side's `getpeername` return `R/<file name>` (`/proc/self/fd/<fd>/R/<file name>` for [proc](#proc)). R no longer exists, so normally it hits nothing when resolved later (if the process's cwd is a place others can write to, other users can see and recreate the spelling; `respelled` in "[What is lost](#what-is-lost)"). A bind through [symlink-file](#symlink-file) returns the symlink's spelling `<base>/sockat.XXXXXXXXXX` (unlinking by it only removes the entry in the base). [symlink-dir](#symlink-dir) of `bind_ex` with the last resort returns `<base>/sockat.XXXXXXXXXX/<file name>`, which in a shared base other users can recreate. In a language where the address accessors of the standard types can be replaced (Python), they return the original path (Python's asyncio `stat`s / unlinks the listener's `getsockname` spelling). Where they cannot be replaced, the caller keeps the original path. On illumos the connecting side's `getpeername` returns the spelling passed to connect rather than the bound spelling (the symlink's spelling for a [symlink-file](#symlink-file) connect) (measured in sockat-rs CI, 2026-11-19) |
| directory looked up first | the routes that use R (those through D and the form without D) and [symlink-dir](#symlink-dir) resolve the socket's directory with realpath when they create the symlink. [proc-direct](#proc-direct), [relative](#relative), [at-direct](#at-direct) and [fork-cwd-direct](#fork-cwd-direct) look up the directory, then pass the file name. A rename or symlink swap in between is not reflected. [widened](#widened), [symlink-file](#symlink-file) and [proc-held](#proc-held) behave as the standard (the target of the symlink of symlink-file and proc-held is the socket file as spelled) |
| how operations tools show it | the address shown by `ss -x`, `lsof`, `/proc/net/unix` etc. is the kernel's spelling (`R/<file name>` etc.), so the socket is hard to tell apart by its original path. The file name stays at the end of the spelling (the spelling of a bind through [symlink-file](#symlink-file) has no file name) |
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
| no route can be used (the spelling does not fit, or no means exists); for a connect without the last resort also when only fork-cwd-direct would reach it | `ENAMETOOLONG` |
| path over the standard length that does not end with a name | invalid argument |
| path containing NUL anywhere but at the start (at any length) | invalid argument |
| the cwd changed during relative | generic error |
| the forked child did not exit normally, or its status was reaped elsewhere and the socket was not bound / connected | generic error |

- OS errors are returned so that the errno can be read in the language's usual way
- Each implementation chooses the types for "invalid argument" and "generic error"

## What each implementation must do

- Follow the routes and order above. Skip a route the language cannot build (treat it as not usable, go on, and put it into `_ex`'s `skipped` with the reason), and show it in the README as an OS × route table
- Provide the test CLI of the language-independent conformance test ([docs/design/conformance.md](design/conformance.md), Japanese)
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
| where D is created | when D cannot be created in `TMPDIR`, `/tmp` is used, and failing that the socket's directory with a `.sockat.` name. A relative or deep `TMPDIR` works. When it can be created nowhere, a bind takes the form without D (thread-cwd-sockdir → proc-sockdir → fork-cwd-sockdir) and the connect variants the next route in "[Connect order](#connect-order)" |
| ways not usable | with thread-cwd made unusable, Linux with `/proc` goes on to proc. When the proc spelling does not fit (a file name over about 79), a bind goes on to fork-cwd (the peer is the parent) and the connect variants to the next route in "[Connect order](#connect-order)" ([proc-held](#proc-held)) |
| connect routes | with each of [proc-direct](#proc-direct), [proc-held](#proc-held), [relative](#relative), [widened](#widened), [symlink-file](#symlink-file) and [at-direct](#at-direct) forced in turn, the socket is reached and nothing remains in the base. For symlink-file, an unsafe base is skipped, a too deep `TMPDIR` falls back to `/tmp`, colliding names are skipped and the attempts stop at 16 |
| bind through symlink-file | on an OS whose bind follows the symlink it gets through and `losses` is `respelled` only. It is not tried on the OSes measured not to follow (Linux / Android, FreeBSD, OpenBSD, illumos). On an OS that does not follow it (when an OS not yet checked did not follow), it goes into `skipped` and nothing remains. When something is at the original path, that error (`EADDRINUSE`) is returned and nothing further is tried |
| no retry on failure | `ENOENT` / `EADDRINUSE` / `ECONNREFUSED` are returned and nothing is created on later routes or bases |
| connect and fork | the `connect` variants and the `connect_ex` variants without the last resort return `ENAMETOOLONG` when only fork-cwd-direct reaches; the `connect_ex` variants with the last resort reach and `losses` is `forked` only |
| `bind_ex` with the last resort | where the default bind gives `ENAMETOOLONG` it reaches through symlink-dir. With a base only the owner can write to, that base is used and `losses` is `respelled` only; with only a shared base, `losses` is `respelled` and `recreatable-spelling`. Nothing remains in the base. Where a default route reaches, `losses` is that route's |
| D that cannot be opened | when the umask removed the owner's permission and D just created cannot be opened, nothing remains in the base |
| relative and cwd | a cwd change during relative is a generic error |
| fork | a client connected to a server bound through fork-cwd or fork-cwd-sockdir sees the parent as the peer (before and after any send); the peer pid behavior of fork-cwd-direct; reading the result with `SIGCHLD` set to `SIG_IGN` |
| macOS | a 253-byte path goes through widened for the connect variants. A bind never uses widened |
| non-blocking connect | a full backlog fails without waiting |
| path not ending with a name, NUL anywhere but at the start | invalid argument, nothing created. NUL even for a short path. A leading NUL (abstract) goes to the standard |
| address the kernel reports | reading it does not fail for a long path. Where the accessors can be replaced, the listener, accepted and connected sockets return the original path, and the language's usual higher layers (Python's asyncio `start_unix_server(sock=...)` etc.) behave as for a short path without extra arguments |
| `bind_ex`'s `discard()` | `discard()` removes the file and does not close the listener. If another file has replaced it while the listener is open, it is not removed |

- The routes differ per OS, so run at least on macOS and Linux. Other Unixes run in CI VMs
- Tests that change process-wide settings such as the cwd or signal handling run inside a child process
- The fork route's child briefly holds copies of every fd, so create "a socket nobody listens on" in a separate process

## Open questions

- Android and the Apple OSes other than macOS are not checked at all
- NetBSD / OpenBSD / illumos: the peer credentials are not checked
- That a non-blocking connect never answers `EINPROGRESS` is checked only on Linux and macOS
