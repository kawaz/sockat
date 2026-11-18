# sockat specification

> English | [日本語](./SPEC-ja.md)

How sockat behaves, independent of the language. Every implementation follows it. The design decisions and the rejected alternatives are in [sockat-rs's DR-0001](https://github.com/kawaz/sockat-rs/blob/main/docs/decisions/DR-0001-long-socket-path-routes.md) (Japanese); what is specific to Rust (types, where `unsafe` lives, tokio) is in [sockat-rs's MANUAL](https://github.com/kawaz/sockat-rs/blob/main/docs/MANUAL.md).

## Terms

| Term | Meaning |
|---|---|
| standard | the language's standard library bind / connect for Unix domain sockets |
| standard length | the longest path the language's standard accepts. A path up to it is handed to the standard unchanged. Usually `sun_path` − 1, `sun_path` − 2 for Java ([DR-0004](decisions/DR-0004-standard-length-per-language.md), Japanese) |
| sockaddr length | the length of `sun_path` − 1 byte (leaving room for the NUL). The longest spelling a sockaddr that is not widened carries. The condition on the spellings of the /proc, relative path, symlink, thread cwd and fork routes |
| directory / file name | what precedes the last component of the path, and the last component |
| spelling | the path string handed to the kernel. A route is a way to build another spelling of the same place |

## Scope

- bind (and listen) / connect of pathname Unix domain sockets
- Unix-like OSes. Windows is not supported

## Operations

| Operation | Fork route | Blocks | Returns |
|---|---|---|---|
| `bind` | tried last | (does not wait) | a listening listener |
| `connect` | never tried | yes | a stream |
| `connect_nonblocking` | never tried | no | a non-blocking stream |
| `connect_any` | tried last | yes | a stream, and whether the fork route was taken (bool) |
| `connect_any_nonblocking` | tried last | no | a stream, and whether the fork route was taken (bool) |

- The listener / stream returned is of the same type the standard bind / connect returns, so it is a drop-in replacement for the standard
- Names may follow the language's naming conventions. The behavior follows the table above
- A language that cannot build the fork route does not provide the `connect_any` variants; its README says "no fork route" in the table ([DR-0002](decisions/DR-0002-no-connect-any-without-fork.md), Japanese)
- A language whose standard connect never blocks (Node.js etc.) provides one connect in the standard's own form, with no separate `_nonblocking` ([DR-0003](decisions/DR-0003-single-connect-when-standard-never-blocks.md), Japanese)
- `connect` / `connect_nonblocking` return `ENAMETOOLONG` when they reach the fork route
- The `connect_any` variants connect even by forking when no other route can be used. The bool is `true` only when the fork route was taken. No pid is returned
- The `connect_any` variants are not in the default API. They sit behind a mechanism the user opts into in that language (a `connect-any` feature in Rust, a separate module in Python, etc.) ([DR-0007](decisions/DR-0007-connect-any-is-opt-in.md), Japanese)
- The two non-blocking variants make the socket non-blocking before connecting and return it that way. When the peer's backlog is full they fail without waiting
- A non-blocking connect is expected to finish within the call. On `EINPROGRESS` that error is returned and the socket is closed (a stream that is not connected is never returned)
- A socket the implementation creates itself gets the same settings as one the language's standard creates (close-on-exec, `SO_NOSIGPIPE`, the listen backlog, etc.)
- When the listener is closed, the socket file is treated as the standard treats it for a short path (Go's standard removes it). For a long path it is not removed, even where the standard removes it (the spelling the kernel holds is not the original path, and removing by that spelling may remove another file). A language whose standard removes it says so under "differs from the standard" in its README

## Short paths

A path up to the standard length is handed to the standard unchanged. Nothing is added and no environment variable is read. A longer path goes to the routes ([DR-0004](decisions/DR-0004-standard-length-per-language.md), Japanese).

- A path containing NUL anywhere but at the start is never handed to the standard, whatever its length; it is an invalid-argument error ([DR-0006](decisions/DR-0006-nul-is-invalid-at-any-length.md), Japanese)
- On Linux / Android a path starting with NUL (abstract namespace, not a file) is out of sockat's scope and is handed to the standard unchanged, whatever its length. A language's own abstract notation (Go's `@` etc.) likewise
- On OSes without an abstract namespace (other than Linux / Android), a path starting with NUL is an invalid argument too, whatever its length
- In a language whose standard has no non-blocking connect, a non-blocking connect alone uses the implementation's own socket, connected to the same address as the standard would
- When the standard does not accept a route's spelling (a language whose standard length is shorter than the sockaddr length), the implementation's own socket is used with the same address too

| OS | sockaddr length |
|---|---|
| Linux / Android / illumos | 107 bytes |
| macOS / iOS and the other Apple OSes / FreeBSD / NetBSD / OpenBSD | 103 bytes |

## Routes for long paths and their order

A path over the standard length is tried on the routes below, in this order per OS, and bound / connected on the first route that can be used.

| OS | Order tried |
|---|---|
| Linux / Android (`/proc` usable) | /proc → relative path → symlink → thread cwd → fork |
| Linux / Android (`/proc` not usable) | relative path → symlink → thread cwd → fork |
| FreeBSD | bindat |
| macOS / iOS and the other Apple OSes | relative path → widened sockaddr → symlink → thread cwd → fork |
| NetBSD / OpenBSD / illumos / other Unix | relative path → symlink → fork |

- A path over the standard length whose last component is not a file name (`dir/`, `dir/.`, `dir/..`, `..`) is an invalid-argument error, and nothing is created
- No route changes the calling process's cwd
- The symlink route goes through the base candidates one by one: a symlink directly in the base when it is safe, the fd-held form when it is not (Linux / Android with `/proc` usable only). `TMPDIR` is used up before `/tmp`

### The routes

| Route | How | Usable when |
|---|---|---|
| /proc | open the directory `O_PATH \| O_DIRECTORY` and hand `/proc/self/fd/<fd>/<file name>` to the standard | `/proc/self/fd/<fd>` can be stat'ed and the whole spelling is within the sockaddr length (a file name up to about 90 bytes) |
| bindat | open the directory `O_RDONLY` and pass the file name to `bindat(2)` / `connectat(2)` | FreeBSD. A file name over 103 bytes is `ENAMETOOLONG` |
| relative path | hand the path relative to the cwd to the standard. Only the string is rewritten; no `chdir` | the original path is absolute and the relative path is within the sockaddr length. The relative directory and the original directory have the same `(st_dev, st_ino)`, and the cwd did not change while the spelling was built |
| widened sockaddr | pass the original path, failing that the relative path, in a sockaddr whose `sun_len` and address length are `2 + path length` | Apple OSes. The path is at most 253 bytes. `EINVAL` / `ENAMETOOLONG` from the kernel means the route is not usable |
| symlink | create a short symlink in a base directory, hand the spelling through it, remove it at once | the spelling is within the sockaddr length (*) and there is a base where the symlink can be created. An unsafe base only through the fd-held form, on Linux / Android with `/proc` usable |
| thread cwd | move the cwd of the binding / connecting thread alone into the directory and bind / connect by the file name | Linux / Apple OSes. The file name is within the sockaddr length (*). The language can create a thread and pin to it |
| fork | fork a child that `fchdir`s into the directory fd and binds / connects by the file name | only `bind` and the `connect_any` variants. The file name is within the sockaddr length (*) |

(*) 253 bytes on an Apple OS while the kernel takes the widened sockaddr. Once it refuses, the sockaddr length applies.

### Building the relative path

1. If the path starts with a spelling of the cwd (`getcwd`, or `$PWD` when its `stat` `(st_dev, st_ino)` matches that of `.`), strip it, comparing whole components
2. Only when 1 is not within the sockaddr length, resolve the socket's directory and the cwd with `realpath` and build a spelling that climbs with `..`
3. Use the shorter. Before using it, check that the relative directory and the original directory have the same `(st_dev, st_ino)`, and that the cwd's `(st_dev, st_ino)` is the same as before 1. Otherwise the route is not usable
4. If the cwd's `(st_dev, st_ino)` has changed after the bind / connect, discard the result and return a generic error (do not remove a socket file it may have created)

### symlink base and name

| Item | Specification |
|---|---|
| base candidates | `TMPDIR` (when a non-empty absolute path), then `/tmp`. Tried once when `TMPDIR` is spelled the same as `/tmp` |
| safe base | stat'ed following symlinks, and one of<br>sticky bit set, owned by root or the effective uid<br>owned by the effective uid, with `mode & 0o022 == 0` |
| name | `sockat.` + 10 characters from 62 alphanumerics, taken from the OS's secure random source |
| collision | on `EEXIST` from `symlink(2)` draw a new name. Give up after 16 attempts and treat the candidate as not usable |
| bind's symlink | points to the socket's directory. Spelling `<base>/sockat.XXXXXXXXXX/<file name>` |
| connect's symlink | points to the socket file (the original path). Spelling `<base>/sockat.XXXXXXXXXX` |
| symlink target | the user's path as spelled (its directory part for a bind; a relative path gets the cwd prepended) |
| cleanup | removed whether the bind / connect succeeds or fails. A failure to remove is ignored |

- For each candidate, check the spelling's length and the base's safety before creating anything. A candidate whose spelling does not fit gets nothing and the next is tried
- Order: `TMPDIR` safe → symlink; unsafe → fd-held form; then `/tmp` safe → symlink; unsafe → fd-held form. Where there is no fd-held form, an unsafe candidate gets nothing and the next is tried
- When the symlink cannot be created (no base, not writable, names exhausted, no random bytes), the next candidate is tried as well

### The fd-held form (unsafe base)

On Linux / Android with `/proc` usable, an unsafe base candidate gets a directory of sockat's own, followed by fd rather than by name ([DR-0008](decisions/DR-0008-unsafe-base-held-by-fd.md), Japanese).

0. Before creating anything, check that `/proc` is usable (`/proc/self/fd/<fd>` resolves for an fd of the base). If not, create nothing and go on
1. Create a directory with mode 0700 in the base. Name and collisions as for the symlink (`sockat.` + 10 characters, a new name on `EEXIST`, give up after 16)
2. Open it `O_DIRECTORY | O_NOFOLLOW` and hold the fd; `fstat` that it is a directory, owned by the effective uid, with no permission for group or other. Otherwise not usable. Then `fchmod(fd, 0700)` to settle the owner's bits (so a umask that strips owner bits does not fail the check every time and pile up leftovers)
3. Create the symlink `s` in the fd with `symlinkat`, pointing to the socket file (the original path)
4. Hand the spelling `/proc/self/fd/<fd>/s`
5. Cleanup: `unlinkat(fd, "s")`. `rmdir` the directory only when `lstat` of its name gives the same `(st_dev, st_ino)` as the fd. Close the fd

- Only the connect variants use it. A bind spelling (`/proc/self/fd/<fd>/s/<file name>`) is longer than the /proc route's, so whenever it would fit the /proc route has already succeeded; it never helps a bind
- Not usable: the directory cannot be created, the `fstat` check fails, `symlinkat` fails
- Once found not usable, clean up what was created, then try the next candidate
- Cleanup happens whether the bind / connect succeeds or fails. A failure to remove is ignored

### The thread cwd route

The process's cwd is not changed ([DR-0005](decisions/DR-0005-thread-cwd-route.md), Japanese).

| OS | How |
|---|---|
| Linux / Android | on a throwaway thread, `unshare(CLONE_FS)` → `fchdir(dirfd)` → bind / connect by the file name |
| Apple OSes | on a throwaway thread, `pthread_fchdir_np(dirfd)` → bind / connect by the file name |
| others | not available |

- On every OS it runs on a throwaway thread sockat creates, discarded after use. The caller's thread's cwd is never touched (restoring with `pthread_fchdir_np(-1)` is not used: it could drop a per-thread cwd the caller set)
- Linux: when a seccomp filter is in place or this cannot be told (`prctl(PR_GET_SECCOMP)` returns non-zero or fails; emulated environments and kernels without seccomp give `EINVAL`) the route is not usable and `unshare` is not called. Some filters refuse `unshare` by killing the process (SIGSYS) rather than with an error (systemd's `SystemCallFilter=` by default, etc.)
- A failing `fchdir` after `unshare` (`EACCES` etc.) is a real failure and is returned, as on the fork route
- The caller creates the socket and holds the directory fd. For a non-blocking connect it makes the socket non-blocking first. The listen after a bind is done by the caller
- The directory is opened as for the fork route
- `pthread_fchdir_np` is a private libSystem API (a wrapper of the `__pthread_fchdir` syscall). It is looked up at run time; when absent the route is not usable
- No side effects: the peer pid stays the caller's, no fd is copied, and other threads' cwd is unchanged. So `connect` / `connect_nonblocking` try it too

### The fork route

1. The parent creates the socket, holds the directory fd and builds the sockaddr before forking. For a non-blocking connect it makes the socket non-blocking before the fork
2. The child does `fchdir(dirfd)` → `bind` / `connect` by the file name → `_exit(result)` (0 is success, 1–255 an errno)
3. The parent `waitpid`s for that pid only. The listen after a bind is done by the parent

- The child's section uses async-signal-safe calls only (no allocation, locks, or the language's cleanup)
- If `waitpid` fails with `ECHILD` (someone else reaped the status), read the result from the socket: for a bind whether `getsockname` holds a path, for a connect whether `getpeername` succeeds. A failure is a generic error
- How the directory is opened: `O_SEARCH` on Apple OSes (`O_RDONLY` if the kernel answers `EISDIR` / `EINVAL`), the `O_PATH` fd from the /proc route on Linux, `O_RDONLY` elsewhere

## How a failing route is treated

- When a route actually binds / connects and fails (`ENOENT`, `EADDRINUSE`, `ECONNREFUSED`, etc.), that error is returned and no later route or base is tried
- The next one is tried only when the route itself cannot be used
  - too short
  - `/proc` not usable
  - the kernel refuses the widened sockaddr
  - the base is unsafe or the symlink cannot be created
  - in the fd-held form (connect variants only), the directory cannot be created, the `fstat` check fails, or `symlinkat` fails
  - on the relative route, the directory of the spelling built does not match the original by `(st_dev, st_ino)`, or the cwd has already changed
  - on the thread cwd route, a seccomp filter is in place (Linux), `unshare` is refused, `pthread_fchdir_np` is absent or fails, or a thread cannot be created or pinned
- A missing directory is `ENOENT` on every OS. The directory is opened first, so this is settled before the file name's length is judged
- `connect` / `connect_nonblocking` open the directory and then return `ENAMETOOLONG` just before the fork route

## Where a path stops being reached

When a path over the standard length becomes `ENAMETOOLONG` (the directory exists; numbers in bytes).

| OS | `bind` | `connect` variants | `connect_any` variants |
|---|---|---|---|
| Linux (`/proc` present) | file name > 107 | file name > 107, and no symlink (whether or not the base is safe)<br>without thread cwd: file name does not fit the `/proc` spelling, relative path > 107, and no symlink (whether or not the base is safe) | file name > 107, and no symlink (whether or not the base is safe) |
| Linux (no `/proc`) | file name > 107 | file name > 107, and no symlink<br>without thread cwd: relative path > 107, and no symlink | file name > 107, and no symlink |
| FreeBSD | file name > 103 | file name > 103 | file name > 103 |
| macOS / iOS and the other Apple OSes | file name > 253 | file name > 253, and no symlink<br>without thread cwd: both the original and the relative path > 253, and no symlink | file name > 253, and no symlink |
| NetBSD / OpenBSD / other BSD | file name > 103 | relative path > 103, and no symlink | file name > 103, and no symlink |
| illumos | file name > 107 | relative path > 107, and no symlink | file name > 107, and no symlink |

- On Linux / Apple OSes where the thread cwd route is usable, the `connect` variants reach as far as the `connect_any` variants
- With the symlink route through `/tmp`, a connect reaches the path whatever the directory depth and the file name length
- On Linux with `/proc` usable, a connect reaches it likewise even through an unsafe base, as long as a directory can be created there (the fd-held form)
- A bind through `/tmp` takes a file name up to 84 bytes (80 on OSes with a 104-byte `sun_path`, 230 on macOS)

## Side effects of the fork route

| Side effect | Detail |
|---|---|
| peer pid | after a connect through the fork route, the peer pid the server sees is that of the exited child. uid / gid are the caller's<br>Linux's `SO_PEERCRED` keeps the child's pid<br>macOS's `LOCAL_PEERPID` turns into the caller's pid once the caller sends |
| fd copies | until it exits, the child holds copies of every fd. A socket or pipe another thread closes meanwhile stays open |

A bind has no side effect visible to the peer, since the child only binds and the parent listens.

## What differs from the standard for a long path

| Point | Detail |
|---|---|
| address the kernel reports | `getsockname` / `getpeername` return the spelling used for the bind (a relative path, `/proc/self/fd/...`, a symlink that no longer exists, the file name alone, a truncated path). For a widened sockaddr, some languages' standards append unrelated bytes after the cut (observed with CPython on macOS, regardless of version). The caller keeps the original path |
| directory looked up first | /proc, relative path, bindat, thread cwd and fork look up the directory, then pass the file name. A rename or symlink swap in between is not reflected. widened sockaddr and symlink behave as the standard |
| another thread's chdir | the relative route returns a generic error if the cwd stayed changed in between. A change and change back is not seen |
| leftover symlink | if the process dies before removing the symlink or the fd-held form's directory, `sockat.XXXXXXXXXX` is left in the base |

- NUL anywhere but at the start is an invalid argument even in a short path. A language whose standard silently truncates at NUL (Go etc.) says so under "differs from the standard" in its README

## Errors

| Situation | Error |
|---|---|
| no directory / nothing to connect to | `ENOENT` |
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
- In a language that brings a socket it created into the standard type, check that a socket bound / connected with a widened sockaddr does not break that step or the address lookups (Go does, so Go skips the widened route). If it breaks, treat the route as one the language cannot build and skip it
- Keep the routes out of the public API. Tests force each route by calling it directly from inside the package
- Make the parts that read the environment (symlink base candidates, the location of `/proc/self/fd`, whether an Apple OS takes the widened sockaddr, whether the thread cwd route is usable) replaceable from tests
- Link this specification from the README and manual. Before introducing behavior that differs from it, change this specification first

## What implementations test

| Aspect | What to check |
|---|---|
| short path boundary | exactly the standard length goes to the standard unchanged; one byte more goes to the routes (check the boundary with the standard itself) |
| location | on each route the socket file is created at the original path and nothing remains in the base |
| traffic | on each route data actually flows between the bound listener and the connected stream |
| standard types | the return values work as the standard types (in languages with async runtimes, hand them over and use them) |
| no retry on failure | `ENOENT` / `EADDRINUSE` / `ECONNREFUSED` are returned and nothing is created on later routes or bases (the later candidate directory's mtime is unchanged) |
| Linux without /proc | with the `/proc/self/fd` location replaced by an empty directory etc., relative path → symlink → thread cwd → fork is followed |
| symlink base | an unsafe base is skipped, a too deep `TMPDIR` falls back to `/tmp`, colliding names are skipped and the attempts stop at 16, the symlink is removed on success and on failure |
| fd-held form | in an unsafe base, the socket is created at the original path and reached, nothing remains in the base afterwards, a directory swapped between creating and opening (other owner or mode) is not used, `TMPDIR` is used before `/tmp`, and unsafe bases are skipped when `/proc` is not usable |
| connect and fork | the `connect` variants return `ENAMETOOLONG` when only the fork route reaches; the `connect_any` variants reach and return `true` |
| cwd | the cwd is unchanged after every route; a cwd change during the relative route is a generic error |
| thread cwd | with the route forced, the process's cwd is unchanged, the peer pid is the caller's, and the socket is created at the original path. When not usable, the next route is tried |
| fork | the peer pid behavior; reading the result with `SIGCHLD` set to `SIG_IGN` |
| macOS | a 253-byte path goes through the widened sockaddr |
| non-blocking connect | a full backlog fails without waiting |
| path not ending with a name, NUL anywhere but at the start | invalid argument, nothing created. NUL even for a short path. A leading NUL (abstract) goes to the standard |
| address the kernel reports | reading it does not fail for a long path |

- The routes differ per OS, so run at least on macOS and Linux. Other Unixes run in CI VMs
- Tests that change process-wide settings such as the cwd or signal handling run inside a child process
- The fork route's child briefly holds copies of every fd, so create "a socket nobody listens on" in a separate process

## Open questions

- Android and the Apple OSes other than macOS are not checked at all
- NetBSD / OpenBSD / illumos: the peer credentials are not checked
- That a non-blocking connect never answers `EINPROGRESS` is checked only on Linux and macOS
