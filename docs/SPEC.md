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
| D | a directory of sockat's own, created for each bind / connect ("The central route") |
| R | a symlink with a random name, pointing to the socket's directory. Created inside D (inside the socket's directory for the form without D) |

## Scope

- bind (and listen) / connect of pathname Unix domain sockets
- Unix-like OSes. Windows is not supported

## Operations

| Operation | Rust | Python | Go | Fork | Blocks | Returns |
|---|---|---|---|---|---|---|
| bind | `bind` | `bind` | `Listen` | tried | (does not wait) | a listening standard listener |
| bind with cleanup | `bind_ex` | `bind_ex` | `ListenEx` | tried | (does not wait) | a standard listener and `discard()` |
| connect | `connect` | `connect` | `Dial` | never tried | yes | a standard stream |
| non-blocking connect | `connect_nonblocking` | `connect_nonblocking` | none | never tried | no | a non-blocking standard stream |
| connect that reaches even by forking | `connect_any` | none | none | tried | yes | `AnyConnection { stream, forked }` |
| the same, non-blocking | `connect_any_nonblocking` | none | none | tried | no | as above (the stream is non-blocking) |

- The names are provisional. Other languages follow their own naming conventions. The behavior follows the table above
- The listener / stream returned is of the same type the standard returns, so it is a drop-in replacement for the standard
- `_ex` exists for bind only. It remembers the realpath and `(st_dev, st_ino)` of the bound socket file; `discard()` closes the listener and removes the file only when that path still has the same `(st_dev, st_ino)`
  - It remembers them right after the bind succeeds (inside the route, before returning the listener). If they cannot be remembered, it closes the listener, leaves the file, and returns an error (it does not hand back a `discard()` that cannot remove anything as a success)
  - The path argument is turned into a string once at the entry, and that value is used for remembering, binding and returning alike (so that a path type that can return a different value on each call never makes the remembered file differ from the bound one)
  - `discard()` succeeds when the file is already gone and when it has been replaced by another file and is left alone. It fails when the check cannot be made (`lstat` fails with something other than `ENOENT` / `ENOTDIR`) and when the removal itself fails (it does not report success when it cannot tell whether anything was removed)
  - Someone who can write to the socket's directory swapping the file between the check and the removal, or between the bind and the remembering, cannot be prevented (POSIX has no way to remove by inode)
