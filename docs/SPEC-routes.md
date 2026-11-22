# sockat specification: building the routes

> English | [日本語](./SPEC-routes-ja.md)

How the routes are built, for each language's implementers. The promise to users (operations, order tried, spelling properties, errors) is in [SPEC](SPEC.md), which is the source; this document describes how to build what meets it. Terms (B, D, E, base, procB, try, unusable, etc.) are in [the SPEC's Terms](SPEC.md#terms). Numbers are in bytes.

## Common

- How a directory is opened (the socket's directory, etc.): `O_SEARCH` on Apple OSes (`O_RDONLY` if the kernel answers `EISDIR` / `EINVAL`), `O_PATH | O_DIRECTORY` on Linux / Android, `O_RDONLY | O_DIRECTORY` elsewhere
- On receiving a relative path, bind and resolve build the absolute candidates before looking up the socket's directory ([Building the absolute candidates](#building-the-absolute-candidates)). When a candidate that fits is handed to the standard, the steps below are not reached
- When going on to the routes, the socket's directory is looked up first with `stat`, and its realpath is taken. When it is missing, `ENOENT`; when it is not a directory, `ENOTDIR`; when the realpath cannot be taken, that error (all before the length is judged or B / D / E is created). Only for a bind or resolve with a relative path whose realpath cannot be taken because of the path length (`ENAMETOOLONG`, `ERANGE`) are the routes treated as unusable instead ([SPEC, "Making a relative path absolute"](SPEC.md#making-a-relative-path-absolute))
- In bind and resolve, for an absolute path over the standard length, the real-path candidate (the realpath taken here with the file name appended) is looked at before any route is tried. When it fits, it is handed to the standard ([Building the absolute candidates](#building-the-absolute-candidates))
- Only the routes that need an fd of the socket's directory ([proc-direct](#proc-direct), [at-direct](#at-direct), [thread-cwd-direct](#thread-cwd-direct)) open it, and when it cannot be opened that route is unusable (`O_RDONLY` on other OSes cannot open a directory without read permission)
- The caller creates the socket. For a non-blocking connect the socket is made non-blocking before that. The listen after a bind is done by the caller
- No route changes the calling process's cwd or the calling thread's cwd

## Building B

The same steps for the automatic bases and for `Options.base`.

1. Make the base's path (the parent's path for `Options.base`) a real path with realpath (macOS's `/tmp` → `/private/tmp` etc.). The checks, opening and spelling below all use this real path
2. Check every directory from the root to the parent: each is owned by root or by oneself, and is either not writable by others or has the sticky bit (the owner of a sticky directory can still swap what is inside, so the owner condition is kept. the same idea as OpenSSH's StrictModes; if an ancestor is writable by others, the parent can be swapped out). For bases 1 to 3 and the socket's directory, only once per base, the first time in the process; for `Options.base`, on every call ([Where B is created](#where-b-is-created))
3. Open the parent with `O_DIRECTORY | O_NOFOLLOW`, hold it by fd, and create B with `mkdirat(parent fd, name, 0700)`
4. Right after creating it, set the mode with `fchmodat(parent fd, name, 0711)` (restoring what the umask took away; the parent has been checked and others cannot swap it), then open it with `O_DIRECTORY | O_NOFOLLOW` and check with `fstat` that it is a real directory owned by oneself. When the mode cannot be set or it cannot be opened, remove the empty directory one just created and go on to the next base (`Options.base` is an error)
5. On `EEXIST`, check what already exists in the same way (a real directory, owned by oneself, not writable by others). Use it even if its mode is not 0711, and do not change the mode. If it fails (occupied), an automatic base is treated as unusable and the next base is tried, and `Options.base` is an error

- "Not writable by others" includes the group (`mode & 022 == 0`)
- "Oneself" is the effective uid (`geteuid`). The `<uid>` in the name is the effective uid too
- When a directory on the way is missing, sockat does not create it and returns an error (how a place the app manages is created is up to the app)
- The name is `sockat-<uid>` (`sockat` under `$XDG_RUNTIME_DIR`, `.sockat.<10 random characters>` under the socket's directory). `Options.base` is the path of B itself, and its last component is the name
- Errors for `Options.base`: an invalid argument when it is a relative path, contains a NUL, or its last component is not a file name (`dir/`, `..`, `/`), `ENOENT` when a directory on the way is missing, `ENOTDIR` when the base is not a directory, `EPERM` when the owner / permission checks fail
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
- Bases are deduplicated by the `(st_dev, st_ino)` of their realpath (macOS's `TMPDIR=/private/tmp` and `/tmp`, etc.)
- A process using one B applies to bases 1 to 3. A B in base 4 (the socket's directory) is one per socket directory
- When it is known beforehand that the spelling will not fit (estimable from the length of the base's real path), B is not created. It does not move on to the next base either; the routes that use B are skipped as unusable (the process's B is the first base where it could be created, and does not change with the path's length)
- When a held B or D has been removed (`st_nlink` of the `fstat` of its fd is 0, or the name's `lstat` and the fd differ in `(st_dev, st_ino)`), it is dropped and created again on the next call (an old systemd-tmpfiles, macOS's `$TMPDIR` cleaning, removed by hand). A removed directory's `st_nlink` becomes 0 on Linux but stays 2 on macOS (APFS), so the check by name is not skipped. The fds of a dropped B or D are not closed but held for the life of the process (if closed, the fd number is reused, and the spelling of a live socket whose procB spelling goes through that number hits another directory)
- Order of choosing B: skip the failures known without creating anything (the base is missing, the check of the directories on the way fails, no other x when `usable_cross_uid` is asked), and estimate the spelling's length at the first base left. If it does not fit, stop there and do not move on to the next base. If creation fails after the estimate passed (`mkdirat` fails, an existing B fails the checks (occupied), etc.), go on to the next base. When moving on like this, estimate the spelling's length again at that base, and if it does not fit, stop there without creating B (so as not to create and hold a B in a base where it does not fit)
- The ordinary B and the B for `usable_cross_uid` are held separately (a later ordinary bind does not switch to the `usable_cross_uid` B). That D could not be created is remembered per B for the rest of that call, and D is not tried again in the same B within the same call
- The safety check of `Options.base` (the directories on the way, owner, not writable by others) is done on every call. The other-x judgement for `usable_cross_uid` is remembered from when B was created (first held). But when it remembered that B itself lacks other x, it is re-checked with `fstat` of B's fd on each call with `usable_cross_uid` (when 2 processes create B for the first time at once, one can open it between the other's `mkdirat` (0700) and `fchmodat` (0711))
- A B once held (bases 1 to 3) is used for the rest of the process. A base where creation failed is not remembered and is tried again on the next call. When D cannot be created, the routes that use D are unusable for that call, and no other B is looked for
- When B cannot be created after the check of `Options.base` passed, that error is returned (`route` none, `skipped` what came before)
- A B in the socket's directory is used only with the procB spelling, not with the real path spelling
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
- For procB (including the estimate of the spelling's length), `/proc` is taken as usable only when the `(st_dev, st_ino)` from stat-ing `/proc/<pid>/fd/<B's fd>` is the same as `fstat` of B's fd (in case the PID namespace and the `/proc` mount disagree). For the estimate before B is opened, the same check is made with the fd of another open directory. The check that chooses the connect row and the check of proc-direct are different ones ([Terms in the SPEC](SPEC.md#terms), [proc-direct](#proc-direct))
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
| Unit | one per (process, B). Created only by a bind that keeps its spelling (including thread-cwd / at) and by `resolve_for_connect` | one per resolve. The default bind's link-dir reuses one per (D, realpath of the socket's directory) ([link-dir](#link-dir)). One per call for thread-cwd / at and for the default connect's link-file |
| Name | 10 random characters | resolve's E is a counter within the process (base 36; it can be short because D is unique per (process, B)). thread-cwd / at's E and the E right under B are 10 random characters |
| mode | 0711 (so that another uid can follow the spelling of B in `/tmp`) | none (a symlink's mode does not affect the right to follow it) |
| While alive | the process keeps an fd holding a flock (shared lock) | resolve's E is not removed |
| Cleanup | not by sockat. Only when `sweep()` is called are the D whose lock has been released removed | resolve's E by `cleanup`. A per-call E is unlinked within the call |

Creating D:

1. Relative to B's fd, `mkdirat(B's fd, name, 0700)` with a random name. On `EEXIST`, draw a new name, giving up after 16 tries
2. Right after creating it, set the mode with `fchmodat(B's fd, name, 0711)`, then open it with `O_DIRECTORY | O_NOFOLLOW` and check with `fstat` that it is a real directory owned by oneself. When the mode cannot be set or it cannot be opened, remove the empty directory one just created, and the routes that use D are unusable for that call (no other B is looked for)
3. Put a flock (shared lock) on that fd and keep holding it. The fd is close-on-exec
4. Check that the `(st_dev, st_ino)` from `lstat` by name is the same as the fd's. If not (another process's `sweep()` removed it between 1 and 3), close the fd and start again from 1

- `sweep()` and `sweep_base(path)` take the owner of a D in B to be dead when `flock(LOCK_EX | LOCK_NB)` on that D succeeds, and remove it (which B are covered is in [the SPEC's `sweep`](SPEC.md#sweep)). Inside B and D they list by fd, and remove only after taking the exclusive lock and checking that the name's `(st_dev, st_ino)` is the same as the locked fd's. `sweep()` silently skips a B it cannot read (no permission, etc.), as it does a base that fails the checks. They do not touch the E right under B (the default connect's), and leave a D containing something other than a symlink. They cover only the directories right under B named in the form of a D (10 characters of the 62 alphanumerics); B is sockat's own, and the user puts nothing else there
- Random names use 62 alphanumeric characters from the OS's secure random source. What the languages share is the form of the names (the characters and the length; sweep tells a D by its form). How bytes are mapped to characters is up to each implementation (rejection sampling without bias is recommended; the small bias of `% 62` is allowed)
- D's name is not a counter, so that the spelling does not become the same when another process with the same PID and the same fd number appears after the process exits
- While D lives it is protected by flock, and B and D are 0711, so the spelling does not later hit an unrelated file (procB cannot be followed after the process exits; a real-path spelling points to the same place until D is removed)
- systemd-tmpfiles (v242 or later) does not clean a directory holding a lock, nor anything under it
- The default connect creates no D (so that D and the flock's fd do not stay in the process)
- When cleaning up an E fails (the default connect's E, the E of a failed bind, the E of thread-cwd and at), it stays silent and changes neither the result of the call nor the original error (a failure to remove does not turn a successful connect into a failure)

## Routes

The sections follow the order of the table in [the SPEC's Route names](SPEC.md#route-names). The order tried is in [Bind order](SPEC.md#bind-order) and [Connect order](SPEC.md#connect-order).

### standard

- How: hand the path to the standard unchanged ([the SPEC's Short paths](SPEC.md#short-paths)). In bind and resolve, when the original path is relative or an absolute path over the standard length, hand the absolute candidate that fits ([Building the absolute candidates](#building-the-absolute-candidates))
- Used when: the spelling handed is up to the standard length. First for both bind and connect. In bind and resolve, also last, for a relative path up to the standard length when no route can be used (5 of [the SPEC's Making a relative path absolute](SPEC.md#making-a-relative-path-absolute))
- Reach: the whole spelling handed up to the standard length
- Spelling properties: `Original` for an absolute path and an absolute candidate, `CwdRelative` when handed as relative

### link-dir

- How: create in D an E pointing to the realpath of the socket's directory, and bind by `B/D/E/<file name>`. E is kept until `cleanup`. When the bind fails ([How a failing route is treated](#how-a-failing-route-is-treated)), the E made in that call is removed right there before the error is returned
- The E of the default bind (the one that returns no `SocketFile`): one per (D, realpath of the socket's directory) is reused, and binds to the same directory put their file names under the same E. The default bind does not clean up E, so references are not counted. `_ex` and resolve create an E per call (the unit of cleanup does not change)
  - When the reused E has been removed (`readlinkat` of its name relative to D's fd fails, or its target differs from the realpath of the socket's directory), it is dropped and created again (the same as B and D in [Where B is created](#where-b-is-created)). When D is created again, its E are created again too
  - When a bind fails, the E is not removed, including one made in that call (another concurrent default bind may be reusing it; [How a failing route is treated](#how-a-failing-route-is-treated))
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
- Used when: 2 of the connect order. Linux / Android in the row with `/proc` usable (how the row is chosen is in [Terms in the SPEC](SPEC.md#terms))
- Unusable when: the socket's directory cannot be opened, `/proc/self/fd/<fd>` stat'ed with that directory's fd differs from `fstat` of the fd in `(st_dev, st_ino)` (checked on every call with the fd actually used, apart from the check that chose the row), the spelling does not fit in a sockaddr
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

## Building the absolute candidates

Used by [the SPEC's Making a relative path absolute](SPEC.md#making-a-relative-path-absolute). Bind and resolve build both on receiving a relative path, and only the real-path candidate on receiving an absolute path over the standard length. It goes the other way from [Building the relative path](#building-the-relative-path) (connect's relative, which strips the cwd from an absolute path), and checks by `(st_dev, st_ino)` in the same way.

| Candidate | How it is built | Check |
|---|---|---|
| the real-path candidate | make the socket's directory (what precedes the last component of the original path; `.` for a relative path without `/`) a real path with realpath(3) (following symlinks), and join `/` and the file name | not needed (realpath is the OS's own lookup) |
| the `$PWD` candidate (only for a relative path) | the steps below | 1 and 3 of the steps below |

Steps of the `$PWD` candidate:

1. Do not build it when `$PWD` is missing or not an absolute path, or when the `(st_dev, st_ino)` from `stat` of `$PWD` differs from `stat` of `.` (`$PWD` is an inherited environment variable and may not have been updated after the cwd changed)
2. Join `$PWD` and the relative path with `/`, split it into components and fold it lexically: drop empty components and `.`, and drop each `..` together with the component before it (`..` at the root stays the root)
3. `stat` the directory of the folded spelling (what precedes the last component), and do not build it when its `(st_dev, st_ino)` differs from the directory of the original relative path (looked up from the cwd). The kernel takes `a/sym/..` to be the parent of the symlink's target, so folding lexically can give another directory

How they are used:

- The real-path candidate is looked at first. When it is up to the standard length it is used, and the `$PWD` candidate need not be built. Lengths are compared in bytes
- A candidate that cannot be built (realpath or `stat` fails, the cwd is over PATH_MAX, `$PWD` fails the check) is not a failure; that candidate just does not exist. No error is returned, and it goes on to the next candidate or to the routes. When the socket's directory is missing there is no candidate either, and it becomes `ENOENT` where the routes look up the socket's directory
- A candidate is not a route, so no candidate name goes into `skipped`. When a candidate is handed to the standard, `route` is `standard` and `skipped` is empty (even for an absolute path over the standard length)
- When a bind with a candidate handed to the standard fails, that error is returned. Neither the other candidate, the routes, nor the original relative path is tried again ([How a failing route is treated](#how-a-failing-route-is-treated))
- Joining, folding and comparing are done on bytes (the path is not converted into a string type; a name that is not UTF-8 is kept as it is)
- Many of the languages' functions that join or normalize paths silently fold `..` lexically (Go's `filepath.Join` and `filepath.Abs`, Python's `os.path.abspath` and `os.path.normpath`, Node's `path.resolve` and `path.join`; measured 2026-11-22). When the `$PWD` candidate is built with them, the check of 3 is still not skipped. For the real-path candidate, do not make the path absolute with them before realpath (`a/sym/..` would be folded first and realpath would look up another directory)
- The real-path candidate points to the real directory at the time realpath was taken. A later rename of the directory or a symlink swap is not reflected (as with link-dir's E)

## Building the relative path

Used by [relative](#relative).

1. If the path starts with the cwd's spelling (`getcwd`, or `$PWD` when its `stat` `(st_dev, st_ino)` matches `.`), strip it at a separator boundary
2. Only when step 1 does not bring it within the sockaddr length, turn the socket's directory and the cwd into real paths with `realpath` and build a spelling that climbs with `..`
3. Use the shorter. Before using it, check that the relative path's directory and the original directory have the same `(st_dev, st_ino)`, and that the cwd's `(st_dev, st_ino)` is the same as before step 1. If not, this route is unusable
4. If the cwd's `(st_dev, st_ino)` has changed after the connect, discard the result and return a general error (it never reaches somewhere else)

## How a failing route is treated

- When a route actually binds / connects and fails (`ENOENT`, `EADDRINUSE`, `ECONNREFUSED`, etc.), that error is returned and the next route is not tried. The same when a bind with an absolute candidate handed to the standard fails: neither the other candidate, the routes, nor the original relative path is tried again
- Then the E made in that call is removed before returning (link-dir, link-file, thread-cwd, at; and the default connect's link-file). The default bind's link-dir E is kept, including one made in that call (another concurrent default bind may be reusing the same E, and a kept E is used by the next bind; since it is not removed, no lock serializing default binds is needed). D and B are kept too
- When removing the E fails, it stays silent and changes neither the result of the call nor the original error (a successful connect is not turned into a failure; the original error is not replaced by the removal's). The `cleanup()` the user calls is different and returns the failure as an error ([SPEC `remove` and `cleanup`](SPEC.md#remove-and-cleanup))
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
