# sockat specification: building the routes

> English | [日本語](./SPEC-routes-ja.md)

How the routes are built, for each language's implementers. The promise to users (operations, order tried, spelling properties, errors) is in [SPEC](SPEC.md), which is the source; this document describes how to build what meets it. Terms (B, D, E, base, procB, try, unusable, etc.) are in [the SPEC's Terms](SPEC.md#terms). Numbers are in bytes.

## Common

- How a directory is opened (the socket's directory, etc.): `O_SEARCH` on Apple OSes (`O_RDONLY` if the kernel answers `EISDIR` / `EINVAL`), `O_PATH | O_DIRECTORY` on Linux / Android, `O_RDONLY | O_DIRECTORY` elsewhere
- The socket's directory is looked up first with `stat`, and its realpath is taken. When it is missing, `ENOENT`; when it is not a directory, `ENOTDIR`; when the realpath cannot be taken, that error (all before the length is judged or B / D / E is created)
- Only the routes that need an fd of the socket's directory ([proc-direct](#proc-direct), [at-direct](#at-direct), [thread-cwd-direct](#thread-cwd-direct)) open it, and when it cannot be opened that route is unusable (`O_RDONLY` on other OSes cannot open a directory without read permission)
- The caller creates the socket. For a non-blocking connect the socket is made non-blocking before that. The listen after a bind is done by the caller
- No route changes the calling process's cwd or the calling thread's cwd

## Building B

The same steps for the automatic bases and for `Options.base`.

1. Make the base's path (the parent's path for `Options.base`) a real path with realpath (macOS's `/tmp` → `/private/tmp` etc.). The checks, opening and spelling below all use this real path
2. Check every directory from the root to the parent: each is owned by root or by oneself, and is either not writable by others or has the sticky bit (the owner of a sticky directory can still swap what is inside, so the owner condition is kept. the same idea as OpenSSH's StrictModes; if an ancestor is writable by others, the parent can be swapped out). Only once, the first time in the process
3. Open the parent with `O_DIRECTORY | O_NOFOLLOW`, hold it by fd, and create B with `mkdirat(parent fd, name, 0700)`
4. Right after creating it, set the mode with `fchmodat(parent fd, name, 0711)` (restoring what the umask took away; the parent has been checked and others cannot swap it), then open it with `O_DIRECTORY | O_NOFOLLOW` and check with `fstat` that it is a real directory owned by oneself. When the mode cannot be set or it cannot be opened, remove the empty directory one just created and go on to the next base (`Options.base` is an error)
5. On `EEXIST`, check what already exists in the same way (a real directory, owned by oneself, not writable by others). Use it even if its mode is not 0711, and do not change the mode. If it fails, an automatic base falls back to `sockat-<uid>.<10 random characters>`, and `Options.base` is an error

- "Not writable by others" includes the group (`mode & 022 == 0`)
- When a directory on the way is missing, sockat does not create it and returns an error (how a place the app manages is created is up to the app)
- The name is `sockat-<uid>` (`sockat` under `$XDG_RUNTIME_DIR`, `.sockat.<10 random characters>` under the socket's directory). `Options.base` is the path of B itself, and its last component is the name
- Errors for `Options.base`: an invalid argument when it is a relative path or its last component is not a file name (`dir/`, `..`, `/`), `ENOENT` when a directory on the way is missing, `ENOTDIR` when the base is not a directory, `EPERM` when the owner / permission checks fail
- The check of `Options.base` (the directories on the way, and B itself if it exists; nothing is created) is done for a long path after the socket's directory is looked up and before any route is tried, for both bind and connect. On failure `route` is none and `skipped` is empty. B is created only when a route that uses B is reached

### Where B is created

Where B's real directory is created and how B is spelled ([Spelling forms](#spelling-forms)) are separate axes. Per process, unless the user gives `Options.base`, B is the first of the following where it can be created (places where the OS's cleaning removes dead D and protects live D come first).

| Order | Base | Why |
|---|---|---|
| 1 | `/tmp` | Linux removes dead D after 10 days, and live D are protected by flock. macOS does not remove live D |
| 2 | `$XDG_RUNTIME_DIR` | no cleaning by age; dead D stay until logout |
| 3 | `$TMPDIR` | dirhelper may remove D in macOS's `$TMPDIR` after 3 days (live ones too) |
| 4 | the socket's directory | when it can be created in none of 1–3 |

- When `$TMPDIR` or `$XDG_RUNTIME_DIR` is empty or a relative path, that base is not used
- A process using one B applies to bases 1 to 3. A B in base 4 (the socket's directory) is one per socket directory
- When it is known beforehand that the spelling will not fit (estimable from the length of the base's real path), B is not created
- When the default connect creates B for the first time with link-file, that B (and its fd) is also used as the process's B from then on (no D is created)
- When `Options.base` is given, that path is B. sockat only creates the per-process D inside, and leaves cleaning B to the app. When the checks fail it is an error, and it does not fall back to the automatic bases
- Passing a different `Options.base` per call makes one process hold several B, with a D per (process, B)
- How B is chosen with `usable_cross_uid` is in "[Another uid and PrivateTmp](#another-uid-and-privatetmp)"

### Spelling forms

sockat decides by itself. From the top, the first that fits.

| Spelling | Form | Used when | Diagnostic `base` | Whether other processes can follow it |
|---|---|---|---|---|
| procB | `/proc/<pid>/fd/<B's fd>/D/…` | `/proc` is usable and it fits (not with `usable_cross_uid`) | `proc` (`sockdir` when B is in the socket's directory, `given` when B is the one of `Options.base`) | same uid and same PID namespace only (root can follow). Not after the process exits |
| real path | B's real path `…/B/D/…` | it fits | B's base (`tmp` / `runtime` / `tmpdir`; `given` when B is the one of `Options.base`) | other uids too when every directory on the way to B and B itself give x to other (B in `/tmp`), otherwise the same uid only (`/run/user/<uid>` and macOS's `$TMPDIR` are 0700) |

- procB has the same form wherever B's real directory is
- `/proc` is taken as usable only when the `(st_dev, st_ino)` from stat-ing `/proc/<pid>/fd/<B's fd>` is the same as `fstat` of B's fd (in case the PID namespace and the `/proc` mount disagree)
- The diagnostic `base` shows the spelling form when B is in a temporary base (`/tmp`, `$XDG_RUNTIME_DIR`, `$TMPDIR`) (`proc` for procB, the base's name for the real path), and shows that B regardless of the spelling form when B is not in a temporary base (the socket's directory, `Options.base`) (`sockdir`, `given`). Whether the spelling is procB or the real path is told by `until` of `Spelling`
- When B is in the socket's directory, the real-path spelling is longer than the original path, so only the procB spelling can be used. On an OS where `/proc` is not usable, resolve's spelling cannot be used, and thread-cwd / at is next
- When no spelling fits, thread-cwd / at is next

### Another uid and PrivateTmp

- With `Options.usable_cross_uid`, only the bases in the order above where every directory on the way to B and B itself give x (the right to traverse) to other are used for B (the first of them where it can be created; an existing B that is 0700 does not qualify), and the procB spelling is not used (even if the child is 0711, another uid cannot traverse it when the parent is 0700; measured)
  - `/tmp` (1777) always qualifies
  - `$XDG_RUNTIME_DIR` (`/run/user/<uid>`) and macOS's `$TMPDIR` are 0700, so they do not. An environment that points `$TMPDIR` at a traversable place qualifies
- When nothing qualifies, or that B's spelling does not fit, it goes on to thread-cwd / at (`Dangling`) rather than falling back to a spelling that does not meet it. That D is created in the usual B that does not look at `usable_cross_uid` (in the order of bases 1 to 4)
- Together with `Options.base`, it is checked that every directory on the way to that base and the base itself give x to other; if not, `EPERM` (no fallback to the automatic bases)
- The connect side (the default connect, `connect_ex`, `resolve_for_connect`) does not look at `usable_cross_uid` (a connect's spelling does not stay with the peer). `Options.base` is used as the base for B on the connect side too
- When this B is a different place from the usual B, it is used as one more B (the only case where a process uses more than one B in the automatic bases)
- A peer whose `/tmp` is isolated (systemd's `PrivateTmp`, etc.) is not an option (procB is tried first, so on Linux this rarely happens). Whether it can be followed is told by `usable_with_private_tmp` of the resulting `Spelling`

## D and E

| | D | E |
|---|---|---|
| Where | inside B | resolve's E and thread-cwd / at's E inside D. The default connect's link-file E right under B |
| Unit | one per (process, B). Created only by a bind that keeps its spelling (including thread-cwd / at) and by `resolve_for_connect` | one per resolve. One per call for thread-cwd / at and for the default connect's link-file |
| Name | 10 random characters | resolve's E is a counter within the process (base 36; it can be short because D is unique per (process, B)). thread-cwd / at's E and the E right under B are 10 random characters |
| mode | 0711 (so that another uid can follow the spelling of B in `/tmp`) | none (a symlink's mode does not affect the right to follow it) |
| While alive | the process keeps an fd holding a flock (shared lock) | resolve's E is not removed |
| Cleanup | not by sockat. Only when `sweep()` is called are the D whose lock has been released removed | resolve's E by `cleanup`. A per-call E is unlinked within the call |

Creating D:

1. Relative to B's fd, `mkdirat(B's fd, name, 0700)` with a random name. On `EEXIST`, draw a new name, giving up after 16 tries
2. Right after creating it, set the mode with `fchmodat(B's fd, name, 0711)`, then open it with `O_DIRECTORY | O_NOFOLLOW` and check with `fstat` that it is a real directory owned by oneself. When the mode cannot be set or it cannot be opened, remove the empty directory one just created and go on to the next base
3. Put a flock (shared lock) on that fd and keep holding it. The fd is close-on-exec
4. Check that the `(st_dev, st_ino)` from `lstat` by name is the same as the fd's. If not (another process's `sweep()` removed it between 1 and 3), close the fd and start again from 1

- `sweep()` and `sweep_base(path)` take the owner of a D in B to be dead when `flock(LOCK_EX | LOCK_NB)` on that D succeeds, and remove it (which B are covered is in [the SPEC's `sweep`](SPEC.md#sweep)). They do not touch the E right under B (the default connect's), and leave a D containing something other than a symlink
- Random names use 62 alphanumeric characters from the OS's secure random source. The names are made the same way in the 3 languages
- D's name is not a counter, so that the spelling does not become the same when another process with the same PID and the same fd number appears after the process exits
- While D lives it is protected by flock, and B and D are 0711, so the spelling does not later hit an unrelated file (procB cannot be followed after the process exits; a real-path spelling points to the same place until D is removed)
- systemd-tmpfiles (v242 or later) does not clean a directory holding a lock, nor anything under it
- The default connect creates no D (so that D and the flock's fd do not stay in the process)

## Routes

The sections follow the order of the table in [the SPEC's Route names](SPEC.md#route-names). The order tried is in [Bind order](SPEC.md#bind-order) and [Connect order](SPEC.md#connect-order).

### standard

- How: hand the path to the standard unchanged ([the SPEC's Short paths](SPEC.md#short-paths))
- Used when: the path is up to the standard length. First for both bind and connect
- Reach: the whole path up to the standard length
- Spelling properties: `Original` for an absolute path, `CwdRelative` for a relative one

### link-dir

- How: create in D an E pointing to the realpath of the socket's directory, and bind by `B/D/E/<file name>`. E is kept until `cleanup`. When the bind fails ([How a failing route is treated](#how-a-failing-route-is-treated)), E is removed right there before the error is returned
- Used when: 2 (procB) and 3 (real path) of the bind order. The spelling `resolve_for_bind` chooses first. Trying it with procB and with the real path is one element in `skipped` (with the last reason)
- Unusable when: the spelling does not fit in a sockaddr, B / D / E cannot be created; for procB, `/proc` is not usable or `usable_cross_uid` is given
- File name reached: sockaddr length − (B's spelling + D + E + 3 separators). About 70 for procB on Linux ([the SPEC's Open questions](SPEC.md#open-questions))
- Spelling properties: `Linked` (`removable` is true)

### link-file

- How: create an E pointing to the socket file's spelling (with the cwd prepended for a relative path), and bind / connect by its spelling
  - bind, `resolve_for_bind` and `resolve_for_connect`: E inside D, the spelling `B/D/E` (B spelled as procB or the real path, per "[Spelling forms](#spelling-forms)"). E is kept until `cleanup`. When the bind fails (both when the error is returned and when it goes on by telling it apart below), E is removed right there
  - the default connect variants: create no D, create an E with a random name right under B, connect by `B/E` with B's real path (procB is not used; B is in `/tmp` first, so it is short), and unlink E right after the connect. Cleanup is only the unlink, with no wait
- Used when: 4 of the bind order (real path only; there is no procB link-file, since Linux, which has `/proc`, does not follow a symlink on bind). 4 of the connect order. `resolve_for_bind` uses it only on the OSes measured to follow a symlink on bind (macOS, NetBSD), not on OSes not yet checked (resolve does not bind, so the telling below cannot be used). `resolve_for_connect` uses only this, and gives `ENAMETOOLONG` when it cannot be used
- Unusable when: the spelling does not fit in a sockaddr, B / D / E cannot be created. On bind, the kernel did not follow the symlink (below)
- File name reached: the file name does not appear in the spelling, so whatever its length (the spelling up to the sockaddr length; the whole original path up to PATH_MAX)
- Spelling properties (bind): `Linked` (`removable` is false: unlinking by the spelling does not follow the last symlink, and removes E)
- connect always follows a symlink in the last component

Telling whether bind follows a symlink in the last component:

- Not tried on the OSes measured not to follow (Linux / Android, FreeBSD 15, OpenBSD 8, illumos (OmniOS)). macOS 26 and NetBSD 11 follow it (measured 2026-11-19, [findings](findings/2026-11-19-bind-through-file-symlink.md), Japanese)
- On other OSes (the default `bind` and `bind_ex`), when the bind fails, `lstat` the original path; if something is there, return that error (`EADDRINUSE` etc.) and do not try the next. If nothing is there or it cannot be checked, take it that the kernel did not follow, treat this route as unusable and go on (it goes into `skipped`, and the E created does not remain). A real failure fails the same way on the next route and is returned there
- When a symlink was already at the last component of the original path before the bind, the bind following it is a property of the standard bind, and sockat does not check it

### thread-cwd

- How: with [the steps of thread-cwd and at](#steps-of-thread-cwd-and-at), move [a throwaway thread](#the-throwaway-thread)'s cwd into D and bind by `E/<file name>`. `unshare(CLONE_FS)` → `fchdir(D's fd)` on Linux / Android, `pthread_fchdir_np(D's fd)` on Apple OSes
- Used when: 5 of the bind order. Linux / Android, Apple OSes
- Unusable when:
  - Linux / Android: it cannot be confirmed that no seccomp filter is installed (`prctl(PR_GET_SECCOMP)` is non-zero or fails), `unshare` is refused
  - Apple OSes: `pthread_fchdir_np` is missing or fails
  - a thread cannot be created
  - NetBSD / OpenBSD / illumos
  - neither B nor D can be created, the spelling does not fit in a sockaddr
- File name reached: sockaddr length − (E's name + 1)
- Spelling properties: `Dangling`

### at

- How: with [the steps of thread-cwd and at](#steps-of-thread-cwd-and-at), bind by `bindat(D's fd, E/<file name>)` without a thread
- Used when: 5 of the bind order. FreeBSD
- Unusable when: neither B nor D can be created, the spelling does not fit in a sockaddr
- File name reached: sockaddr length − (E's name + 1)
- Spelling properties: `Dangling`

### proc-direct

- How: open the socket's directory and connect by `/proc/self/fd/<fd>/<file name>`
- Used when: 2 of the connect order. Linux / Android with `/proc` usable
- Unusable when: the socket's directory cannot be opened, `/proc/self/fd/<fd>` cannot be looked up with stat, the spelling does not fit in a sockaddr
- File name reached: about 90 (depends on the fd's digits)
- bind does not use it (the fd number in the spelling is later reused, and it hits a same-named file in another directory)

### relative

- How: connect by a path relative to the cwd. Only the string is rewritten; there is no `chdir` ([Building the relative path](#building-the-relative-path))
- Used when: 2 of the connect order. The original path is absolute. Linux / Android without `/proc` usable, Apple OSes, NetBSD / OpenBSD / illumos / other Unix
- Unusable when: the relative path is over the sockaddr length, the directory of the built spelling does not match the original by `(st_dev, st_ino)`, the cwd has already changed
- Reach: the relative path within the sockaddr length
- bind does not use it (when the cwd changes, the spelling hits somewhere else)

### widened

- How: connect with a sockaddr whose `sun_len` and address length are `2 + path length`, passing the original path, or the relative path if that does not work
- Used when: 2 of the connect order, after relative. Apple OSes. The path is up to 253 bytes
- Unusable when: the kernel returns `EINVAL` / `ENAMETOOLONG`
- Reach: the original or relative path up to 253
- bind does not use it (the address is cut in the middle and breaks the reading side, such as CPython's `getsockname` and Go's `net.FileConn`)

### at-direct

- How: open the socket's directory and connect by `connectat(fd, <file name>)`. Not through E
- Used when: 2 of the connect order. FreeBSD
- Unusable when: the socket's directory cannot be opened, the file name is over 103 bytes
- File name reached: 103
- bind does not use it (the spelling becomes the file name alone, and later hits a same-named file in the process's cwd)

### thread-cwd-direct

- How: open the socket's directory, move [a throwaway thread](#the-throwaway-thread)'s cwd there (the same means as [thread-cwd](#thread-cwd)), and connect by the file name. Needs neither D nor E (a connect's spelling does not stay with the peer)
- Used when: 3 of the connect order (stream and DGRAM). Linux / Android, Apple OSes
- Unusable when: those of [thread-cwd](#thread-cwd)'s "unusable when" that do not depend on B / D, the socket's directory cannot be opened, the file name is over the sockaddr length
- File name reached: the sockaddr length

## Steps of thread-cwd and at

Used by a bind when resolve's spelling does not fit.

1. Use the process's D, held by fd, as the base (when neither B nor D can be created, thread-cwd / at are unusable and skipped)
2. In D, create with `symlinkat` an E with a random name pointing to the realpath of the socket's directory
3. Bind by `E/<file name>` relative to D's fd (the means below)
4. Remove E at once, on success or failure (only if this call created it). The spelling is `Dangling`

| Means | How the base fd (D for thread-cwd / at, the socket's directory for thread-cwd-direct) is used | OS |
|---|---|---|
| thread-cwd | move the cwd in a throwaway thread (`unshare(CLONE_FS)` → `fchdir`) | Linux / Android |
| thread-cwd | `pthread_fchdir_np(fd)` in a throwaway thread | Apple OSes |
| at | pass the fd to `bindat` (no thread) | FreeBSD |

- The spelling contains the random name E already removed, so even if the fd number is later reused, it hits nothing unless a same-named thing happens to be in the cwd (the spelling can be seen by other users, so when the process's cwd is writable by others, someone can see it and recreate it. Removing by the original path never hits it)
- E points to the realpath of the socket's directory, so a rename or a symlink swap of the directory after E is created is not reflected
- If the process dies midway, E stays in D (it is removed with D by the OS's cleaning)

## The throwaway thread

Used by [thread-cwd](#thread-cwd) and [thread-cwd-direct](#thread-cwd-direct).

- The thread is a throwaway one sockat creates, discarded after use. The calling thread's cwd is never touched (going back with `pthread_fchdir_np(-1)` can erase a cwd the caller gave its thread)
- The caller waits until the throwaway thread ends before cleaning up E and closing the fds. Even when the wait is interrupted (Python's `KeyboardInterrupt` etc.), nothing is cleaned up until the thread ends (if an fd closed first had its number reused, the thread would move into an unrelated directory and bind / connect there)
- On Linux / Android, `unshare` is not called when a seccomp filter is installed. There are environments where the filter refuses it by killing the process (SIGSYS) (the default of systemd's `SystemCallFilter=`)
- A failure of the `fchdir` after `unshare` (`EACCES` etc.) is returned as a real failure
- `pthread_fchdir_np` is a private libSystem API (the `__pthread_fchdir` syscall). It is looked up at run time, and when it is missing the next route is tried

## Building the relative path

Used by [relative](#relative).

1. If the path starts with the cwd's spelling (`getcwd`, or `$PWD` when its `stat` `(st_dev, st_ino)` matches `.`), strip it at a separator boundary
2. Only when step 1 does not bring it within the sockaddr length, turn the socket's directory and the cwd into real paths with `realpath` and build a spelling that climbs with `..`
3. Use the shorter. Before using it, check that the relative path's directory and the original directory have the same `(st_dev, st_ino)`, and that the cwd's `(st_dev, st_ino)` is the same as before step 1. If not, this route is unusable
4. If the cwd's `(st_dev, st_ino)` has changed after the connect, discard the result and return a general error (it never reaches somewhere else)

## How a failing route is treated

- When a route actually binds / connects and fails (`ENOENT`, `EADDRINUSE`, `ECONNREFUSED`, etc.), that error is returned and the next route is not tried
- Then the E made in that call is removed before returning (link-dir, link-file, thread-cwd, at; and the default connect's link-file). D and B are kept
- It goes on to the next only when the route itself is unusable (each route's "unusable when")
  - the spelling does not fit
  - B / D / E cannot be created
  - the means of thread-cwd, at or thread-cwd-direct is not usable
  - `/proc` is not usable
  - for widened, the kernel does not accept the widened sockaddr
  - the link-file bind fails and nothing is at the original path or it cannot be checked (taken as the kernel not following the symlink)
  - for relative, the directory of the built spelling does not match the original by `(st_dev, st_ino)`, or the cwd has already changed
  - no B meets `usable_cross_uid`
- A missing directory is `ENOENT` on every OS. The directory is looked up first, so this is decided before the length
