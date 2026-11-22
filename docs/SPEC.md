# sockat specification

> English | [日本語](./SPEC-ja.md)

How sockat behaves, independent of the language (the promise to users and to those who write each language's README). Every implementation follows it.

- How the routes are built (building the base B, each route's steps): [SPEC-routes.md](SPEC-routes.md)
- How far each condition reaches: [the reach table](../pages/reach/README.md)
- Decisions and rejected alternatives: [docs/decisions](decisions/INDEX.md) (Japanese; the current design is [DR-0017](decisions/DR-0017-resolve-through-persistent-base.md))
- What is specific to a language (types, runtime integration, memory safety): the README and manual of each language's repository ([sockat-rs](https://github.com/kawaz/sockat-rs), [sockat-py](https://github.com/kawaz/sockat-py), [sockat-go](https://github.com/kawaz/sockat-go), [sockat-ts](https://github.com/kawaz/sockat-ts))

## Terms

| Term | Meaning |
|---|---|
| standard library | the language's standard library bind / connect for Unix domain sockets |
| standard library length | the longest path the language's standard library accepts unchanged in a sockaddr that is not widened, never more than the sockaddr length (`sun_path` − 1). A path up to it is handed to the standard library unchanged. Usually `sun_path` − 1, `sun_path` − 2 for Java. Even if the standard library lets a longer path through by truncating it, widening the sockaddr or a detour of its own, that is not used (Node on macOS, Bun). A path of exactly `sun_path` with no room for the NUL is not used either, even if the standard library accepts it (108 for Node on Linux, etc.) ([DR-0004](decisions/DR-0004-standard-length-per-language.md), Japanese) |
| sockaddr length | the length of `sun_path` − 1 byte (leaving room for the NUL). The longest spelling a sockaddr that is not widened carries |
| original path | the path the user passed |
| directory / file name | what precedes the last component of the original path, and the last component. The socket's directory is the former |
| absolute candidate | an absolute path that points to the same place as the original path and does not depend on the cwd. There are the real-path candidate (the realpath of the socket's directory + the file name) and the `$PWD` candidate (the relative path joined to `$PWD` with `..` and `.` folded, checked to be the same directory as the original; only for a relative path) ([Making a relative path absolute](#making-a-relative-path-absolute)) |
| spelling | the path string handed to the kernel. The kernel remembers a bind's spelling and returns it from `getsockname` / `getpeername` |
| route | a way to build another spelling of the same place as the original path and bind / connect with it. The names are in "[Route names](#route-names)" |
| try | check whether a route can be used, and if so bind / connect with its spelling. If not, go on to the next route |
| unusable / failure | unusable: the route itself cannot be used (the spelling does not fit, the means is missing, B / D / E cannot be created). failure: the bind / connect was actually made and the OS returned an error ([How a failing route is treated](SPEC-routes.md#how-a-failing-route-is-treated)) |
| base | where B is created. One of `/tmp`, `$XDG_RUNTIME_DIR`, `$TMPDIR` and the socket's directory ([Where B is created](SPEC-routes.md#where-b-is-created)). Not used when the user gives B itself in `Options.base` |
| B | a real directory created in the base. One per user, reused across processes |
| D | a directory created in B, one per (process, B). Its name is 10 random characters |
| E | a symlink. One kind points to the socket's directory (link-dir and thread-cwd / at), the other to the socket file (link-file) |
| procB | spelling B as `/proc/<pid>/fd/<B's fd>`. Only processes of the same uid can follow it, and it cannot be followed after the process exits |
| real-path spelling | spelling B by its real path |
| resolve | turning a long path into a short spelling through B / D / E and returning it ([resolve](#resolve)) |
| spelling properties | whether the spelling of a bind or a resolve can be used later. Returned as `Spelling` ([Spelling properties: `Spelling`](#spelling-properties-spelling)). `Dangling` is a spelling that contains an E already removed, and reaches nothing |
| fails the checks | does not pass the owner and permission checks of a base, B or `Options.base` (a real directory, owned by oneself or root, not writable by others) |
| the connect variants | `connect`, `connect_nonblocking`, and the `_ex` of each |
| `/proc` usable | checked differently where it is used (against a mismatch between the PID namespace and the `/proc` mount).<br>Choosing the connect row (the proc-direct row or the relative row of [Connect order](#connect-order)): `/proc/self/fd/<fd>` stat'ed with an fd opened on `/` has the same `(st_dev, st_ino)` as `fstat` of that fd. Apart from this, proc-direct makes the same check with the socket's directory's fd of that connect, and is unusable when they differ ([proc-direct](SPEC-routes.md#proc-direct))<br>Using procB (including the estimate of the spelling's length): `/proc/<pid>/fd/<B's fd>` stat'ed has the same `(st_dev, st_ino)` as `fstat` of B's fd ([Spelling forms](SPEC-routes.md#spelling-forms)) |

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
- `sweep()` removes the dead D in the bases, and `sweep_base(path)` removes the dead D in the B of `Options.base` ([`sweep`](#sweep))
- There is no way for the user to choose or combine routes, and no function that changes a process-wide default
- Names follow each language's conventions. Python puts `_ex` in the submodule `sockat.ex` (to keep them apart from the standard library's `socket.connect_ex`). Go's stream functions are `Listen` / `ListenEx` / `Dial` / `DialEx`

### Functions

Shown with the Rust names.

| Type | Function | Returns |
|---|---|---|
| stream | `bind(path)` | a listening standard library listener |
| stream | `connect(path)` | a standard library stream |
| stream | `connect_nonblocking(path)` | a non-blocking standard library stream |
| stream | `bind_ex(path, Options)` | `Bound<UnixListener>` |
| stream | `connect_ex(path, Options)` | `Connected<UnixStream>` |
| stream | `connect_nonblocking_ex(path, Options)` | `Connected<UnixStream>` (the stream is non-blocking) |
| DGRAM | `datagram::bind(path)` | a `UnixDatagram` of the standard library |
| DGRAM | `datagram::unbound()` | a `UnixDatagram` of the standard library |
| DGRAM | `datagram::connect(&sock, path)` | nothing |
| DGRAM | `datagram::send_to(&sock, buf, path)` | the number of bytes sent (its routes are in "[Open questions](#open-questions)") |
| DGRAM | `datagram::bind_ex(path, Options)` | `Bound<UnixDatagram>` |
| DGRAM | `datagram::connect_ex(&sock, path, Options)` | `Report` |
| DGRAM | `datagram::send_to_ex(&sock, buf, path, Options)` | the number of bytes sent and `Report` (its routes are in "[Open questions](#open-questions)") |
| SEQPACKET | `seqpacket::bind(path)`, `connect(path)`, `connect_nonblocking(path)` and each `_ex` | open |
| resolve | `resolve_for_bind(path, Options)` | `ForBind` |
| resolve | `resolve_for_connect(path, Options)` | `ForConnect` |
| base | `sweep()` | nothing |
| base | `sweep_base(path)` | nothing |

- On failure, the default operations return the standard library's error type; `_ex` and resolve return an error type that carries diagnostics ([Diagnostics](#diagnostics))
- For DGRAM, only the functions of the standard library's `UnixDatagram` that take a path, and `unbound` used with them, are mirrored. `pair` is not
- A DGRAM connect tries the routes in the same order as a stream connect ([Connect order](#connect-order)). The routes of `send_to` are in "[Open questions](#open-questions)"
- Go's DGRAM connect is `DialUnixgram(path)` (creating the socket and connecting in one call; Go's standard library form). Those who want to connect a bound socket to a long path make the spelling with resolve and hand it to the standard library

### `Options`

| Field | What it is |
|---|---|
| `usable_cross_uid: bool` | asks for a spelling that a peer of another uid can also follow. Only the bind side (`bind_ex`, `resolve_for_bind`) looks at it; the connect side (`connect_ex` etc., `resolve_for_connect`) does not (a connect's spelling does not stay with the peer). It affects how B is chosen and keeps procB from being used. When it cannot be met, thread-cwd / at is used ([Another uid and PrivateTmp](SPEC-routes.md#another-uid-and-privatetmp)). Whether it was met is told by the resulting `Spelling` |
| `base: Option<Path>` | the user gives the path of B itself (an app passes a place it manages, e.g. `/tmp/app-<uid>/sockat`). B is created there; when the checks fail it is an error, and it does not fall back to the automatic bases ([Errors](#errors)). On the bind side together with `usable_cross_uid`, it is also checked that every directory on the way to that base and the base itself give x to other. The connect side also uses it as the base for B. Passing a different `base` per call makes one process hold several B. The spelling form is chosen in the same order as in the automatic case. This B is sockat's own, and the user puts nothing else there (`sweep_base` covers only the directories named in the form of a D) |

### What is returned

| Type | Contents |
|---|---|
| `Bound<S>` | `socket` (the standard library's type), `file: SocketFile` (`remove()`, `cleanup()`), `spelling: Spelling`, diagnostics (`route`, `base`, `skipped`) |
| `Connected<S>` | `socket` (the standard library's type), diagnostics (`route`, `skipped`) |
| `Report` | diagnostics (`route`, `skipped`) |
| `ForBind` | `path` (the spelling), `spelling`, `cleanup()`, `socket_file()` (a call made after the bind that receives a `SocketFile`; [`SocketFile` of `ForBind`](#socketfile-of-forbind)), diagnostics. It has no `remove()` |
| `ForConnect` | `path` (the spelling), `spelling`, `cleanup()`, diagnostics (`route`, `skipped`). It has no call that receives a `SocketFile` (the type prevents removing by mistake) |

- `remove()` and `cleanup()` are in "[Cleanup](#cleanup)"
- The connect variants (`Connected`, `Report`) do not return the spelling's properties (a connect's spelling does not stay with the peer and is used only within that call). `ForConnect` does return them (the user may keep a resolved spelling and use it for a long time; [Spelling properties: `Spelling`](#spelling-properties-spelling))
- There is no bool for "was it handed to the standard library unchanged" (`spelling == Original` or `route == "standard"` tells)
- Field and type names follow each language's conventions

### Non-blocking connect

- The socket is made non-blocking before connecting and returned that way. When the peer's backlog is full it fails without waiting
- `EINPROGRESS` is returned as an error and the socket is closed
- Cleanup does not wait (an E the default connect created for link-file is only unlinked)
- A language whose standard library's connect never blocks (Node.js, Go, etc.) provides one connect in the standard library's own form and no separate `_nonblocking`. The same for the `connect_ex` variants ([DR-0003](decisions/DR-0003-single-connect-when-standard-never-blocks.md), Japanese). Go's `Dial` / `DialEx`, like the standard library's `net.DialUnix`, never wait (when the backlog is full, Linux gives `EAGAIN` at once and macOS `ECONNREFUSED`)

### Same as the standard library

- The listener / stream / datagram returned is of the same type the standard library returns, so it is a drop-in replacement for the standard library
- A socket the implementation creates itself gets the same settings as one the language's standard library creates (close-on-exec, `SO_NOSIGPIPE`, the listen backlog, etc.). There is no way to specify the backlog
- Whether closing a standard library listener removes the socket file is left to the standard library's own mechanism (the differences for a long path are in "[What differs from the standard library for a long path](#what-differs-from-the-standard-library-for-a-long-path)"). The listener of `bind_ex` does not remove the file when closed, even for a short path; only `remove()` removes it

### Diagnostics

On success `_ex` and resolve return the following.

| Field | What it is |
|---|---|
| `route` | the name of the route taken |
| `base` | the spelling of the B a bind used (`proc`, `sockdir`, `runtime`, `tmpdir`, `tmp`, `given`; what the values mean is in [Spelling forms](SPEC-routes.md#spelling-forms)). It has a value only when the spelling goes through B (link-dir, link-file), and none otherwise (standard, thread-cwd, at). `Connected`, `Report` and `ForConnect` have none |
| `skipped` | the routes tried and found unusable, in the order tried. Each element is `{ name: the route name, reason: why it was unusable }`. When it goes on to the routes (a path over the standard library length, and a relative path whose absolute candidates do not fit) `standard` is included |

- `skipped` has one element per route name. Trying link-dir with procB and with the real path is still one element, with the `reason` of the last try. Not using procB because of `usable_cross_uid` is not skipping a route, so nothing is added
- When a call skips a base among 1 to 3 because the B with the default name already exists there and fails the checks (occupied), the occupation is added to the `reason` why a route that uses B could not be used (the spelling does not fit, etc.) ([Building B](SPEC-routes.md#building-b)). It does not appear in calls after an earlier call has come to hold the B in the next base
- `skipped` contains only the routes in that call's row of the order tables (for bind the row is decided by the OS, for connect by the OS and whether `/proc` is usable). The connect row of Linux without `/proc` usable has no proc-direct, so it is not included.  A route whose means the OS lacks (thread-cwd on NetBSD, OpenBSD and illumos, thread-cwd-direct on an OS that cannot move a thread's cwd) is not in that OS's row and is not included

- Every route tried before `route` was unusable (when a route actually binds / connects and fails, the error is returned there and the next is not tried; only when a bind's link-file is told apart at run time does it go on). So there is no "was it usable" bool
- The names in `route`, `base` and `skipped` and the `reason` are for diagnostics and promise nothing about their content (routes are added and changed). Branch on `Spelling`
- Route names are the same ASCII in Japanese and English
- When `_ex` fails, the error carries `skipped` too. When a route actually bound / connected and failed, its name (`route`) is attached as well (none for `ENAMETOOLONG`, where none could be used)
- How they are attached follows each language's conventions. The errno of an OS error stays readable (Rust gives `skipped` to an error type holding the errno, Go an error type whose `Unwrap` reaches the errno, Python an attribute of the exception, etc.)

## resolve

It turns a long path into a short spelling that keeps pointing to the same place as the original path and returns it. While the spelling lives, upper libraries that remove by the `getsockname` spelling, DGRAM replies and operational tools work as with the original path. The spelling is just a path, so the user can hand it to the standard library whatever the socket type (stream / DGRAM / SEQPACKET) and operation (bind / connect / `send_to`). A returned spelling may be used later after the cwd has changed, so a relative path is made absolute before it is handled ([Making a relative path absolute](#making-a-relative-path-absolute)).

| | `resolve_for_bind` | `resolve_for_connect` |
|---|---|---|
| Spelling | `B/D/E/<file name>` (link-dir) first, then `B/D/E` (link-file) | `B/D/E` (link-file), whatever the file name's length |
| Where link-file is used | only on the OSes measured to follow a symlink on bind (macOS, NetBSD). On OSes not yet checked, link-dir only (resolve does not bind, so whether bind follows cannot be told) | every OS (connect always follows a symlink in the last component) |
| Returns | `ForBind` (`spelling`, `cleanup()`, `socket_file()`) | `ForConnect` (`spelling`, `cleanup()`) |
| When it cannot | `ENAMETOOLONG` (a length only thread-cwd / at reaches) | `ENAMETOOLONG` (link-file cannot be used, e.g. B cannot be created) |

- An absolute path up to the standard library length is returned unchanged (`Original`)
- For a relative path and an absolute path over the standard library length, an absolute candidate that fits is returned when there is one (`Original`; nothing is created in the base)
- For a relative path where none of the spellings above can be used, the original relative path is returned unchanged if it is up to the standard library length (`CwdRelative`); if it is longer, `ENAMETOOLONG`
- resolve only returns a spelling, so those who want the `ENAMETOOLONG` cases reached too use `bind` / `connect`. The default `bind` can try thread-cwd / at, and the default `connect` the routes needing no write and thread-cwd-direct
- resolve spells B as procB or the real path, chosen as for the default bind ([Spelling forms](SPEC-routes.md#spelling-forms))
- resolve does not list B on each call (so as not to add steps to resolve)
- To connect to the same path repeatedly, use the spelling made once by `resolve_for_connect` for every connect and `cleanup` at the end
- The default `bind` uses resolve internally and reaches lengths resolve cannot with thread-cwd / at. The default `connect` creates no D ([Connect order](#connect-order)). The default bind keeps its spelling; the default connect does not

## Spelling properties: `Spelling`

Whether the spelling of a bind or a resolve can be used later is returned as one value (`spelling` of `Bound`, `ForBind` and `ForConnect`).

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
| `Original` | the original absolute path, or an absolute candidate (independent of the cwd) | standard |
| `CwdRelative` | the original relative path. It points elsewhere after the cwd changes (a hazard the standard library already has, but it is reported). Only when no route could be used even with the relative path made absolute (5 of [Making a relative path absolute](#making-a-relative-path-absolute)) | standard |
| `Linked` | goes through B / D / E and points to the same place as the original path | link-dir, link-file |
| `Dangling` | contains an E already cleaned up. Reaches nothing | thread-cwd, at |

Attributes of `Linked`:

| Attribute | What it is | Value |
|---|---|---|
| `removable` | whether unlinking by the spelling removes the real file | true for link-dir (the E in the middle is followed). false for link-file (the last symlink is not followed and E is removed; removing the file needs `remove`) |
| `until` | until when the spelling can be followed | `Process` (procB: not after the process exits). `Cleanup` (real-path spelling: E stays until `cleanup`, D until the OS cleaning after the process exits) |
| `usable_cross_uid` | whether a peer of another uid can follow it | false for procB (same uid and same PID namespace only; root can follow). For a real-path spelling, true when every directory on the way to B and B itself give x to other (B in `/tmp`), otherwise false (`/run/user/<uid>` and macOS's `$TMPDIR` are 0700, and so is an existing B that is 0700) |
| `usable_with_private_tmp` | whether the peer can follow it even when either side has its `/tmp` isolated (systemd's `PrivateTmp`, etc.) | always true for a procB spelling (the spelling does not pass through `/tmp`). For a spelling with B's real path, false when either the path of B's base before realpath or the spelling (the real path) passes through `/tmp` or `/var/tmp` (B in macOS's `/tmp` is false even though its spelling is `/private/tmp`), true when neither does. "Passes through" means that, component by component, it is `/tmp` or `/var/tmp`, or is under the realpath of either. A peer in a wholly different mount namespace (a container, etc.) is not covered |

- The connect variants (`connect_ex` etc.) do not return the spelling's properties (a connect's spelling does not stay with the peer and is used only within that call). `resolve_for_connect` does return them. The user may keep the returned spelling and use it for a long time, so it tells that a spelling left relative cannot be used after the cwd changes (`CwdRelative`) and that a procB spelling can be followed only while the process lives (`until`) ([DR-0019](decisions/DR-0019-absolutize-relative-path-on-bind.md), Japanese)
- The `spelling` of `ForConnect` is one of `Original`, `CwdRelative` and `Linked` (a link-file spelling; `removable` is false). The attributes of `Linked` have the same definitions as for a bind's spelling and tell the actual properties of the spelling (`resolve_for_connect` does not look at `Options.usable_cross_uid`, so it does not choose a B that meets `usable_cross_uid`)

## Cleanup

### `remove` and `cleanup`

| Call | What it does | Held by |
|---|---|---|
| `remove()` | removes the bound socket file once, and does `cleanup` too | `SocketFile` (the one of `Bound`, and the one `socket_file()` of `ForBind` returns) |
| `cleanup()` | cleans up resolve's E once | `SocketFile`, `ForBind`, `ForConnect` |

- Neither happens automatically (Rust's Drop does not do them either). A call after one that succeeded does nothing (`remove` is idempotent in the sense that it removes what the resolved spelling points to once). A call after one that failed tries again (remembering the failure and returning it forever would leave no way to clean up). Even when called concurrently, only one removal runs at a time
- `cleanup()` returns a failure to unlink E (other than `ENOENT`) as an error (it reports the result of the cleanup the user asked for). Only the cleanup of E inside a call stays silent ([How a failing route is treated](SPEC-routes.md#how-a-failing-route-is-treated)). `remove()` returns the error of removing the file first, and otherwise the error of `cleanup` (a language whose convention is to join both into one error may join them: Go's `errors.Join`)
- sockat does not clean up B and D ([What stays in the base](#what-stays-in-the-base))
- Do not use a spelling after it is cleaned up. When B is in `/tmp`, after B is gone someone else can recreate the same name (as with the standard library: after the original path is removed, anyone who can write to that directory can recreate it)

### `remove`

- `remove` only removes the file and does not close the listener. The user closes it
- It remembers the realpath and `(st_dev, st_ino)` of the bound socket file and removes it only when that path still has the same `(st_dev, st_ino)`
  - It remembers them right after the bind succeeds (before returning the listener). If they cannot be remembered, it closes the listener, cleans up the E it made, leaves the socket file, and returns an error (it does not hand back a `remove()` that cannot remove anything as a success; nothing could be checked, so removing could remove a replaced file)
  - When the spelling is `CwdRelative` (no route could be used and the relative path was handed to the standard library as is), compare the process's cwd `(st_dev, st_ino)` before anything about the path is looked up and after both the bind and the realpath taken for remembering; if they differ, treat it like the case where they cannot be remembered (so that a cwd change in between does not make it remember and remove an unrelated file under the old cwd. A change and change back is not seen). When the relative path was made absolute and bound, the realpath remembered does not depend on the cwd, so this comparison is not made
  - After the bind, when the last element of the original path is a symlink (on macOS and NetBSD the standard library's bind follows a last symlink and creates the socket at its target), it remembers the realpath and `(st_dev, st_ino)` of what it led to (so that `remove` does not remove the user's symlink). Whether or not the last element is a symlink, when what it would remember is not a socket, it is treated like the case where they cannot be remembered (`bind_ex` closes the listener, cleans up the E and returns an error; remembering what replaced the file right after the bind would make `remove` remove that)
  - Where to remember: link-dir, thread-cwd and at remember the real directory the route created the socket in (the realpath E points to, the D moved to) with the file name (the original path is not resolved again, so that what was created is remembered even if a symlink on the way is switched between building the route and after the bind). standard resolves, after the bind, the realpath of the spelling handed to the standard library (the original path or an absolute candidate). link-file resolves, after the bind, the realpath of what E points to (the original path, with the cwd prepended for a relative path)
  - The path argument is turned into a string once at the entry, and that value is used for remembering, binding and returning alike
- It succeeds when the file is already gone and when it has been replaced by another file and is left alone. It fails when the check cannot be made (`lstat` fails with something other than `ENOENT` / `ENOTDIR`) and when the removal itself fails
- Even when it fails, it goes on to `cleanup`, and returns the error of removing the file
- A replacement is told apart by `(st_dev, st_ino)` only, and what is promised is a replacement while the listener is open. Something removed and recreated after the listener is closed cannot be told apart on a filesystem that reuses numbers at once (ext4, BSD UFS / FFS). Each language's docs recommend calling `remove` before closing the listener ([findings](findings/2026-11-19-inode-reuse-after-close.md), Japanese)
- Someone who can write to the socket's directory or a directory on the way swapping the file or a directory (renaming a real directory on the way and putting a symlink in its place, etc.) between the check and the removal, or between the bind and the remembering, cannot be prevented (POSIX has no way to remove by inode)
- For a bind to an abstract name (a path starting with NUL on Linux / Android), `SocketFile` holds no file and `remove()` removes no file (it only does what `cleanup` does). `socket_file()` of `ForBind` returns the same form

| Language | Form |
|---|---|
| Rust | `remove` of `SocketFile` |
| Python | the return value includes a function without arguments |
| Go | the methods `Remove()` / `Cleanup()` of `*SocketFile`. The listener of `ListenEx` does not remove the file when closed, even for a short path; only this removes it (`SetUnlinkOnClose(false)`) |

### `SocketFile` of `ForBind`

At resolve time nothing is bound, so `ForBind` cannot remember the socket file's `(st_dev, st_ino)` and has no `remove()`. When the user calls `socket_file()` after binding on their own (the name follows each language's convention; in Rust `socket_file(&self) -> io::Result<SocketFile>`), it returns a `SocketFile`. Without that call there is nothing that removes the file.

- At the call it follows the spelling all the way, including a symlink at the last element of the original path (the standard library's bind follows it on macOS and NetBSD), and remembers the realpath and `(st_dev, st_ino)` of the socket file it ends at (so that `remove` does not remove the user's symlink). When it cannot follow it (before the bind, no file), it is an error. When what it ends at is not a socket (an unrelated file that was at the original path before the bind, etc.), it is an error
- The returned `SocketFile` works like the one of `Bound` ([`remove`](#remove)). Its `cleanup()` cleans up once the same E as `cleanup()` of `ForBind`
- Call it after the bind and before closing the listener. A replacement between the bind and the call cannot be told apart
- When the spelling is `CwdRelative` (no spelling could be used and the relative path was returned as is), the process cwd's `(st_dev, st_ino)` at resolve time and at the call are compared, and a difference is an error

### What stays in the base

| | B | D | E |
|---|---|---|---|
| Unit | one per user, reused across processes. A process uses one B in bases 1 to 3 (`/tmp`, `$XDG_RUNTIME_DIR`, `$TMPDIR`) (one more only with `usable_cross_uid`). A B in the socket's directory is one per directory. A B in `Options.base` is one per given path | one per (process, B). Created only by a bind that keeps its spelling (including thread-cwd / at) and by `resolve_for_connect` | one per resolve. The default bind's link-dir reuses one per (D, realpath of the socket's directory). One per call for thread-cwd / at and for the default connect's link-file |
| While alive | not removed | the process keeps an fd holding a flock (shared lock) | resolve's E is not removed |
| Cleanup | not by sockat (B in `Options.base` is managed by the app) | not by sockat. A dead process's D is removed by the OS's temporary-directory cleaning. Only when `sweep()` is called are the D whose lock has been released removed | resolve's E by `cleanup`. A per-call E is unlinked within the call |

- The default `bind` returns no `SocketFile`, so its E stays until the process exits and is removed with D by the OS's temporary-directory cleaning. There is no mechanism for cleaning up after a process that execs. Users who care about cleanup use `_ex` or resolve
- The default `bind` reuses the link-dir E for binds to the same directory, so the E grow only with the number of socket directories. A link-file E is one per bind
- The default `connect` leaves no D or E in the process (it creates no D, and unlinks the E right under B right after the connect). When it creates B for the first time, that B and its fd are used as the process's B from then on
- A B in the socket's directory (`.sockat.<random>`) is not covered by `sweep`, may not be removed by the OS's cleaning either, and stays in the user's directory
- A long-lived process that keeps creating and removing socket directories where bases 1 to 3 cannot be used accumulates the fds of each directory's B and D, so it passes a fixed `Options.base`

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
- `sweep()` covers the B with the default names in bases 1 to 3 (`sockat-<uid>`, `sockat`). Only those that exist; it creates no B
- `sweep_base(path)` (the name follows each language's convention) removes the dead D in the B passed as `Options.base`. The app that manages that B calls it. When B or its parent is missing, it does nothing and succeeds. The path is checked as for `Options.base` (a wrong form is an invalid argument; a symlink, someone else's, or a B or directory on the way writable by others is `EPERM`; not a directory is `ENOTDIR`)
- `sweep()` silently skips the bases and B that fail the checks, and a B it cannot read (no permission, etc.)
- Inside B and D it lists by fd, and removes only after taking the exclusive lock and checking that the name's `(st_dev, st_ino)` is the same as the locked fd's
- It covers only the directories right under B whose name has the form of a D (10 characters of the 62 alphanumerics). B (including the B of `Options.base`) is sockat's own, and the user puts nothing else there
- A B in the socket's directory is not covered
- It does not touch the E right under B (the default connect's, and the ones the CLI's `resolve` places and reuses; [DR-0018](decisions/DR-0018-cli-resolve-with-reused-hashed-link.md)). A D containing something other than a symlink is left
- It is never called automatically (B is not listed on each resolve, at the start of a process, or at exit). Where tests run over and over, the user calls it

## Short paths

An absolute path up to the standard library length is handed to the standard library unchanged. Nothing is added and no environment variable is read. A longer path goes to the routes ([DR-0004](decisions/DR-0004-standard-length-per-language.md), Japanese). A relative path is made absolute before it is split by length for bind and resolve, and is split by length as it is for the connect variants and `send_to` ([Making a relative path absolute](#making-a-relative-path-absolute)).

- A path containing NUL anywhere but at the start is never handed to the standard library, whatever its length; it is an invalid-argument error ([DR-0006](decisions/DR-0006-nul-is-invalid-at-any-length.md), Japanese)
- An empty path is an invalid-argument error
- Among the spellings handed to the standard library as relative ones, one the standard library does not read as a path (Node's node:net takes a string that reads as a number to be a TCP port; Go's standard library on illumos rewrites a leading `@` into an abstract name) is handed to the standard library with `./` in front, which names the same file. A relative path is handed as it is for the connect variants and `send_to`, and for bind and resolve in case 5 of [Making a relative path absolute](#making-a-relative-path-absolute). The same goes for the relative spelling of a route (relative). For bind and resolve, `Spelling` stays `CwdRelative`
- On Linux / Android a path starting with NUL (abstract namespace) is out of scope and is handed to the standard library unchanged, whatever its length. A language's own abstract notation (Go's `@` etc.) likewise. The `Spelling` of `_ex` and resolve is `Original`
- On OSes without an abstract namespace, a path starting with NUL is an invalid argument too, whatever its length
- In a language whose standard library has no non-blocking connect, a non-blocking connect alone uses the implementation's own socket, connected to the same address as the standard library would
- When the standard library does not accept a route's spelling (a language whose standard library length is shorter than the sockaddr length), the implementation's own socket is used with the same address too

| OS | sockaddr length |
|---|---|
| Linux / Android / illumos | 107 bytes |
| Apple OSes / FreeBSD / NetBSD / OpenBSD | 103 bytes |

## Making a relative path absolute

When bound with a relative path, the spelling the kernel remembers is relative too, and once the cwd changes it points elsewhere (a standard library that unlinks by the address's spelling on close, a standard library that unlinks the given path in the cwd at the time of the close, and DGRAM replies then hit somewhere else or do not arrive). The operations whose spelling stays make a relative path absolute with the cwd before handling it ([DR-0019](decisions/DR-0019-absolutize-relative-path-on-bind.md), Japanese).

| Operation | On receiving a relative path |
|---|---|
| bind (`bind`, `bind_ex`, `datagram::bind`, `datagram::bind_ex`) | make it absolute before handling it |
| resolve (`resolve_for_bind`, `resolve_for_connect`) | make it absolute before handling it (the returned spelling may be used later after the cwd has changed) |
| the connect variants (`connect`, `connect_nonblocking`, `datagram::connect` and each `_ex`), and the destination of a send (`datagram::send_to` and its `_ex`) | leave it as it is (the spelling does not stay with the peer, and after connecting or sending a change of the cwd does not matter. Handed as relative, nothing is created in the base) |

The steps of bind and resolve:

1. The form of the arguments (an empty path, NUL, the form of `Options.base`) is checked first. An abstract name is out of scope (handed to the standard library unchanged, whatever its length)
2. For a relative path, build two absolute candidates ([Building the absolute candidates in SPEC-routes](SPEC-routes.md#building-the-absolute-candidates))
   - the real-path candidate: the socket's directory made a real path with realpath (following symlinks), with the file name appended
   - the `$PWD` candidate: only when `$PWD` is the same thing as `.`, the relative path joined to it as a string with `..` and `.` folded lexically, checked by `(st_dev, st_ino)` that the folded directory is the same thing as the original directory
3. When a candidate is up to the standard library length, hand it to the standard library (the real-path candidate is looked at first). `route` is `standard` and `Spelling` is `Original`. Nothing is created in the base
4. When neither fits or can be built, go on to [the routes for long paths](#routes-for-long-paths-and-their-order)
5. When no route can be used in 4, go on with the original relative path. If it is up to the standard library length, hand it to the standard library as relative (`Spelling` is `CwdRelative`). If it is longer, `ENAMETOOLONG` (the routes for long paths are the same as those tried in 4). This keeps every place the standard library reaches reachable

- For an absolute path over the standard library length too, the real-path candidate is looked at before going on to the routes, and when it fits it is handed to the standard library (`route` is `standard`, `Spelling` is `Original`). No `$PWD` candidate is built for an absolute path
- Two candidates are looked at to widen the cases where the path can be handed to the standard library unchanged (sometimes the real path is shorter, sometimes the `$PWD` candidate is). When one fits, nothing needs to be created in the base. They do not compete in shortness (fitting is enough)
- It falls to 5 only when the routes themselves are unusable. When a bind is actually made with an absolute candidate or a route and fails (`EADDRINUSE`, `ENOENT`, etc.), that error is returned and neither the other candidate nor the original relative path is tried again (so as not to try the same failure twice or create something somewhere else)
- What changes is whether the spelling the kernel remembers is relative or absolute; where the socket file is created does not change
- `CwdRelative` is returned only in case 5. When the cwd is very deep (its absolute path is over PATH_MAX: 4096 on Linux, 1024 on macOS), neither the real-path candidate nor the `$PWD` candidate can be built or fits, and it goes on to 4 or 5
- A spelling that is absolute but depends on the cwd, such as `/proc/self/cwd/…`, is not touched (only relative paths are covered)
- A relative path up to the standard library length that does not end in a name (`dir/`, `..`, etc.) is not made absolute; it is handed to the standard library as relative (there is no file name, so no candidate can be made; the error the standard library returns is returned as is). resolve does not call the standard library, so it returns the path as is with `CwdRelative` (the error comes from the standard library when the user hands that spelling to it)
- For a relative path, when the socket's directory exists but its realpath cannot be taken because of the path length (the cwd is over PATH_MAX, etc.; the errno differs by OS and by how the real path is taken (libc's realpath or the language's own implementation). Measured 2026-11-22: libc's realpath gives `ERANGE` on macOS; Go's `Getwd` + `EvalSymlinks` gives `ENAMETOOLONG` on Linux, `EINVAL` on macOS and `ENOMEM` on FreeBSD; glibc's realpath on Linux and Python's `os.path.realpath` succeed and return a real path over PATH_MAX, so when a `stat` of that real path gives `ENAMETOOLONG` it is treated the same, as not taken. Each implementation judges in one place the errnos that the path length causes in its language and OS), that is not an error: the routes are treated as unusable and it goes on to 5. No route has been tried at that point, so `skipped` is empty (when the original relative path is up to the standard library length, `route` is `standard` with `CwdRelative`; when over, `ENAMETOOLONG` with no `route`). Any other failure (`ENOENT`, `ENOTDIR`, `EACCES`, etc.) is returned as that error
- The diagnostics when the path is handed to the standard library as relative in 5: `route` is `standard`, and `skipped` holds only the routes that were unusable in 4, without `standard` (it is the route that went through in the end). That it was handed over as relative shows in `Spelling` being `CwdRelative`
- When the cwd is over PATH_MAX and the path is handed to the standard library as relative in 5, only the default bind reaches. `bind_ex` cannot take the real path of the bound socket file to remember it, so it returns an error (the same as "when it cannot be remembered" under [`remove`](#remove))
- When an absolute candidate is handed to the standard library, `Options.base` is not checked (B is not used; the same as an absolute path up to the standard library length, where base is not looked at). When no candidate fits and it goes on to the routes, base is checked as before and a failure is returned as that error (even for a relative path it does not fall to 5; a base error is not "the routes are unusable")
- A language that replaces what returns the address (Python, TypeScript) returns the given path when it was absolute, also when the real-path candidate was handed to the standard library
- A language that replaces what returns the address (Python, TypeScript) returns, after a bind with a relative path, not the given relative string but the absolute form (the candidate when a candidate was handed to the standard library; when it went on to the routes, the form of the real-path candidate, or of the `$PWD` candidate when that cannot be made). It returns the given relative path only in the case of 5
- What differs from the standard library (the address the kernel returns becomes absolute, a deep cwd creates things in the base even for a short relative path, etc.) is in "[What differs from the standard library for a long path](#what-differs-from-the-standard-library-for-a-long-path)"

## Routes for long paths and their order

A path over the standard library length (for a relative path in bind and resolve, one whose absolute candidates do not fit; [Making a relative path absolute](#making-a-relative-path-absolute)) is tried on the routes in the order below and bound / connected on the first route that can be used. How each route is built is in [SPEC-routes.md](SPEC-routes.md#routes); how far it reaches is in [the reach table](../pages/reach/README.md).

- A path whose last component is not a file name (`dir/`, `dir/.`, `dir/..`, `..`) is an invalid-argument error, and nothing is created
- The socket's directory is looked up first. When it is missing, `ENOENT`; when it is not a directory, `ENOTDIR` (before the length is judged or B / D / E is created)
- In bind and resolve, for an absolute path over the standard library length, the real-path candidate is looked at after the socket's directory is looked up and before any route is tried. When it fits, it is handed to the standard library
- The routes never fold the path lexically (`..` and `.` are not removed on the string). The kernel takes `a/sym/..` to be the parent of the symlink's target, so the directory is looked up by the OS (open, realpath(3)). Only the `$PWD` candidate is folded lexically, and it is used only after the folded directory is checked to be the same thing as the original
- No route changes the calling process's cwd or the calling thread's cwd
- No fork (neither for bind nor for connect). The cases only a fork reached, and the fork technique, are in [fork-cwd](../pages/fork-cwd.md)

### Route names

A name is "means + what it is about". The suffix `-direct` is the form that passes the file name without going through E.

| Name | What it does | Operation |
|---|---|---|
| `standard` | hand the path to the standard library unchanged | bind, connect |
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
| 1 | `standard` | | the original absolute path, or an absolute candidate | the original absolute path is up to the standard library length, or a candidate fits | `Original` |
| 2 | `link-dir` | procB | `B/D/E/<file name>` | `/proc` is usable and it fits (not with `usable_cross_uid`) | `Linked` |
| 3 | `link-dir` | real path | same | it fits | `Linked` |
| 4 | `link-file` | real path | `B/D/E` | OSes whose bind follows a symlink in the last component | `Linked` |
| 5 | `thread-cwd` (`at` on FreeBSD) | | `E/<file name>` | Linux / Android, Apple OSes (`at` on FreeBSD) | `Dangling` |
| 6 | `standard` | | the original relative path | the original path is relative and up to the standard library length (5 of [Making a relative path absolute](#making-a-relative-path-absolute)) | `CwdRelative` |
| 7 | `ENAMETOOLONG` | | | | |

- The spelling is kept, so while it lives, upper libraries that remove by the `getsockname` spelling and DGRAM replies work as with the original path. thread-cwd / at come after, for when resolve's spelling does not fit
- link-file is not tried on the OSes measured not to follow a symlink on bind (Linux / Android, FreeBSD, OpenBSD, illumos). macOS and NetBSD follow it (measured 2026-11-19, [findings](findings/2026-11-19-bind-through-file-symlink.md), Japanese). On other OSes it is tried and whether it follows is told apart at run time
- bind does not use proc-direct, relative, widened or at-direct. Their spelling later hits an unrelated file (proc-direct, relative, at-direct), or the address is cut in the middle and breaks the reading side (widened)
- When no B meets `usable_cross_uid`, or its spelling does not fit, it goes to 5 rather than falling back to a spelling that does not meet it. The D then is created in the usual B that does not look at `usable_cross_uid` (in the order of bases 1 to 4)

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

- The connect variants do not make a relative path absolute ([Making a relative path absolute](#making-a-relative-path-absolute)). A relative path up to the standard library length is handed to the standard library as relative at 1
- A connect's spelling does not stay with the peer (the connecting socket is not bound), so no E is kept. A one-off connect from a CLI usually ends at 2, and reaches even in a sandbox with no writable base
- relative and widened sometimes reach farther than the routes through the base
- 3 can be used on Linux / Android and Apple OSes ([thread-cwd-direct](SPEC-routes.md#thread-cwd-direct))
- A DGRAM connect uses the same order

## What differs from the standard library for a long path

Bind and resolve make a relative path absolute ([Making a relative path absolute](#making-a-relative-path-absolute)), so even a short relative path differs from the standard library in some points (the rows "Relative path:" of the table).

| Point | What happens |
|---|---|
| Relative path: the address the kernel returns | after a bind with a relative path, even a short one, the address shown by `getsockname` on the bound side, `getpeername` on a side that connected to it, `ss`, `lsof`, etc. is not the given relative path but an absolute path (an absolute candidate or a route's spelling). Code comparing the address string with the given relative path no longer matches |
| Relative path: a deep cwd | a relative path that is over the standard library length once made absolute goes to the routes even when it is short enough for the standard library to create nothing, and B / D / E are created in the base |
| Relative path: a cwd change after the candidates are built | when the cwd changes between building the absolute candidates and the bind, the socket is created under the cwd at the time the candidates were built (the standard library's bind with a relative path uses the cwd at the time of the bind) |
| The address the kernel returns | `getsockname` on the bound side, and `getpeername` on a side that connected to it, return the bind's spelling, not the original path. Whether it can be used later is told by `Spelling`. A language that can replace, within the standard library's type, what returns the address (Python, TypeScript) returns the original path. On illumos, the connecting side's `getpeername` returns the spelling passed to connect rather than the one bound (measured in sockat-rs's CI, 2026-11-19) |
| How it looks in operational tools | the address shown by `ss -x`, `lsof`, `/proc/net/unix`, etc. is the bind's spelling. For link-dir and thread-cwd / at the file name stays at the end of the spelling. A link-file spelling does not show the file name |
| When the listener is closed | the default bind (Go's `Listen`, etc.) behaves as the standard library does. With a standard library that unlinks by the address's spelling on close (Go's `UnixListener.Close`), a link-dir spelling follows the E in the middle and removes the file at the original path (same as the standard library). With a link-file spelling the unlink does not follow the last symlink, so E itself is removed and the socket file stays (differs from the standard library; each language's README says so). A `Dangling` spelling is not unlinked (Go uses `SetUnlinkOnClose(false)`). The bind of `_ex` does not remove anything on close, whatever the spelling; only `remove()` of `SocketFile` removes the file (removing by the spelling would remove a replaced file without telling it apart) |
| The directory is looked up first | link-dir's and thread-cwd / at's E point to the realpath of the socket's directory, and proc-direct, at-direct and thread-cwd-direct look up the directory before passing the file name. A rename or a symlink swap in between is not reflected |
| Another thread's chdir | relative gives a general error when the cwd changed in between and stayed changed. A change and change back is not seen |
| State grows outside the app's own place | B / D / E stay in `/tmp`, `$XDG_RUNTIME_DIR`, `$TMPDIR`. The default `bind`'s E and a dead process's D stay until the OS cleans them ([What stays in the base](#what-stays-in-the-base)) |
| Environments where a live D can be removed | Linux with systemd older than v242, and B in macOS's `$TMPDIR` ([What stays in the base](#what-stays-in-the-base)). The spelling only stops being followable |
| A peer with `PrivateTmp` | when the peer's `/tmp` is isolated, it cannot follow a spelling through `/tmp`. On Linux procB is used first, so this rarely happens. `usable_with_private_tmp` tells whether it can follow |

- NUL anywhere but at the start is an invalid argument even for a short path. A language whose standard library silently truncates at NUL (Go, etc.) says so under "differs from the standard library" in its reference

## Patterns not to use

Patterns that, when using sockat, remove an unrelated file or fail to remove the file. This section is the source for warnings to users; other sections and each language's docs point here. Each language's reference links to this section and gives only the concrete form in that language (e.g. Go's `os.Remove(l.Addr().String())`) and recommended code that avoids it (run as a test).

| Pattern | Why not | Instead |
|---|---|---|
| unlinking / stat-ing the socket file by the spelling the kernel returns (`getsockname`, the listener's address, etc.) without looking at `Spelling` | with a link-file spelling only E is removed and the file stays. A `Dangling` spelling reaches nothing | keep the original path and use it. `remove()` |
| using an old spelling after `cleanup` or after the process exits | after B in `/tmp` is cleaned up, someone else can recreate the same name. A procB spelling cannot be followed after the process exits | use a spelling only within `until` |
| binding with a relative path and removing it by the given relative path string after changing the cwd | it hits a file elsewhere (what sockat makes absolute is the spelling handed to the kernel; the string the user holds stays relative. With `CwdRelative` the kernel's spelling is relative too) | `remove()`. When making the path absolute yourself, do not use a function that folds `..` lexically (`a/sym/..` would become another directory) |
| relying on closing the listener to remove the socket file | for a long path it depends on the spelling and may not be removed ("[What differs from the standard library for a long path](#what-differs-from-the-standard-library-for-a-long-path)"). The listener of `bind_ex` never removes it on close | `remove()`, or remove by the original path |
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
| a socket file nobody listens on / nobody holds | `ECONNREFUSED` (a DGRAM connect gets `EDESTADDRREQ` on illumos; measured in sockat-go's CI 2026-11-21) |
| the backlog is full | Linux gives `EAGAIN` for a non-blocking connect (a blocking connect waits); macOS gives `ECONNREFUSED` |
| no route can be used (the spelling does not fit, the means is missing) | `ENAMETOOLONG` (in bind and resolve, a relative path up to the standard library length is handed to the standard library as relative) |
| `resolve_for_bind` at a length only thread-cwd / at reaches | `ENAMETOOLONG` |
| `resolve_for_connect` when link-file cannot be used (B cannot be created, the spelling does not fit) | `ENAMETOOLONG` |
| `Options.base` is a relative path, contains a NUL, or its last component is not a file name (`dir/`, `..`, `/`). Regardless of the path's length, and checked before telling whether it is an abstract name (a check of the argument's form, like a NUL not at the start) | invalid argument |
| `Options.base` is a symlink | `EPERM` (not a real directory; the check fails) |
| `Options.base` is neither a directory nor a symlink | `ENOTDIR` |
| a directory on the way to `Options.base` is missing | `ENOENT` |
| `Options.base` failed the owner / permission checks (including, on the bind side with `usable_cross_uid`, whether every directory on the way and the base itself give x to other) | `EPERM` |
| a path over the standard library length that does not end in a name | invalid argument |
| a path containing NUL anywhere but at the start (whatever its length) | invalid argument |
| an empty path | invalid argument (after the form check of `Options.base`, before the abstract check. Linux's standard library turns a bind of an empty path into an autobind to a nameless abstract address) |
| the cwd changed during relative | general error |

- The directory is looked up first, so `ENOENT` and `ENOTDIR` are decided before the length on every OS
- In bind and resolve, when the socket's directory of a relative path is missing, it is `ENOENT` even for a short path, as for a long path (`route` is none). No absolute candidate can be built, so it goes on to the routes and is decided where the socket's directory is looked up
- An `Options.base` error does not fall back to the automatic bases
- OS errors are returned in a form from which the errno can be read in that language's way
- An error the OS returns is returned unchanged, so the errno can differ by OS. Tests do not hard-code the errno; they compare with the errno the standard library returns for the same operation on a short path on the same OS
- When the standard library itself turns an OS error into another errno (Node's listen returns `EACCES` for a missing directory, etc.), a failure of a spelling handed to the standard library (a path up to the standard library length, an absolute candidate) gets the standard library's errno, and a path not handed to the standard library gets the errno of this table. Tests compare that errno with this table
- Which type represents "invalid argument" and "general error" is up to each implementation

## What each implementation must do

- Follow the routes and order of this specification ([SPEC-routes.md](SPEC-routes.md)). A route that cannot be built in the language is skipped (treated as unusable and the next is tried, and put into `_ex`'s `skipped` with the reason), and the reference states it in an OS × route table
- Provide the test CLI of the language-independent conformance test ([docs/design/conformance.md](design/conformance.md), Japanese)
- In a language that adopts its own socket into the standard library's type, check that adopting a socket connected via widened, and reading its address, do not crash. If they crash, skip widened as a route that cannot be built
- Routes are not exposed in the public API. Tests force each route by calling it directly from inside the package
- The parts that read the environment (the base candidates, where `/proc` is, whether Apple OSes accept a widened sockaddr, whether the thread cwd can be used) can be replaced from tests
- The reference links to this specification (from the README it is reached through "How it works" at the end). Before adding behavior that disagrees with it, fix this specification first
- The user-facing docs (each language's manual and reference) do not copy what is common to all languages; they link to the sections of this specification and pages: "[What differs from the standard library for a long path](#what-differs-from-the-standard-library-for-a-long-path)", "[Patterns not to use](#patterns-not-to-use)", "[What stays in the base](#what-stays-in-the-base)", "[`sweep`](#sweep)". A language's docs hold only the names and types in that language, the concrete forms and recommended code in that language, and the caveats specific to that language (bugs and limits of its standard library or runtime). Each specific caveat gets one line in the hub's [per-language caveats](../pages/langs.md)
- The opening of each language's README (who it is for, the error that language's standard library gives, the before / after in that language, installation) is written with that language's own examples, not replaced by a link. What is not copied is the explanation beyond it
- Each language's docs use the same paths (so the hub can link to them): the top of the manual `docs/MANUAL-ja.md` / `docs/MANUAL.md` (only the list of what you want to do, in the order bind, connect, DGRAM, SEQPACKET, resolve), usage by situation `docs/manual/bind-ja.md`, `connect-ja.md`, `datagram-ja.md`, `seqpacket-ja.md`, `resolve-ja.md` and the English `.md` (a heading per situation and typical sample code; what the language lacks is left out; SEQPACKET has no dedicated functions, so its page is only a short pointer with a link to the resolve page. The pointer says which resolve to use: `resolve_for_bind` for the side that listens (binds), `resolve_for_connect` for the side that connects), and the reference `docs/REFERENCE-ja.md` / `docs/REFERENCE.md` (what is not usage: the list of functions and types, `Options`, `Spelling`, errors, patterns not to use, language-specific caveats, the OS × route table)

## What implementations test

| Aspect | What to check |
|---|---|
| The short-path boundary | a path exactly the standard library length goes to the standard library unchanged, and one byte longer goes to the routes (checking the boundary with the standard library itself) |
| Relative paths in bind and resolve | a short relative path goes to the standard library as an absolute candidate and is `Original`. With a cwd reached through a symlink, it goes to the standard library with whichever of the real-path candidate and the `$PWD` candidate fits. When `$PWD` differs from `.`, the `$PWD` candidate is not used. For a relative path with `..`, a candidate whose folded directory differs from the original (`a/sym/..`) is not used. A short relative path in a deep cwd goes to the routes. When no route can be used, it goes to the standard library as relative and is `CwdRelative`. When a bind with an absolute candidate fails, neither the other candidate nor the relative path is tried again. After a bind with a relative path, `remove()` removes the bound file even if the cwd has been changed |
| The real-path candidate of a long absolute path | a long absolute path that fits as a real path (through a symlink) goes to the standard library with nothing created in the base (`Original`) |
| Relative paths in the connect variants | a relative path is not made absolute, and when it is up to the standard library length it goes to the standard library as relative (nothing is created in the base) |
| The `spelling` of `ForConnect` | `Original` for an absolute path up to the standard library length and an absolute candidate, `Linked` for a link-file spelling (`removable` is false). `until` is `Process` for a procB spelling |
| Where the spelling lands | unlinking / stat-ing the spelling does not hit an unrelated file (a same-named file in the cwd, a same-named file in another directory whose fd number was made to be reused) |
| Checking B | a base that fails the checks on the way to B is not used. When the B with the default name in bases 1 to 3 already exists and fails the checks (occupied), nothing is created in that base and the next base is tried, and the `reason` when the routes that use B are unusable tells it was occupied. `Options.base` that fails is an error |
| Concurrency | many concurrent binds / connects do not conflict in creating B / D or in reusing the default bind's E |
| The default bind's E | repeated default binds to the same directory leave one link-dir E. After the reused E has been removed, a bind creates E again and goes through |
| `sweep` | it does not remove the D of other live processes |
| `cleanup` | no E remains after `cleanup` |
| The default connect | nothing remains right under B after the connect, and it does not wait |
| `remove` | the file is removed and the listener is not closed. If the file was replaced by another while the listener was open, it is not removed |
| `socket_file()` of `ForBind` | calling it before the bind is an error. `remove` of the `SocketFile` it returns after the bind does not remove a replaced file |
| thread-cwd / at | when forced, neither the process's cwd nor the calling thread's cwd changes and no E remains after the call. The socket is created at the original path and can send and receive |
| link-file on bind | on an OS whose bind does not follow the symlink it goes into `skipped` and nothing remains. When something is at the original path, that error (`EADDRINUSE`) is returned and the next is not tried |
| The connect routes | forcing proc-direct, relative, widened, at-direct, thread-cwd-direct and link-file one by one reaches the socket |
| No retry on failure | `ENOENT` / `EADDRINUSE` / `ECONNREFUSED` are returned and nothing is created on later routes. When a bind by link-dir or link-file fails, no E made in that call is left (the default bind's link-dir E stays) |
| relative and the cwd | a cwd change during relative gives a general error |
| macOS | a 253-byte path reaches via widened for the connect variants. bind does not use widened |
| Non-blocking connect | it fails without waiting when the backlog is full |
| A path not ending in a name, NUL not at the start | an invalid argument with nothing created. NUL even for a short path. A path starting with NUL (abstract) goes to the standard library |
| The address the kernel returns | reading it does not crash even for a long path. In a language that can replace it, the listener, an accepted socket and a connected socket each return the original path, and the language's typical upper library (Python asyncio's `start_unix_server(sock=...)`, etc.) works as for a short path without extra arguments |

- Routes differ per OS, so run at least on macOS and Linux. Other Unix in CI VMs
- Tests that change process-wide settings, such as the cwd or signal handling, run in a child process

## Open questions

- Reach: a procB spelling takes about 35 bytes for `/proc/<pid>/fd/<fd>/` + D + `/E/`, and the file name reached on Linux is about 70. Between that and thread-cwd, thread-cwd is used
- `send_to` sends to resolve's spelling, so it does not use relative (a send cannot be taken back). What to do with a `send_to` at a length resolve cannot handle (send with thread-cwd, or `ENAMETOOLONG`)
- A reply to a DGRAM sender bound to a long path reaches while the spelling lives (procB for the same uid, the real path of B in `/tmp` for another uid too). How `Spelling` expresses the cases where it does not reach (after `cleanup`, procB with another uid)
- The return type of Rust's SEQPACKET
- Android and the Apple OSes other than macOS are not checked at all
- The peer credentials on NetBSD, OpenBSD and illumos are not checked
- That a non-blocking connect does not return `EINPROGRESS` is confirmed only on Linux and macOS
