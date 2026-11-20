# sockat specification

> English | [日本語](./SPEC-ja.md)

How sockat behaves, independent of the language (the promise to users and to those who write each language's README). Every implementation follows it.

- How the routes are built (building the base B, each route's steps): [SPEC-routes.md](SPEC-routes.md)
- How far each condition reaches: [the reach table](../pages/reach/README.md)
- Decisions and rejected alternatives: [docs/decisions](decisions/INDEX.md) (Japanese; the current design is [DR-0017](decisions/DR-0017-resolve-through-persistent-base.md))
- What is specific to a language (types, runtime integration, memory safety): the README and manual of each language's repository ([sockat-rs](https://github.com/kawaz/sockat-rs), [sockat-py](https://github.com/kawaz/sockat-py), [sockat-go](https://github.com/kawaz/sockat-go))

## Terms

| Term | Meaning |
|---|---|
| standard | the language's standard library bind / connect for Unix domain sockets |
| standard length | the longest path the language's standard accepts. A path up to it is handed to the standard unchanged. Usually `sun_path` − 1, `sun_path` − 2 for Java ([DR-0004](decisions/DR-0004-standard-length-per-language.md), Japanese) |
| sockaddr length | the length of `sun_path` − 1 byte (leaving room for the NUL). The longest spelling a sockaddr that is not widened carries |
| original path | the path the user passed |
| directory / file name | what precedes the last component of the original path, and the last component. The socket's directory is the former |
| spelling | the path string handed to the kernel. The kernel remembers a bind's spelling and returns it from `getsockname` / `getpeername` |
| route | a way to build another spelling of the same place as the original path and bind / connect with it. The names are in "[Route names](#route-names)" |
| try | check whether a route can be used, and if so bind / connect with its spelling. If not, go on to the next route |
| unusable / failure | unusable: the route itself cannot be used (the spelling does not fit, the means is missing, B / D / E cannot be created). failure: the bind / connect was actually made and the OS returned an error ([How a failing route is treated](SPEC-routes.md#how-a-failing-route-is-treated)) |
| base | where B is created. One of `/tmp`, `$XDG_RUNTIME_DIR`, `$TMPDIR` and the socket's directory ([Where B is created](SPEC-routes.md#where-b-is-created)). Not used when the user gives B itself in `Options.base` |
| B | a real directory created in the base. One per user, reused across processes |
| D | a directory created in B, one per (process, B). Its name is random |
| E | a symlink. One kind points to the socket's directory (link-dir and thread-cwd / at), the other to the socket file (link-file) |
| procB | spelling B as `/proc/<pid>/fd/<B's fd>`. Only processes of the same uid can follow it, and it cannot be followed after the process exits |
| real-path spelling | spelling B by its real path |
| resolve | turning a long path into a short spelling through B / D / E and returning it ([resolve](#resolve)) |
| spelling properties | whether a bind's spelling can be used later. Returned as `Spelling` ([Spelling properties: `Spelling`](#spelling-properties-spelling)). `Dangling` is a spelling that contains an E already removed, and reaches nothing |
| the connect variants | `connect`, `connect_nonblocking`, and the `_ex` of each |
| `/proc` usable | `/proc/self/fd/<fd>` and `/proc/<pid>/fd/<fd>` can be looked up |

OSes are grouped as follows.

| Group | What it covers |
|---|---|
| Linux / Android | the OSes with the Linux kernel |
| Apple OSes | macOS, iOS, etc. Where only macOS is written, it was measured on macOS |
| FreeBSD, NetBSD, OpenBSD, illumos | each of these OSes |
| other Unix | Unix-like OSes not listed above |

## Scope

- bind (and listen) / connect / `send_to` of pathname Unix domain sockets
- socket types stream, DGRAM and SEQPACKET (details of DGRAM and SEQPACKET are in "[Open questions](#open-questions)")
- Unix-like OSes. Windows is not supported

## Operations

- They are placed in a module per type, in the standard library's form (stream at the crate root, `datagram::`, `seqpacket::`)
- The default operations take only a path. For those who need cleanup and diagnostics, one `_ex(…, Options)` is provided for each default operation
- For those who hand the spelling to the standard library themselves, there are two resolves, one per use ([resolve](#resolve))
- `sweep()` removes the dead D in the base ([`sweep`](#sweep))
- There is no way for the user to choose or combine routes, and no function that changes a process-wide default
- Names follow each language's conventions. Python puts `_ex` in the submodule `sockat.ex` (to keep them apart from the standard `socket.connect_ex`). Go's stream functions are `Listen` / `ListenEx` / `Dial` / `DialEx`

### Functions

Shown with the Rust names.

| Type | Function | Returns |
|---|---|---|
| stream | `bind(path)` | a listening standard listener |
| stream | `connect(path)` | a standard stream |
| stream | `connect_nonblocking(path)` | a non-blocking standard stream |
| stream | `bind_ex(path, Options)` | `Bound<UnixListener>` |
| stream | `connect_ex(path, Options)` | `Connected<UnixStream>` |
| stream | `connect_nonblocking_ex(path, Options)` | `Connected<UnixStream>` (the stream is non-blocking) |
| DGRAM | `datagram::bind(path)` | a standard `UnixDatagram` |
| DGRAM | `datagram::unbound()` | a standard `UnixDatagram` |
| DGRAM | `datagram::connect(&sock, path)` | nothing |
| DGRAM | `datagram::send_to(&sock, buf, path)` | the number of bytes sent |
| DGRAM | `datagram::bind_ex(path, Options)` | `Bound<UnixDatagram>` |
| DGRAM | `datagram::connect_ex(&sock, path, Options)` | `Report` |
| DGRAM | `datagram::send_to_ex(&sock, buf, path, Options)` | the number of bytes sent and `Report` |
| SEQPACKET | `seqpacket::bind(path)`, `connect(path)`, `connect_nonblocking(path)` and each `_ex` | open |
| resolve | `resolve_for_bind(path, Options)` | `ForBind` |
| resolve | `resolve_for_connect(path, Options)` | `ForConnect` |
| base | `sweep()` | nothing |

- On failure, the default operations return the standard's error type; `_ex` and resolve return an error type that carries diagnostics ([Diagnostics](#diagnostics))
- For DGRAM, only the functions of the standard `UnixDatagram` that take a path, and `unbound` used with them, are mirrored. `pair` is not
- A DGRAM connect tries the routes in the same order as a stream connect ([Connect order](#connect-order)). The routes of `send_to` are in "[Open questions](#open-questions)"

### `Options`

| Field | What it is |
|---|---|
| `usable_cross_uid: bool` | asks for a spelling that a peer of another uid can also follow. It affects how B is chosen and keeps procB from being used. When it cannot be met, thread-cwd / at is used ([Another uid and PrivateTmp](SPEC-routes.md#another-uid-and-privatetmp)). Whether it was met is told by the resulting `Spelling` |
| `base: Option<Path>` | the user gives the path of B itself (an app passes a place it manages, e.g. `/tmp/app-<uid>/sockat`). B is created there; when the checks fail it is an error, and it does not fall back to the automatic bases ([Errors](#errors)). Together with `usable_cross_uid`, it is also checked that every directory on the way to that base gives x to other. Passing a different `base` per call makes one process hold several B. The spelling form is chosen in the same order as in the automatic case |

### What is returned

| Type | Contents |
|---|---|
| `Bound<S>` | `socket` (the standard type), `file: SocketFile` (`remove()`, `cleanup()`), `spelling: Spelling`, diagnostics (`route`, `base`, `skipped`) |
| `Connected<S>` | `socket` (the standard type), diagnostics (`route`, `skipped`) |
| `Report` | diagnostics (`route`, `skipped`) |
| `ForBind` | `path` (the spelling), `spelling`, `remove()`, `cleanup()`, diagnostics |
| `ForConnect` | `path` (the spelling), `cleanup()`, diagnostics. It has no `remove()` (the type prevents removing by mistake) |

- `remove()` and `cleanup()` are in "[Cleanup](#cleanup)"
- The properties of a connect's spelling are not returned (a connect's spelling does not stay with the peer)
- There is no bool for "was it handed to the standard unchanged" (`spelling == Original` or `route == "standard"` tells)
- Field and type names follow each language's conventions

### Non-blocking connect

- The socket is made non-blocking before connecting and returned that way. When the peer's backlog is full it fails without waiting
- `EINPROGRESS` is returned as an error and the socket is closed
- Cleanup does not wait (an E the default connect created for link-file is only unlinked)
- A language whose standard connect never blocks (Node.js, Go, etc.) provides one connect in the standard's own form and no separate `_nonblocking`. The same for the `connect_ex` variants ([DR-0003](decisions/DR-0003-single-connect-when-standard-never-blocks.md), Japanese). Go's `Dial` / `DialEx`, like the standard `net.DialUnix`, never wait (when the backlog is full, Linux gives `EAGAIN` at once and macOS `ECONNREFUSED`)

### Same as the standard

- The listener / stream / datagram returned is of the same type the standard returns, so it is a drop-in replacement for the standard
- A socket the implementation creates itself gets the same settings as one the language's standard creates (close-on-exec, `SO_NOSIGPIPE`, the listen backlog, etc.). There is no way to specify the backlog
- Whether closing a standard listener removes the socket file is left to the standard's own mechanism (the differences for a long path are in "[What differs from the standard for a long path](#what-differs-from-the-standard-for-a-long-path)"). The listener of `bind_ex` does not remove the file when closed, even for a short path; only `remove()` removes it

### Diagnostics

On success `_ex` and resolve return the following.

| Field | What it is |
|---|---|
| `route` | the name of the route taken |
| `base` | the spelling of the B a bind used (`proc`, `sockdir`, `runtime`, `tmpdir`, `tmp`). It has a value only when the spelling goes through B (link-dir, link-file), and none otherwise (standard, thread-cwd, at). `Connected` and `Report` have none |
| `skipped` | the routes tried and found unusable, in the order tried. Each element is `{ name: the route name, reason: why it was unusable }`. For a long path `standard` is included |

- `skipped` has one element per route name. Trying link-dir with procB and with the real path is still one element, with the `reason` of the last try. Not using procB because of `usable_cross_uid` is not skipping a route, so nothing is added

- Every route tried before `route` was unusable (when a route actually binds / connects and fails, the error is returned there and the next is not tried; only when a bind's link-file is told apart at run time does it go on). So there is no "was it usable" bool
- The names in `route`, `base` and `skipped` and the `reason` are for diagnostics and promise nothing about their content (routes are added and changed). Branch on `Spelling`
- Route names are the same ASCII in Japanese and English
- When `_ex` fails, the error carries `skipped` too. When a route actually bound / connected and failed, its name (`route`) is attached as well (none for `ENAMETOOLONG`, where none could be used)
- How they are attached follows each language's conventions. The errno of an OS error stays readable (Rust gives `skipped` to an error type holding the errno, Go an error type whose `Unwrap` reaches the errno, Python an attribute of the exception, etc.)

## resolve

It turns a long path into a short spelling that keeps pointing to the same place as the original path and returns it. While the spelling lives, upper libraries that remove by the `getsockname` spelling, DGRAM replies and operational tools work as with the original path. The spelling is just a path, so the user can hand it to the standard library whatever the socket type (stream / DGRAM / SEQPACKET) and operation (bind / connect / `send_to`).

| | `resolve_for_bind` | `resolve_for_connect` |
|---|---|---|
| Spelling | `B/D/E/<file name>` (link-dir) first, then `B/D/E` (link-file) | `B/D/E` (link-file), whatever the file name's length |
| Where link-file is used | only on the OSes measured to follow a symlink on bind (macOS, NetBSD). On OSes not yet checked, link-dir only (resolve does not bind, so whether bind follows cannot be told) | every OS (connect always follows a symlink in the last component) |
| Returns | `ForBind` (`spelling`, `remove()`, `cleanup()`) | `ForConnect` (`cleanup()`) |
| When it cannot | `ENAMETOOLONG` (a length only thread-cwd / at reaches) | `ENAMETOOLONG` (link-file cannot be used, e.g. B cannot be created) |

- A path up to the standard length is returned unchanged (`Original` for an absolute path, `CwdRelative` for a relative one)
- resolve only returns a spelling, so those who want the `ENAMETOOLONG` cases reached too use `bind` / `connect`. The default `bind` can try thread-cwd / at, and the default `connect` the routes needing no write and thread-cwd-direct
- resolve spells B as procB or the real path, chosen as for the default bind ([Spelling forms](SPEC-routes.md#spelling-forms))
- resolve does not list B on each call (so as not to add steps to resolve)
- To connect to the same path repeatedly, use the spelling made once by `resolve_for_connect` for every connect and `cleanup` at the end
- The default `bind` uses resolve internally and reaches lengths resolve cannot with thread-cwd / at. The default `connect` creates no D ([Connect order](#connect-order)). The default bind keeps its spelling; the default connect does not

## Spelling properties: `Spelling`

Whether a bind's spelling can be used later is returned as one value (`spelling` of `Bound` and `ForBind`).

```rust
#[non_exhaustive]
pub enum Spelling {
    Original,
    CwdRelative,
    Linked { removable: bool, until: Until, usable_cross_uid: bool, usable_with_private_tmp: bool },
    Dangling,
}
```

| Value | Spelling | Route |
|---|---|---|
| `Original` | the original absolute path | standard |
| `CwdRelative` | the original relative path. It points elsewhere after the cwd changes (a hazard the standard already has, but it is reported) | standard |
| `Linked` | goes through B / D / E and points to the same place as the original path | link-dir, link-file |
| `Dangling` | contains an E already cleaned up. Reaches nothing | thread-cwd, at |

Attributes of `Linked`:

| Attribute | What it is | Value |
|---|---|---|
| `removable` | whether unlinking by the spelling removes the real file | true for link-dir (the E in the middle is followed). false for link-file (the last symlink is not followed and E is removed; removing the file needs `remove`) |
| `until` | until when the spelling can be followed | `Process` (procB: not after the process exits). `Cleanup` (real-path spelling: E stays until `cleanup`, D until the OS cleaning after the process exits) |
| `usable_cross_uid` | whether a peer of another uid can follow it | false for procB (same uid and same PID namespace only; root can follow). For a real-path spelling, true when every directory on the way to B gives x to other (B in `/tmp`), otherwise false (`/run/user/<uid>` and macOS's `$TMPDIR` are 0700) |
| `usable_with_private_tmp` | whether the peer can follow it even when either side has its `/tmp` isolated (systemd's `PrivateTmp`, etc.) | true when the spelling does not pass through `/tmp` or `/var/tmp`. A peer in a wholly different mount namespace (a container, etc.) is not covered |

- A connect's spelling does not stay with the peer, so its properties are not returned

## Cleanup

### `remove` and `cleanup`

| Call | What it does | Held by |
|---|---|---|
| `remove()` | removes the bound socket file once, and does `cleanup` too | `SocketFile` of `Bound`, `ForBind` |
| `cleanup()` | cleans up resolve's E once | `SocketFile` of `Bound`, `ForBind`, `ForConnect` |

- Neither happens automatically (Rust's Drop does not do them either). From the second call on they do nothing (`remove` is idempotent in the sense that it removes what the resolved spelling points to once)
- sockat does not clean up B and D ([What stays in the base](#what-stays-in-the-base))
- Do not use a spelling after it is cleaned up. When B is in `/tmp`, after B is gone someone else can recreate the same name (as with the standard library: after the original path is removed, anyone who can write to that directory can recreate it)

### `remove`

- `remove` only removes the file and does not close the listener. The user closes it
- It remembers the realpath and `(st_dev, st_ino)` of the bound socket file and removes it only when that path still has the same `(st_dev, st_ino)`
  - It remembers them right after the bind succeeds (before returning the listener). If they cannot be remembered, it closes the listener, leaves the file, and returns an error (it does not hand back a `remove()` that cannot remove anything as a success)
  - For a relative path, compare the process's cwd `(st_dev, st_ino)` before anything about the path is looked up and after both the bind and the realpath taken for remembering; if they differ, treat it like the case where they cannot be remembered (so that a cwd change in between does not make it remember and remove an unrelated file under the old cwd. A change and change back is not seen)
  - The path argument is turned into a string once at the entry, and that value is used for remembering, binding and returning alike
- It succeeds when the file is already gone and when it has been replaced by another file and is left alone. It fails when the check cannot be made (`lstat` fails with something other than `ENOENT` / `ENOTDIR`) and when the removal itself fails
- A replacement is told apart by `(st_dev, st_ino)` only, and what is promised is a replacement while the listener is open. Something removed and recreated after the listener is closed cannot be told apart on a filesystem that reuses numbers at once (ext4, BSD UFS / FFS). Each language's docs recommend calling `remove` before closing the listener ([findings](findings/2026-11-19-inode-reuse-after-close.md), Japanese)
- Someone who can write to the socket's directory swapping the file between the check and the removal, or between the bind and the remembering, cannot be prevented (POSIX has no way to remove by inode)

| Language | Form |
|---|---|
| Rust | `remove` of `SocketFile` |
| Python | the return value includes a function without arguments |
| Go | the return value includes a `func() error`. Even for a short path, only this removes the file (`SetUnlinkOnClose(false)`) |

### What stays in the base

| | B | D | E |
|---|---|---|---|
| Unit | one per user, reused across processes. A process uses one B in the automatic bases (one more only with `usable_cross_uid`). A B in `Options.base` is one per given path | one per (process, B). Created only by a bind that keeps its spelling (including thread-cwd / at) and by `resolve_for_connect` | one per resolve. One per call for thread-cwd / at and for the default connect's link-file |
| While alive | not removed | the process keeps an fd holding a flock (shared lock) | resolve's E is not removed |
| Cleanup | not by sockat (B in `Options.base` is managed by the app) | not by sockat. A dead process's D is removed by the OS's temporary-directory cleaning. Only when `sweep()` is called are the D whose lock has been released removed | resolve's E by `cleanup`. A per-call E is unlinked within the call |

- The default `bind` returns no `SocketFile`, so its E stays until the process exits and is removed with D by the OS's temporary-directory cleaning. There is no mechanism for cleaning up after a process that execs. Users who care about cleanup use `_ex` or resolve
- The default `connect` leaves no state in the process (it creates no D, and unlinks the E right under B right after the connect)

The OS's temporary-directory cleaning ([research](research/2026-11-20-tmp-cleaners-and-persistent-base.md), Japanese):

| Base | A dead D | A live D |
|---|---|---|
| Linux's `/tmp` | systemd-tmpfiles removes it with everything under it at an age of 10 days | a directory holding a flock is skipped with everything under it (systemd v242 or later). In older environments (v239 of RHEL 8, etc.) it can be removed after 10 days |
| `$XDG_RUNTIME_DIR` | no cleaning by age; it stays until the last logout and reboot | same |
| macOS's `/tmp` | a directory containing a symlink is not removed, so it stays until reboot | not removed |
| macOS's `$TMPDIR` | dirhelper may remove it after 3 days (the handling per file type is not checked) | same |
| FreeBSD, NetBSD, OpenBSD, illumos | by default not removed, or removed on reboot. The daily cleaning does not remove symlinks | same |

- When a live D is removed, the spelling only stops being followable; nothing dangerous happens
- Across an exec the fd holding D's flock is closed, and even if the inherited listener lives, D and E can be removed by `sweep()` or the OS's cleaning (the spelling only stops being followable). A procB spelling stops being followable at the exec

### `sweep`

- Only when called, it removes the D in B whose owners are dead (D whose lock has been released). It does not remove the D of other live processes (how it tells is in [D and E](SPEC-routes.md#d-and-e))
- It is never called automatically (resolve does not list B on each call)

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
| Apple OSes / FreeBSD / NetBSD / OpenBSD | 103 bytes |

## Routes for long paths and their order

A path over the standard length is tried on the routes in the order below and bound / connected on the first route that can be used. How each route is built is in [SPEC-routes.md](SPEC-routes.md#routes); how far it reaches is in [the reach table](../pages/reach/README.md).

- A path whose last component is not a file name (`dir/`, `dir/.`, `dir/..`, `..`) is an invalid-argument error, and nothing is created
- The socket's directory is looked up first. When it is missing, `ENOENT`; when it is not a directory, `ENOTDIR` (before the length is judged or B / D / E is created)
- No route changes the calling process's cwd or the calling thread's cwd
- No fork (neither for bind nor for connect). The cases only a fork reached, and the fork technique, are in [fork-cwd](../pages/fork-cwd.md)

### Route names

A name is "means + what it is about". The suffix `-direct` is the form that passes the file name without going through E.

| Name | What it does | Operation |
|---|---|---|
| `standard` | hand the path to the standard unchanged | bind, connect |
| `link-dir` | `B/D/E/<file name>` through an E pointing to the socket's directory | bind |
| `link-file` | `B/D/E` through an E pointing to the socket file (`B/E` with B's real path for the default connect) | bind, connect |
| `thread-cwd` | move a throwaway thread's cwd into D, then `E/<file name>` through an E removed at once | bind |
| `at` | the same spelling as thread-cwd, passed to `bindat` with D's fd and no thread | bind |
| `proc-direct` | `/proc/self/fd/<fd of the socket's directory>/<file name>` | connect |
| `relative` | a path relative to the cwd | connect |
| `widened` | a widened sockaddr | connect |
| `at-direct` | `connectat` with the socket's directory fd and the file name | connect |
| `thread-cwd-direct` | move a throwaway thread's cwd into the socket's directory and pass the file name | connect |

### Bind order

| Order | Route | B spelled as | Spelling | Used when | `Spelling` |
|---|---|---|---|---|---|
| 1 | `standard` | | the original path | up to the standard length | `Original` / `CwdRelative` |
| 2 | `link-dir` | procB | `B/D/E/<file name>` | `/proc` is usable and it fits (not with `usable_cross_uid`) | `Linked` |
| 3 | `link-dir` | real path | same | it fits | `Linked` |
| 4 | `link-file` | real path | `B/D/E` | OSes whose bind follows a symlink in the last component | `Linked` |
| 5 | `thread-cwd` (`at` on FreeBSD) | | `E/<file name>` | Linux / Android, Apple OSes (`at` on FreeBSD) | `Dangling` |
| 6 | `ENAMETOOLONG` | | | | |

- The spelling is kept, so while it lives, upper libraries that remove by the `getsockname` spelling and DGRAM replies work as with the original path. thread-cwd / at come after, for when resolve's spelling does not fit
- link-file is not tried on the OSes measured not to follow a symlink on bind (Linux / Android, FreeBSD, OpenBSD, illumos). macOS and NetBSD follow it (measured 2026-11-19, [findings](findings/2026-11-19-bind-through-file-symlink.md), Japanese). On other OSes it is tried and whether it follows is told apart at run time
- bind does not use proc-direct, relative, widened or at-direct. Their spelling later hits an unrelated file (proc-direct, relative, at-direct), or the address is cut in the middle and breaks the reading side (widened)
- When no B meets `usable_cross_uid`, or its spelling does not fit, it goes to 5 rather than falling back to a spelling that does not meet it

### Connect order

Routes needing neither a write nor a thread come first; routes that start a thread and routes that write to the base come after.

| Order | Route | What it does |
|---|---|---|
| 1 | `standard` | the original path |
| 2 | `proc-direct` / `relative` / `widened` / `at-direct` | needs neither a write nor a thread (per OS, table below) |
| 3 | `thread-cwd-direct` | needs neither D nor E |
| 4 | `link-file` | create an E with a random name right under B, connect by `B/E` with B's real path, and unlink E at once (procB is not used). Reaches whatever the file name's length. Unusable when the spelling does not fit |
| 5 | `ENAMETOOLONG` | |

| OS | Routes of 2 |
|---|---|
| Linux / Android (`/proc` usable) | proc-direct |
| Linux / Android (`/proc` not usable) | relative |
| Apple OSes | relative → widened |
| FreeBSD | at-direct |
| NetBSD / OpenBSD / illumos / other Unix | relative |

- A connect's spelling does not stay with the peer (the connecting socket is not bound), so no E is kept. A one-off connect from a CLI usually ends at 2, and reaches even in a sandbox with no writable base
- relative and widened sometimes reach farther than the routes through the base
- 3 can be used on Linux / Android and Apple OSes ([thread-cwd-direct](SPEC-routes.md#thread-cwd-direct))
- A DGRAM connect uses the same order

## What differs from the standard for a long path

| Point | What happens |
|---|---|
| The address the kernel returns | `getsockname` on the bound side, and `getpeername` on a side that connected to it, return the bind's spelling, not the original path. Whether it can be used later is told by `Spelling`. A language that can replace, within the standard type, what returns the address (Python) returns the original path. On illumos, the connecting side's `getpeername` returns the spelling passed to connect rather than the one bound (measured in sockat-rs's CI, 2026-11-19) |
| How it looks in operational tools | the address shown by `ss -x`, `lsof`, `/proc/net/unix`, etc. is the bind's spelling. For link-dir and thread-cwd / at the file name stays at the end of the spelling. A link-file spelling does not show the file name |
| When the listener is closed | a standard that removes by the address's spelling on close (Go's `UnixListener.Close`, etc.) removes the file at the original path when the spelling's `removable` is true. With a link-file spelling E is removed and the file stays; with `Dangling` nothing is removed |
| The directory is looked up first | link-dir's and thread-cwd / at's E point to the realpath of the socket's directory, and proc-direct, at-direct and thread-cwd-direct look up the directory before passing the file name. A rename or a symlink swap in between is not reflected |
| Another thread's chdir | relative gives a general error when the cwd changed in between and stayed changed. A change and change back is not seen |
| State grows outside the app's own place | B / D / E stay in `/tmp`, `$XDG_RUNTIME_DIR`, `$TMPDIR`. The default `bind`'s E and a dead process's D stay until the OS cleans them ([What stays in the base](#what-stays-in-the-base)) |
| Environments where a live D can be removed | Linux with systemd older than v242, and B in macOS's `$TMPDIR` ([What stays in the base](#what-stays-in-the-base)). The spelling only stops being followable |
| A peer with `PrivateTmp` | when the peer's `/tmp` is isolated, it cannot follow a spelling through `/tmp`. On Linux procB is used first, so this rarely happens. `usable_with_private_tmp` tells whether it can follow |

- NUL anywhere but at the start is an invalid argument even for a short path. A language whose standard silently truncates at NUL (Go, etc.) says so under "differs from the standard" in its README

## Patterns not to use

Patterns that, when using sockat, remove an unrelated file or fail to remove the file. This section is the source for warnings to users; other sections and each language's docs point here. Each language's README / manual gives, under the same heading, the concrete form in that language (e.g. Go's `os.Remove(l.Addr().String())`) and recommended code that avoids it (run as a test).

| Pattern | Why not | Instead |
|---|---|---|
| unlinking / stat-ing the socket file by the spelling the kernel returns (`getsockname`, the listener's address, etc.) without looking at `Spelling` | with a link-file spelling only E is removed and the file stays. A `Dangling` spelling reaches nothing | keep the original path and use it. `remove()` |
| using an old spelling after `cleanup` or after the process exits | after B in `/tmp` is cleaned up, someone else can recreate the same name. A procB spelling cannot be followed after the process exits | use a spelling only within `until` |
| binding with a relative path and removing it by that relative path after changing the cwd | it hits a file elsewhere (`CwdRelative`) | make the path absolute before binding. `remove()` |
| relying on closing the listener to remove the socket file | for a long path it depends on the spelling and may not be removed ("[What differs from the standard for a long path](#what-differs-from-the-standard-for-a-long-path)"). The listener of `bind_ex` never removes it on close | `remove()`, or remove by the original path |
| relying on `remove()` to close the listener too | `remove()` only removes the file | close the listener yourself |
| calling `remove()` after closing the listener | another file recreated after the close may not be told apart ([`remove`](#remove)) | call it before closing the listener |
| letting a peer of another uid follow a procB spelling or a spelling with `usable_cross_uid` false | it cannot be followed | give `Options.usable_cross_uid` and check the resulting `Spelling` |
| branching on the strings in `route`, `base`, `skipped` or `reason` of `_ex` | they are for diagnostics and promise nothing about their content | branch on `Spelling` |

## Errors

| Situation | Error |
|---|---|
| the directory is missing / nothing to connect to | `ENOENT` |
| something other than a directory where the directory should be | `ENOTDIR` |
| a file already exists where bind would create one | `EADDRINUSE` |
| a socket file nobody listens on | `ECONNREFUSED` |
| the backlog is full | Linux gives `EAGAIN` for a non-blocking connect (a blocking connect waits); macOS gives `ECONNREFUSED` |
| no route can be used (the spelling does not fit, the means is missing) | `ENAMETOOLONG` |
| `resolve_for_bind` at a length only thread-cwd / at reaches | `ENAMETOOLONG` |
| `resolve_for_connect` when link-file cannot be used (B cannot be created, the spelling does not fit) | `ENAMETOOLONG` |
| a directory on the way to `Options.base` is missing | `ENOENT` |
| `Options.base` is not a directory | `ENOTDIR` |
| `Options.base` failed the owner / permission checks (including, with `usable_cross_uid`, whether every directory on the way gives x to other) | `EPERM` |
| a path over the standard length that does not end in a name | invalid argument |
| a path containing NUL anywhere but at the start (whatever its length) | invalid argument |
| the cwd changed during relative | general error |

- The directory is looked up first, so `ENOENT` and `ENOTDIR` are decided before the length on every OS
- An `Options.base` error does not fall back to the automatic bases
- OS errors are returned in a form from which the errno can be read in that language's way
- Which type represents "invalid argument" and "general error" is up to each implementation

## What each implementation must do

- Follow the routes and order of this specification ([SPEC-routes.md](SPEC-routes.md)). A route that cannot be built in the language is skipped (treated as unusable and the next is tried, and put into `_ex`'s `skipped` with the reason), and the README states it in an OS × route table
- Provide the test CLI of the language-independent conformance test ([docs/design/conformance.md](design/conformance.md), Japanese)
- In a language that adopts its own socket into the standard type, check that adopting a socket connected via widened, and reading its address, do not crash. If they crash, skip widened as a route that cannot be built
- Routes are not exposed in the public API. Tests force each route by calling it directly from inside the package
- The parts that read the environment (the base candidates, where `/proc` is, whether Apple OSes accept a widened sockaddr, whether the thread cwd can be used) can be replaced from tests
- The README and manual link to this specification. Before adding behavior that disagrees with it, fix this specification first
- What the user-facing docs state: that state grows outside the app's own place, that a spelling is not used after cleanup, a peer with `PrivateTmp`, and that a live D can be removed in environments with systemd older than v242 and in macOS's `$TMPDIR` (each item is in "[What differs from the standard for a long path](#what-differs-from-the-standard-for-a-long-path)" and "[Patterns not to use](#patterns-not-to-use)")

## What implementations test

| Aspect | What to check |
|---|---|
| The short-path boundary | a path exactly the standard length goes to the standard unchanged, and one byte longer goes to the routes (checking the boundary with the standard itself) |
| Where the spelling lands | unlinking / stat-ing the spelling does not hit an unrelated file (a same-named file in the cwd, a same-named file in another directory whose fd number was made to be reused) |
| Checking B | a base that fails the checks on the way to B is not used. `Options.base` that fails is an error |
| Concurrency | many concurrent binds / connects do not conflict in creating B / D |
| `sweep` | it does not remove the D of other live processes |
| `cleanup` | no E remains after `cleanup` |
| The default connect | nothing remains right under B after the connect, and it does not wait |
| `remove` | the file is removed and the listener is not closed. If the file was replaced by another while the listener was open, it is not removed |
| thread-cwd / at | when forced, neither the process's cwd nor the calling thread's cwd changes and no E remains after the call. The socket is created at the original path and can send and receive |
| link-file on bind | on an OS whose bind does not follow the symlink it goes into `skipped` and nothing remains. When something is at the original path, that error (`EADDRINUSE`) is returned and the next is not tried |
| The connect routes | forcing proc-direct, relative, widened, at-direct, thread-cwd-direct and link-file one by one reaches the socket |
| No retry on failure | `ENOENT` / `EADDRINUSE` / `ECONNREFUSED` are returned and nothing is created on later routes |
| relative and the cwd | a cwd change during relative gives a general error |
| macOS | a 253-byte path reaches via widened for the connect variants. bind does not use widened |
| Non-blocking connect | it fails without waiting when the backlog is full |
| A path not ending in a name, NUL not at the start | an invalid argument with nothing created. NUL even for a short path. A path starting with NUL (abstract) goes to the standard |
| The address the kernel returns | reading it does not crash even for a long path. In a language that can replace it, the listener, an accepted socket and a connected socket each return the original path, and the language's typical upper library (Python asyncio's `start_unix_server(sock=...)`, etc.) works as for a short path without extra arguments |

- Routes differ per OS, so run at least on macOS and Linux. Other Unix in CI VMs
- Tests that change process-wide settings, such as the cwd or signal handling, run in a child process

## Open questions

- Reach: a procB spelling takes about 35 bytes for `/proc/<pid>/fd/<fd>/` + D + `/E/`, and the file name reached on Linux is about 70. Between that and thread-cwd, thread-cwd is used
- The length of the names of B / D / E (it affects the reach; the reach table estimates B at 17 bytes)
- Whether FreeBSD's connect can use link-file (not checked)
- `send_to` sends to resolve's spelling, so it does not use relative (a send cannot be taken back). What to do with a `send_to` at a length resolve cannot handle (send with thread-cwd, or `ENAMETOOLONG`)
- A reply to a DGRAM sender bound to a long path reaches while the spelling lives (procB for the same uid, the real path of B in `/tmp` for another uid too). How `Spelling` expresses the cases where it does not reach (after `cleanup`, procB with another uid)
- The return type of Rust's SEQPACKET
- The identity for `remove()` of `ForBind`: at resolve time nothing is bound, so the socket file's `(st_dev, st_ino)` cannot be remembered. The form is open (a proposal: a call made after the bind that receives a `SocketFile`)
- Android and the Apple OSes other than macOS are not checked at all
- The peer credentials on NetBSD, OpenBSD and illumos are not checked
- That a non-blocking connect does not return `EINPROGRESS` is confirmed only on Linux and macOS