- The `connect_any` variants connect even by forking when no other route can be used. No pid is returned. `forked` is true only when the fork route was taken
- The `connect_any` variants are not in the default API; they sit behind a mechanism the user opts into (an `any` feature in Rust) ([DR-0007](decisions/DR-0007-connect-any-is-opt-in.md), Japanese). A language that cannot build the fork route does not provide them; its README says "no fork route" in the table ([DR-0002](decisions/DR-0002-no-connect-any-without-fork.md), Japanese)
- A language whose standard connect never blocks (Node.js etc.) provides one connect in the standard's own form ([DR-0003](decisions/DR-0003-single-connect-when-standard-never-blocks.md), Japanese)
- `connect` / `connect_nonblocking` return `ENAMETOOLONG` when they reach the fork route
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
- The socket's directory is looked up first with `stat`, and its realpath is taken. When it is missing, `ENOENT`; when it is not a directory, `ENOTDIR`; when the realpath cannot be taken, that error (all before the length is judged or D is created). Only the routes that need an fd of the socket's directory (/proc, connectat, fork, the form without D) open it, and when it cannot be opened that route is unusable (`O_RDONLY` on other OSes cannot open a directory without read permission)
- No route changes the calling process's cwd or the calling thread's cwd
- How a directory is opened (the base, the socket's directory): `O_SEARCH` on Apple OSes (`O_RDONLY` if the kernel answers `EISDIR` / `EINVAL`), `O_PATH | O_DIRECTORY` on Linux, `O_RDONLY | O_DIRECTORY` elsewhere

### Order tried

| Step | bind | `connect` / `connect_nonblocking` | `connect_any` variants |
|---|---|---|---|
| 1 | up to the standard length, the standard unchanged ("Short paths") | same | same |
| 2 | the central route (thread cwd; bindat on FreeBSD) | the central route (thread cwd; connectat on FreeBSD) | as left |
| 3 | the central route's /proc form (Linux / Android with `/proc` usable) | as left | as left |
| 4 | the central route by fork | the fallback routes | the fallback routes |
| 5 | `ENAMETOOLONG` | `ENAMETOOLONG` | the fork route |

- A bind's step 4 is tried when steps 2 and 3 cannot use the thread cwd / `/proc`, or the `/proc` spelling does not fit. When D can be created nowhere, steps 2 to 4 are tried in the form without D ("Where D is created"). When the spelling does not fit the sockaddr, it is not tried and the result is `ENAMETOOLONG`
- A bind never uses /proc (the form not going through D), relative path, widened sockaddr, or the symlink in a base (the spelling would hit an unrelated file later, the address would be cut short and break whoever reads it, or the central route suffices)
- A connect's spelling is left nowhere on the peer (the connecting socket is not bound), so the fallback routes put no random part in it

### The central route

1. Open the base ("Where D is created") and hold its fd; inside it, `mkdirat` D with mode 0700. The name is `sockat.` (`.sockat.` in the socket's directory) + 10 characters from 62 alphanumerics (the OS's secure random source). Draw a new name on `EEXIST`; give up after 16
2. Open D (`O_PATH | O_DIRECTORY | O_NOFOLLOW` on Linux, `O_SEARCH | O_DIRECTORY | O_NOFOLLOW` on Apple OSes (`O_RDONLY` if the kernel answers `EISDIR` / `EINVAL`), `O_RDONLY | O_DIRECTORY | O_NOFOLLOW` on other OSes. `O_PATH` and `O_SEARCH` open even when the umask removed the owner's read permission). `fstat` that it is a directory, owned by the effective uid, with no permission for group or other, then settle it to 0700
   - An `O_PATH` fd: `chmod("/proc/self/fd/<fd>", 0700)` if `/proc` is usable. Otherwise reopen D by name with `O_RDONLY | O_DIRECTORY | O_NOFOLLOW`, confirm its `(st_dev, st_ino)` equals the first fd's, and `fchmod` (`fchmod` on an `O_PATH` fd fails with `EBADF`)
   - Any other fd: `fchmod`
   - If, after the check passed, D cannot be reopened or settled, it counts as "cannot create" and step 5 cleans D up
3. Create R inside D: `symlinkat(<realpath of the socket's directory>, Dfd, R)`. R's name is 10 characters from 62 alphanumerics (no `sockat.`). Draw a new name on `EEXIST`; give up after 16
4. Bind / connect by `R/<file name>` relative to D's fd ("Ways to work relative to D's fd")
5. Cleanup: remove R with `unlinkat(Dfd, R)` only if this call created it. Remove D with `unlinkat(base fd, D's name, AT_REMOVEDIR)` only when the check in step 2 passed and `fstatat(base fd, D's name, AT_SYMLINK_NOFOLLOW)` gives the same `(st_dev, st_ino)` as the fd. Close the fds. This happens on success and on failure. A failure to remove is ignored

- The spelling `R/<file name>` is 11 bytes + the file name. A file name may be up to the sockaddr length − 11 (96 on Linux / illumos, 92 on Apple OSes / BSD)
- After cleanup R exists nowhere, so the spelling the kernel reports, resolved later in another context such as the process's cwd, hits no unrelated file
- A D that failed the check is someone else's; it and its contents are left alone
- The length, and whether a way can be used (as far as can be told), are checked before D is created. If not usable, nothing is created and the next is tried
- The length of the /proc variant's spelling depends on D's fd number, which is unknown until D is opened. Before creating D it is estimated, and it is checked again once D is open (if it does not fit, D is cleaned up and the next is tried)
- Checking whether `/proc` is usable does not need an fd of the socket's directory (use the fd of `/` or of D)

### Where D is created

| Order | Base | Condition |
|---|---|---|
| 1 | `${TMPDIR:-/tmp}` | a relative path is fine too (opened once and held by fd) |
| 2 | `/tmp` | only when 1 fails. Skipped when spelled the same as 1 |
| 3 | the socket's directory | only when 2 fails too. The name is `.sockat.XXXXXXXXXX` (it is the user's directory, so a leftover is recognizable as sockat's and stays inconspicuous). A bind should be able to write there; a connect not necessarily |

- "Fails" means: the base cannot be opened, D cannot be created, names are exhausted, no random bytes, the check in step 2 fails, or R cannot be created
- When D can be created nowhere, a bind goes on to the form without D. It creates an R in the socket's directory (named `.sockat.XXXXXXXXXX`, pointing to the socket's directory's realpath) and, resolving against the socket's directory fd instead of D's, binds by `.sockat.XXXXXXXXXX/<file name>`. The means are tried in the same order as with D (thread cwd (bindat on FreeBSD) → the /proc variant `/proc/self/fd/<fd>/.sockat.XXXXXXXXXX/<file name>` → fork). The spelling is 19 bytes + the file name (a file name up to 88 on Linux / illumos, 84 on Apple OSes / BSD; about 72 for the /proc variant). If the socket's directory cannot be opened or R cannot be created either, `ENAMETOOLONG`
- When D can be created nowhere, the connect variants go on to the fallback routes
- Neither the base's safety (sticky etc.) nor its length matters. D is held by fd, and the base does not appear in the spelling

### Ways to work relative to D's fd

| Way | OS | How | Not usable when |
|---|---|---|---|
| thread cwd | Linux / Android | on a throwaway thread, `unshare(CLONE_FS)` → `fchdir(Dfd)` → bind / connect by `R/<file name>` | a seccomp filter is in place or this cannot be told (`prctl(PR_GET_SECCOMP)` returns non-zero or fails), `unshare` is refused, a thread cannot be created or pinned |
| thread cwd | Apple OSes | on a throwaway thread, `pthread_fchdir_np(Dfd)` → as above | `pthread_fchdir_np` is absent or fails, a thread cannot be created or pinned |
| bindat / connectat | FreeBSD | without a thread, pass `R/<file name>` to `bindat(Dfd, ...)` / `connectat(Dfd, ...)` | |
| /proc form | Linux / Android with `/proc` usable | without a thread, bind / connect by `/proc/self/fd/<Dfd>/R/<file name>` | `/proc/self/fd/<Dfd>` cannot be resolved, the spelling does not fit the sockaddr (a file name up to about 79 bytes; it varies with the fd's digits) |
| (none) | NetBSD / OpenBSD / illumos | no means (a bind goes on to fork) | |

- The caller waits until the throwaway thread finishes before cleaning up R and D and closing the fd. Even if the wait is interrupted (Python's `KeyboardInterrupt` and the like), nothing is cleaned up until the thread finishes (if an fd closed early has its number reused, the thread moves into an unrelated directory and binds there)
- The thread is a throwaway one sockat creates, discarded after use. The caller's thread's cwd is never touched (restoring with `pthread_fchdir_np(-1)` could drop a per-thread cwd the caller set)
- On Linux, `unshare` is not called while a seccomp filter is in place. Some filters refuse it by killing the process (SIGSYS) (systemd's `SystemCallFilter=` by default)
- A failing `fchdir` after `unshare` (`EACCES` etc.) is a real failure and is returned
- The caller creates the socket and holds D's fd. For a non-blocking connect it makes the socket non-blocking first. The listen after a bind is done by the caller
- `pthread_fchdir_np` is a private libSystem API (the `__pthread_fchdir` syscall). It is looked up at run time
- The thread cwd and the /proc form have no side effects (the peer pid stays the caller's, no fd is copied, and other threads' cwd is unchanged). So `connect` / `connect_nonblocking` try them too
- The /proc form's spelling goes through R as well, so a reused fd number later hits no unrelated file

### The fork route

1. The parent creates the socket, holds the fd and builds the sockaddr before forking. For a non-blocking connect it makes the socket non-blocking before the fork
2. The child does `fchdir(fd)` → `bind` / `connect` by the spelling → `_exit(result)` (0 is success, 1–255 an errno)

| Operation | fd the child `fchdir`s into | Spelling |
|---|---|---|
| bind | D | `R/<file name>` |
| bind (D can be created nowhere) | the socket's directory | `.sockat.XXXXXXXXXX/<file name>` (R inside the socket's directory) |
| `connect_any` variants | the socket's directory | the file name |

3. The parent `waitpid`s for that pid only, then cleans up R and D. The listen after a bind is always done by the parent ([DR-0010](decisions/DR-0010-fork-bind-listen-by-parent.md), Japanese)

- The child's section uses async-signal-safe calls only (no allocation, locks, or the language's cleanup)
- If `waitpid` fails with `ECHILD` (someone else reaped the status), read the result from the socket: for a bind whether `getsockname` holds a path, for a connect whether `getpeername` succeeds. A failure is a generic error
- The `connect_any` variants on Apple OSes use the widened sockaddr when the kernel takes it

### Fallback routes (connect variants)

Tried when the central route cannot be used (no means, D cannot be created, the spelling does not fit).

| OS | Order tried |
|---|---|
| Linux / Android (`/proc` usable) | /proc → fd-held form → symlink |
| Linux / Android (`/proc` not usable) | relative path → symlink |
| macOS / iOS and the other Apple OSes | relative path → widened sockaddr → symlink |
| FreeBSD | connectat |
| NetBSD / OpenBSD / illumos / other Unix | relative path → symlink |

| Route | How | Usable when |
|---|---|---|
| /proc | open the socket's directory and hand `/proc/self/fd/<fd>/<file name>` | `/proc/self/fd/<fd>` can be stat'ed and the spelling is within the sockaddr length (a file name up to about 90 bytes; it varies with the fd's digits) |
| fd-held form | create D (steps 1, 2 and 5 of the central route), create the symlink `s` in it with `symlinkat`, pointing to the socket file, and hand `/proc/self/fd/<Dfd>/s`. `s` is removed only if this call created it | Linux / Android with `/proc` usable. D and `s` can be created |
| relative path | hand the path relative to the cwd. Only the string is rewritten; no `chdir` | the original path is absolute and the relative path is within the sockaddr length ("Building the relative path") |
| widened sockaddr | pass the original path, failing that the relative path, in a sockaddr whose `sun_len` and address length are `2 + path length` | Apple OSes. The path is at most 253 bytes. `EINVAL` / `ENAMETOOLONG` from the kernel means not usable |
| symlink | create a symlink to the socket file in a safe base, hand `<base>/sockat.XXXXXXXXXX`, remove it at once | the spelling is within the sockaddr length and there is a safe base where the symlink can be created ("symlink base and name") |
| connectat | open the socket's directory and `connectat(fd, <file name>)` | FreeBSD. The file name is at most 103 bytes |

- The target of the fd-held form's and the symlink route's symlink is the socket file as spelled (a relative path gets the cwd prepended)

### Building the relative path

1. If the path starts with a spelling of the cwd (`getcwd`, or `$PWD` when its `stat` `(st_dev, st_ino)` matches that of `.`), strip it, comparing whole components
2. Only when 1 is not within the sockaddr length, resolve the socket's directory and the cwd with `realpath` and build a spelling that climbs with `..`
3. Use the shorter. Before using it, check that the relative directory and the original directory have the same `(st_dev, st_ino)`, and that the cwd's `(st_dev, st_ino)` is the same as before 1. Otherwise the route is not usable
4. If the cwd's `(st_dev, st_ino)` has changed after the connect, discard the result and return a generic error

### symlink base and name

| Item | Specification |
|---|---|
| base candidates | `TMPDIR` (when a non-empty absolute path), then `/tmp`. Tried once when `TMPDIR` is spelled the same as `/tmp` |
| safe base | stat'ed following symlinks; a directory, and one of<br>sticky bit set, owned by root or the effective uid<br>owned by the effective uid, with `mode & 0o022 == 0` |
| name | `sockat.` + 10 characters from 62 alphanumerics, taken from the OS's secure random source |
| collision | on `EEXIST` draw a new name. Give up after 16 attempts and treat the candidate as not usable |
| cleanup | removed whether the connect succeeds or fails. A failure to remove is ignored |

- For each candidate, check the spelling's length and the base's safety before creating anything. A candidate that does not fit, is unsafe, or where nothing can be created gets nothing and the next is tried

## How a failing route is treated

- When a route actually binds / connects and fails (`ENOENT`, `EADDRINUSE`, `ECONNREFUSED`, etc.), that error is returned and no later route or base is tried
- The next one is tried only when the route itself cannot be used
  - the spelling does not fit
  - D or R cannot be created in a base for D (the next base is tried)
  - a way to work relative to D's fd cannot be used (its "Not usable when" in "Ways to work relative to D's fd")
  - `/proc` not usable
  - in the fd-held form, D or `s` cannot be created
  - the kernel refuses the widened sockaddr
  - the base is unsafe or the symlink cannot be created
  - on the relative route, the directory of the spelling built does not match the original by `(st_dev, st_ino)`, or the cwd has already changed
- A missing directory is `ENOENT` on every OS. The directory is looked up first, so this is settled before the length is judged
- `connect` / `connect_nonblocking` return `ENAMETOOLONG` just before the fork route

## Where a path stops being reached

When a path over the standard length becomes `ENAMETOOLONG` (the directory exists and D can be created; numbers in bytes).

| OS | `bind` | `connect` variants | `connect_any` variants |
|---|---|---|---|
| Linux / Android (`/proc` present) | file name > 96 | always reached (fd-held form) | always reached |
| Linux / Android (no `/proc`) | file name > 96 | the central route is not usable (file name > 96 or no thread cwd), relative path > 107, and no symlink | file name > 107, and no symlink |
| FreeBSD | file name > 92 | file name > 103 | file name > 103 |
| macOS / iOS and the other Apple OSes | file name > 92 | the central route is not usable (file name > 92 or no thread cwd), both the original and the relative path > 253, and no symlink | file name > 253, and no symlink |
| NetBSD / OpenBSD / other BSD | file name > 92 | relative path > 103, and no symlink | file name > 103, and no symlink |
| illumos | file name > 96 | relative path > 107, and no symlink | file name > 107, and no symlink |

- On Linux without the thread cwd, a bind uses the /proc form for a file name up to about 79 bytes, and fork beyond that up to 96
- When D can be created nowhere, a bind reaches a file name of 88 (84 on Apple OSes / BSD, about 72 with the /proc variant alone) through the form without D (when R can be created in the socket's directory). The connect variants reach as far as the fallback routes do (the fd-held form is not usable)
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
| address the kernel reports | the bound side's `getsockname` and the connecting side's `getpeername` return `R/<file name>` (`/proc/self/fd/<fd>/R/<file name>` for the /proc form). R no longer exists, so it hits nothing wherever it is resolved later. In a language where the address accessors of the standard types can be replaced (Python), they return the original path (Python's asyncio `stat`s / unlinks the listener's `getsockname` spelling). Where they cannot be replaced, the caller keeps the original path |
| directory looked up first | the central route resolves the socket's directory with realpath when it creates R. The fallback routes' /proc, relative path and connectat, and the fork of the `connect_any` variants, look up the directory, then pass the file name. A rename or symlink swap in between is not reflected. The widened sockaddr and the symlink route behave as the standard |
| another thread's chdir | the relative route returns a generic error if the cwd stayed changed in between. A change and change back is not seen |
| leftovers | if the process dies before removing D, R or a base's symlink, `sockat.XXXXXXXXXX` is left in the base, and `.sockat.XXXXXXXXXX` (D, or the R of the form without D) in the socket's directory. On OSes that open D with `O_RDONLY` (other than Linux and Apple OSes), D cannot be opened when the umask removed the owner's read permission; it cannot be checked, so it is left untouched |

- NUL anywhere but at the start is an invalid argument even in a short path. A language whose standard silently truncates at NUL (Go etc.) says so under "differs from the standard" in its README

## Errors

| Situation | Error |
|---|---|
| no directory / nothing to connect to | `ENOENT` |
| something other than a directory where the directory should be | `ENOTDIR` |
| a file already exists where bind would create the socket | `EADDRINUSE` |
| a socket file nobody listens on | `ECONNREFUSED` |
| backlog full | Linux: `EAGAIN` for a non-blocking connect (a blocking one waits); macOS: `ECONNREFUSED` |
| fits no route; for the `connect` variants also when only the fork route would reach it | `ENAMETOOLONG` |
| path over the standard length that does not end with a name | invalid argument |
| path containing NUL anywhere but at the start (at any length) | invalid argument |
| the cwd changed during the relative route | generic error |
| the forked child did not exit normally, or its status was reaped elsewhere and the socket was not bound / connected | generic error |

- OS errors are returned so that the errno can be read in the language's usual way
- Each implementation chooses the types for "invalid argument" and "generic error"

## What each implementation must do

- Follow the routes and order above. Skip a route the language cannot build (treat it as not usable and go on), and show it in the README as an OS × route table
- In a language that brings a socket it created into the standard type, check that a socket connected with a widened sockaddr does not break that step or the address lookups. If it breaks, treat the route as one the language cannot build and skip it
- Keep the routes out of the public API. Tests force each route by calling it directly from inside the package
- Make the parts that read the environment (where D is created, the symlink base candidates, the location of `/proc/self/fd`, whether an Apple OS takes the widened sockaddr, whether the thread cwd can be used) replaceable from tests
- Link this specification from the README and manual. Before introducing behavior that differs from it, change this specification first

## What implementations test

| Aspect | What to check |
|---|---|
| short path boundary | exactly the standard length goes to the standard unchanged; one byte more goes to the routes (check the boundary with the standard itself) |
| central route | with it forced, neither the process's cwd nor the calling thread's cwd changes, the socket is created at the original path and data flows, the peer pid is the caller's, and nothing remains in the base after cleanup |
| returned spelling | after a bind, unlinking / stat'ing the returned spelling (`getsockname`) as is hits no unrelated file (a same-named file in the cwd, a same-named file in another directory that got the reused fd number) |
| swapped directory | a directory swapped between creating and opening D (another owner, or permission for group / other) is neither used nor emptied |
| where D is created | when D cannot be created in `TMPDIR`, `/tmp` is used, and failing that the socket's directory with a `.sockat.` name. A relative or deep `TMPDIR` works. When it can be created nowhere, a bind takes the form without D (thread cwd → the /proc variant → fork) and the connect variants the fallback routes |
| ways not usable | with the thread cwd made unusable, Linux with `/proc` goes on to the /proc form. When that is not usable either, a bind goes on to fork (the peer is the parent) and the connect variants to the fallback routes |
| fallback routes | with each forced, the socket is reached and nothing remains in the base. For symlink, an unsafe base is skipped, a too deep `TMPDIR` falls back to `/tmp`, colliding names are skipped and the attempts stop at 16 |
| no retry on failure | `ENOENT` / `EADDRINUSE` / `ECONNREFUSED` are returned and nothing is created on later routes or bases |
| connect and fork | the `connect` variants return `ENAMETOOLONG` when only the fork route reaches; the `connect_any` variants reach with `forked` true |
| relative path and cwd | a cwd change during the relative route is a generic error |
| fork | a client connected to a server bound through the fork route sees the parent as the peer (before and after any send); the peer pid behavior of the `connect_any` variants; reading the result with `SIGCHLD` set to `SIG_IGN` |
| macOS | a 253-byte path goes through the widened sockaddr for the connect variants. A bind never uses the widened sockaddr |
| non-blocking connect | a full backlog fails without waiting |
| path not ending with a name, NUL anywhere but at the start | invalid argument, nothing created. NUL even for a short path. A leading NUL (abstract) goes to the standard |
| address the kernel reports | reading it does not fail for a long path. Where the accessors can be replaced, the listener, accepted and connected sockets return the original path, and the language's usual higher layers (Python's asyncio `start_unix_server(sock=...)` etc.) behave as for a short path without extra arguments |
| `_ex` | `discard()` closes and the file is removed. If another file has replaced it in between, it is not removed |

- The routes differ per OS, so run at least on macOS and Linux. Other Unixes run in CI VMs
- Tests that change process-wide settings such as the cwd or signal handling run inside a child process
- The fork route's child briefly holds copies of every fd, so create "a socket nobody listens on" in a separate process

## Open questions

- Android and the Apple OSes other than macOS are not checked at all
- NetBSD / OpenBSD / illumos: the peer credentials are not checked
- That a non-blocking connect never answers `EINPROGRESS` is checked only on Linux and macOS
