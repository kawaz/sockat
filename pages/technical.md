# How sockat works

> English | [日本語](./technical-ja.md)

How sockat makes a short path in place of a long one. This page lines up the techniques considered, compares them, and says which ones sockat uses, in what order, and why. For usage, see the [README](../README.md) and the [user manual](./manual.md).

## The problem

```
/home/u/.cache/example-app/worktrees/feature-login/.tmp/test-0f3a9c/daemon.sock
```

A Unix domain socket address (`sockaddr_un`) carries the path in a fixed-size field called `sun_path`. Leaving room for the NUL, it holds 107 bytes on Linux and 103 bytes on macOS and the BSDs. This page calls this the "sockaddr length". A path deep down like the one above goes over it, and the standard library refuses before the bind / connect (Rust's `path must be shorter than SUN_LEN`, Python's `AF_UNIX path too long`, etc.). Some standard libraries, like that of Node.js 22 on Linux, silently truncate it to 108 bytes and create the socket somewhere else.

The limit is on the length of the path string handed to the kernel, not on the depth of the directory. Hand it a short string that points to the same place, and a socket deep down is reached.

```
/very/deep/.../dir/daemon.sock    too long to fit sun_path
daemon.sock                       the same place if the cwd is /very/deep/.../dir
/tmp/x/L/daemon.sock              the same place if /tmp/x/L is a symlink to /very/deep/.../dir
```

This page calls the path string handed to the kernel the "spelling". How to make a short spelling that points to the same place as the original path is what sockat is about.

- The workaround of creating a different socket in a short place such as `/tmp` is not covered, since no socket appears at the original path
- Depending on the technique, the directory part can drop out of the spelling, but the file name (the last component of the path) stays in the spelling for most techniques. So for most techniques, how far they reach is decided by "how many bytes the file name can be"

## Techniques for a short spelling

### Moving the cwd

```
chdir("/very/deep/.../dir")
bind(sock, "daemon.sock")
```

Move the cwd into the socket's directory, and a spelling of just the file name reaches it. There are 3 kinds, by whose cwd is moved.

- **The process's chdir**: the most straightforward. But a process has one cwd, so a library call changes process-wide state
- **A thread's cwd**: moves only the cwd of a throwaway thread. Linux uses `fchdir` after `unshare(CLONE_FS)`; Apple OSes use `pthread_fchdir_np`. Usable on Linux / Android and Apple OSes
- **A forked child**: only the child moves, binds / connects, and exits at once. The child and the parent share the same socket, so the result stays on the parent's socket. The listen after a bind is done by the parent (if the child listens, the server peer the other side sees is the dead child)

When the spelling is just the file name, the reach is a file name up to the sockaddr length (107 on Linux, 103 on macOS and the BSDs).

Drawbacks:

- A thread's cwd cannot be used on Linux under a seccomp filter (docker's default, systemd's `SystemCallFilter=`). Some filters kill the process with SIGSYS on the mere call of `unshare`, so you have to check first whether one is in place
- `pthread_fchdir_np` is a private API of libSystem and may go away in the future
- Starting a thread has a cost. In a study for the TypeScript implementation, starting a throwaway Worker took about 9 ms per call, while a connect through the standard library with a spelling through a symlink took 0.1 ms
- fork has side effects on the whole process: the child holds copies of every fd, the parent gets `SIGCHLD`, `pthread_atfork` handlers run, another thread's `waitpid(-1)` may reap the child, on connect the peer pid the other side sees is that of the exited child, etc. In Go the runtime does not work in a forked child, so it cannot be used
- On bind, the spelling the kernel remembers is just the file name ([next section](#bind-and-connect-differ))

### A path relative to the cwd

```
cwd:       /home/u/work
original:  /home/u/work/a/very/deep/.../dir/daemon.sock
spelling:  a/very/deep/.../dir/daemon.sock
```

No chdir; only the string is rewritten. If the cwd is above the original path, the front is cut off; otherwise a spelling that climbs with `..` is made.

- Pros: needs no write and no thread, and works on every OS. If the socket's directory is close to the cwd, even a long file name is reached
- Cons: whether it reaches depends on the cwd (the whole relative path must be within the sockaddr length). If another thread changes the cwd between making the spelling and using it, it points somewhere else. A bind's spelling also points somewhere else when the cwd changes later

### `/proc/self/fd/<fd>/<name>`

```
fd = open("/very/deep/.../dir", O_PATH | O_DIRECTORY)     → 7
spelling:  /proc/self/fd/7/daemon.sock
```

Open the socket's directory, hold the fd, and spell through that fd in `/proc`.

- OSes: Linux / Android with `/proc`
- Reach: a file name up to about 90 bytes (it varies with the fd's digits)
- Pros: needs no write and no thread. crun, conmon, podman, systemd's `connect_unix_path` and Bun's standard library (Linux) use this form for long paths
- Cons: you have to be ready for environments where the PID namespace and the `/proc` mount do not match. sockat uses it only when `/proc/self/fd/<fd>` stat'ed has the same `(st_dev, st_ino)` as `fstat` of the fd. On bind, the spelling points somewhere else after the fd is closed

### Placing a symlink

```
/tmp/x/L  →  /very/deep/.../dir                  points to the directory
spelling:  /tmp/x/L/daemon.sock

/tmp/x/L  →  /very/deep/.../dir/daemon.sock      points to the file
spelling:  /tmp/x/L
```

Place a symlink in a short place and spell through it.

A symlink to the directory works on every OS. The file name reached is the sockaddr length minus the base's spelling and the symlink's name. Unlinking by the spelling follows the symlink in the middle and removes the original file, which works the same as unlinking by the original path.

A symlink to the file:

- connect always follows a symlink in the last component, so it works on every OS
- Whether bind follows a symlink in the last component differs by OS. Measured: macOS and NetBSD follow it; Linux, FreeBSD and OpenBSD do not. On the OSes that do not, it fails with `EADDRINUSE` and nothing is created at the original path
- The file name does not appear in the spelling, so it reaches whatever the file name's length (the whole original path up to PATH_MAX)
- Unlinking by the spelling only removes the symlink; the socket file stays

Both:

- Pros: if there is a short place you can write to, no thread and no `/proc` are needed
- Cons: you have to write to the base, and things are left behind. If others can write to the base, they can swap the symlink. The spelling points to the same place as the original path only while the symlink exists

### `bindat` / `connectat`

```
fd = open("/very/deep/.../dir", O_RDONLY | O_DIRECTORY)
connectat(fd, sock, <sockaddr of "daemon.sock">, len)
```

Pass the directory's fd and have the relative spelling looked up from that directory. It is the bind / connect version of `openat`.

- OSes: FreeBSD
- Reach: a file name up to 103 bytes
- Pros: needs no write and no thread
- Cons: only FreeBSD has it. On bind, the spelling the kernel remembers is just the file name

### Apple's widened sockaddr

```
pass a sockaddr whose sun_len and address length are "2 + the path's length", holding a path of up to 253 bytes
```

The kernel of Apple OSes accepts an address longer than the declared `sun_path` (104 bytes).

- OSes: Apple OSes
- Reach: the whole path (or a relative path) up to 253 bytes
- Pros: creates nothing, and the original path can be passed as is. Node.js on macOS with libuv 1.53 or later binds / connects paths of 104 to 253 bytes this way
- Cons: the address of a socket bound this way is cut in the middle, and the reading side breaks. CPython's `getsockname` returns it with unrelated bytes appended, and asyncio's cleanup crashes. With Go's `net.FileConn`, the peer's `RemoteAddr` is nil and `.String()` panics

### Comparison

| Technique | Example spelling | OSes | Reach (Linux / macOS) | Needs |
|---|---|---|---|---|
| The process's chdir | `daemon.sock` | all | file name 107 / 103 | being allowed to change the process's cwd |
| A thread's cwd | `daemon.sock` | Linux / Android<br>Apple OSes | file name 107 / 103 | a thread<br>on Linux, no seccomp filter |
| A forked child | `daemon.sock` | all | file name 107 / 103 | being allowed to fork |
| Relative path | `a/…/daemon.sock` | all | whole relative path 107 / 103 | the cwd being close to the socket |
| `/proc/self/fd` | `/proc/self/fd/7/daemon.sock` | Linux / Android | file name about 90 / — | `/proc` |
| Symlink to the directory | `/tmp/x/L/daemon.sock` | all | depends on the length of the base's spelling | a short base you can write to |
| Symlink to the file | `/tmp/x/L` | connect: all<br>bind: macOS, NetBSD | any file name length | a short base you can write to |
| `bindat` / `connectat` | fd + `daemon.sock` | FreeBSD | — / — (file name 103 on FreeBSD) | — |
| Widened sockaddr | the original path | Apple OSes | — / whole path 253 | — |

## bind and connect differ

### A bind's spelling stays in the kernel

```
fd = open("/very/deep/.../dir", O_PATH | O_DIRECTORY)     → 7
bind(sock, "/proc/self/fd/7/daemon.sock")
close(fd)
getsockname(sock)                                          → "/proc/self/fd/7/daemon.sock"
```

The kernel remembers the spelling passed to bind and returns it from `getsockname` (and from `getpeername` on a side that connected to it). This spelling gets used later.

- Upper libraries unlink / stat by the returned spelling (Python asyncio's cleanup, Go's `UnixListener.Close`). So does the user's `remove_file(local_addr)`
- A DGRAM receiver replies to the sender's spelling
- Operational tools such as `ss -x`, `lsof` and `/proc/net/unix` show that spelling

The spelling is resolved again later, in another context. A spelling that would then hit an unrelated file cannot be used for bind.

| Bind spelling | Resolved later, it |
|---|---|
| `/proc/self/fd/<n>/<file name>` | hits a same-named file in another directory once the closed fd's number is reused (sockat-rs measured this in docker, and an unrelated file was removed) |
| just the file name (the cwd-moving techniques, `bindat`) | hits a same-named file in the process's cwd (measured by sockat-py on macOS) |
| a path relative to the cwd | hits another place when the cwd changes |
| widened sockaddr | the address is cut in the middle, and the reading side breaks |

It is the upper library, not the user's code, that removes the file, so the user has no way to avoid it. There are real uses of these forms. Bun's standard library, for a bind at a long path, binds with `/proc/self/fd/<fd>/<file name>` on Linux and then closes the fd, and binds with just the file name on macOS. crun and conmon also bind with `/proc/self/fd/<fd>/<name>` of an fd they close later.

The opposite form also exists: bind through a symlink with a random name and remove it at once within the call. It does not hit an unrelated file later, but since the spelling reaches nothing, upper libraries that remove by the `getsockname` spelling, DGRAM replies and operational tools do not reach the original path. That a reply does not reach a DGRAM sender bound to a long path has been confirmed by measurement.

A bind's spelling must meet 2 conditions.

1. While the socket lives, it keeps pointing to the same place as the original path
2. However it is resolved later, it does not hit an unrelated file

### A connect's spelling does not stay with the peer

The connecting socket is not bound, so the spelling used for connect does not stay with the peer. Once connected, removing the symlink used, closing the directory's fd, or moving the cwd back leaves the connection as it is. For DGRAM, too, the destination is fixed at connect, and later `send`s reach it.

So connect need not care about bind's 2 conditions, and can choose techniques to fit how it is used. connect is done on demand, by CLIs and control queries. It may also be called by short-lived, numerous processes from a sandbox with no place to write. So for connect, few steps and needing no write and no thread come first.

- A relative-path connect checks the cwd after the connect, and if it changed, throws away the result and returns an error. It never returns having reached somewhere else

## The form sockat chose

### Base B, and D and E inside it

sockat sets up the symlink technique in a form that meets bind's 2 conditions. At its center are these 3.

```
/tmp/sockat-1000/                    B  a base per user. Reused across processes
/tmp/sockat-1000/k3J9xQ2mZa/         D  a directory per process. Its name is 10 random characters
/tmp/sockat-1000/k3J9xQ2mZa/0        E  a symlink. Points to the socket's directory or file
```

Example spellings:

```
/tmp/sockat-1000/k3J9xQ2mZa/0/daemon.sock     E points to the socket's directory
/tmp/sockat-1000/k3J9xQ2mZa/1                 E points to the socket file
/proc/4242/fd/5/k3J9xQ2mZa/0/daemon.sock      Linux. B spelled through the process's fd
```

- **B**: a real directory created in a temporary directory. Its name is `sockat-<uid>` (`sockat` under `$XDG_RUNTIME_DIR`). A process normally uses one B
- **D**: a directory created in B, one per (process, B). The process keeps an fd of D holding a flock (shared lock)
- **E**: a symlink in D. The name of an E kept in the spelling is a counter within the process (base 36); D is unique per process, so it can be short. The name of an E removed at once (those of thread-cwd / at and of the default connect) is 10 random characters

On Linux, when `/proc` is usable, the form that spells B as `/proc/<pid>/fd/<B's fd>` (procB) is tried first (not when `usable_cross_uid` asks that a peer of another uid can follow it). Only processes of the same uid can follow a procB spelling, and it cannot be followed after the process exits. It does not go through `/tmp`, so the peer can follow it even when its `/tmp` is isolated by systemd's `PrivateTmp`.

How the techniques of the previous section map to the names inside sockat. The names appear in the diagnostics of `_ex` (`route`, `skipped`).

| Technique | Name inside sockat | Used for |
|---|---|---|
| Hand the original path to the standard library unchanged | `standard` | bind, connect |
| Symlink to the directory (through B, D, E) | `link-dir` | bind |
| Symlink to the file (through B, D, E) | `link-file` | bind, connect |
| A thread's cwd (through D and an E removed at once) | `thread-cwd` | bind |
| `bindat` (through D and an E removed at once) | `at` | bind |
| A thread's cwd (straight into the socket's directory) | `thread-cwd-direct` | connect |
| `connectat` | `at-direct` | connect |
| `/proc/self/fd` | `proc-direct` | connect |
| A path relative to the cwd | `relative` | connect |
| Widened sockaddr | `widened` | connect |
| The process's chdir, a forked child | none (not used) | |

### Bind order

| Order | Route | Spelling | Used when |
|---|---|---|---|
| 1 | `standard` | the original path | up to the standard library length |
| 2 | `link-dir` | `/proc/<pid>/fd/<B's fd>/D/E/<file name>` | on Linux, `/proc` is usable and it fits |
| 3 | `link-dir` | `<B's real path>/D/E/<file name>` | it fits |
| 4 | `link-file` | `<B's real path>/D/E` | OSes whose bind follows a symlink |
| 5 | `thread-cwd` (`at` on FreeBSD) | `E/<file name>` (E removed at once) | Linux / Android, Apple OSes, FreeBSD |
| 6 | `ENAMETOOLONG` | | |

- 2 to 4 keep their spelling. While the socket lives, the spelling points to the same place as the original path, so upper libraries that remove by the `getsockname` spelling, DGRAM replies and operational tools work as with the original path
- link-dir comes before link-file. Unlinking by a link-dir spelling follows E and removes the original file (the same as the original path), and operational tools show the file name too. Unlinking by a link-file spelling only removes E and the socket file stays, and the file name does not show in the spelling
- link-file reaches whatever the file name's length, so bind on macOS and NetBSD reaches up to the file name limit (NAME_MAX, 255 bytes). It is not tried on the OSes measured not to follow. On OSes not yet measured it is tried, and if it fails with nothing at the original path, it is taken as "did not follow" and the next route is tried
- thread-cwd / at come after, for when the spellings of 2 to 4 do not fit. E is removed right after the bind, so the spelling reaches nothing. The spelling contains the random name that was removed, so resolved later it hits nothing, unless something of the same name happens to be in the cwd
- bind does not use proc-direct, relative, at-direct or widened (for the reasons in the table of [A bind's spelling stays in the kernel](#a-binds-spelling-stays-in-the-kernel))
- Whether the spelling can be used later is told by the `Spelling` that `bind_ex` and `resolve_for_bind` return (4 kinds: the original spelling, relative to the cwd, through B / D / E, reaching nothing)

### Connect order

| Order | Route | What it does |
|---|---|---|
| 1 | `standard` | the original path |
| 2 | Linux: `proc-direct` (`relative` if `/proc` is not usable)<br>Apple OSes: `relative` → `widened`<br>FreeBSD: `at-direct`<br>NetBSD, OpenBSD: `relative` | needs no write and no thread |
| 3 | `thread-cwd-direct` | moves a throwaway thread's cwd into the socket's directory and connects by the file name (Linux / Android, Apple OSes) |
| 4 | `link-file` | creates an E with 10 random characters right under B, connects by `<B's real path>/<E>`, and removes E at once |
| 5 | `ENAMETOOLONG` | |

- Routes needing no write and no thread come first. A one-off connect from a CLI usually ends here, and reaches even in a sandbox that cannot write to the base. relative and widened sometimes reach farther than the routes through the base
- thread-cwd-direct needs neither D nor E. A connect's spelling does not stay with the peer, so unlike bind there is no need to put a random name in between
- link-file is the last route, which reaches whatever the file name's length. It creates no D, creates E right under B, and removes it right after the connect, so no D or E is left in the process (when it creates B for the first time, that B is used as the process's B from then on)
- To connect to the same path repeatedly, use the spelling made once by `resolve_for_connect` every time and `cleanup` at the end

The file name reached in an ordinary environment (the thread cwd and `/proc` usable, the base writable at the OS's default). These are the values of the Rust, Python and Go implementations; the TypeScript implementation is shorter in places (the reach table).

| OS | bind | connect |
|---|---|---|
| Linux | up to 96 bytes (thread-cwd from 77) | up to 255 bytes |
| macOS | up to 255 bytes | up to 255 bytes |
| FreeBSD | up to 92 bytes (at) | up to 255 bytes |
| NetBSD | up to 255 bytes | up to 255 bytes |
| OpenBSD | up to 72 bytes | up to 255 bytes |

### Where the base is

B is created in the first of the following where it can be created. Places where the OS's cleaning removes dead D and protects live D come first.

| Order | Base | Why |
|---|---|---|
| 1 | `/tmp` | on Linux, systemd-tmpfiles removes dead D after 10 days, and live D are protected by flock. macOS does not remove live D |
| 2 | `$XDG_RUNTIME_DIR` | no cleaning by age; dead D stay until logout |
| 3 | `$TMPDIR` | dirhelper may remove D in macOS's `$TMPDIR` after 3 days, live ones too |
| 4 | the socket's directory | when it can be created in none of 1 to 3. The name is `.sockat.<10 random characters>` |

- Before using B, sockat checks that it is a real directory, owned by oneself, and not writable by others (including the group). It also checks that every directory from the root to B's parent is owned by root or by oneself, and is either not writable by others or sticky. If others can write to an ancestor, the parent can be swapped out along with everything in it
- If someone else has created `/tmp/sockat-<uid>` first and it fails the checks, that base is not used and the next base is tried. No B with another name is created instead, so things do not pile up in the base
- B and D are created with 0711. The real-path spelling of a B in `/tmp` can be followed by a peer of another uid too. `$XDG_RUNTIME_DIR` and macOS's `$TMPDIR` are 0700, so a B there is for the same uid only
- An app that wants to choose the base itself can pass the path of B in `Options.base`

### Keep, don't remove, and protect with flock

B, D and E are not removed while the socket is in use. The kernel remembers a bind's spelling for the life of the socket, so the spelling staying followable is a condition for working correctly.

To keep what is left from hitting an unrelated file later:

- D's name is random. With a counter, after the process exits, another process with the same PID and the same fd number could appear, and the same spelling would point to that process's socket
- While D lives it is protected by flock, and B and D are 0711, so the spelling does not later hit an unrelated file. A procB spelling cannot be followed after the process exits; a real-path spelling points to the same place until D is removed
- If a held B or D has been removed, it is created again on the next call. The fds of a dropped B or D are not closed but kept. If closed, the fd number is reused, and a procB spelling through that number would hit another directory

flock also protects D from the OS's cleaning. systemd-tmpfiles (v242 or later) skips a directory holding a flock, with everything under it. A live D can be removed only on Linux with systemd older than v242 (v239 of RHEL 8, etc.) and when B is in macOS's `$TMPDIR`. Even then the spelling only stops being followable; nothing dangerous happens.

### Cleanup is left to the OS's cleaning and an explicit `sweep`

sockat does not clean up B and D itself. The D of a dead process is removed by the OS's temporary-directory cleaning. Linux's `/tmp` after 10 days, `$XDG_RUNTIME_DIR` at the last logout or a reboot, and macOS's `/tmp` does not remove a directory containing a symlink, so until reboot. On FreeBSD, NetBSD and OpenBSD by default, they are not removed or are removed on reboot.

- What is left is small. Measured in 2 apps that use sockat, one test run's 12 D and 150 E came to 0 in `du`. What piles up is E (the number of binds) more than D (the number of processes that bound at a long path)
- Only when `sweep()` is called are the D whose lock has been released (D whose owner is dead) removed. The D of live processes are not removed. Measured, 292 D and 3035 E went to 0, and B stayed
- Where tests run over and over, the user calls `sweep()`, because macOS's `/tmp` keeps piling up until reboot

Why not remove automatically:

- Tools that put per-user sockets and temporary things in `/tmp` (ssh-agent, tmux, etc.) customarily leave others' leftovers to the OS's cleaning rather than removing them. Having the next process clean up is the form for caches that keep growing (Go's build cache, etc.), not for D and E, which take almost no space
- Listing B on every call adds steps and IO to resolve and connect
- flock tells whether D is alive, so there is no need for a mechanism that puts the PID in the name to guess whether it is alive

### Weaknesses of this form

- State grows outside the app's own place (`/tmp`, `$XDG_RUNTIME_DIR`, `$TMPDIR`). The default `bind`'s E and a dead process's D stay until the OS cleans them
- If someone else creates `/tmp/sockat-<uid>` first, sockat moves to the next base. On macOS it moves to the long `$TMPDIR`, so the reach shrinks
- A B in `/tmp` can be recreated by someone else under the same name after it is gone. A spelling is not used after it is cleaned up
- A procB spelling is longer by `/proc/<pid>/fd/<fd>/` plus D and E, and the file name reached on Linux is shorter than with thread-cwd
- Across an exec the fd holding D's flock is closed, and even if the inherited listener lives, D and E can be removed by `sweep()` or the OS's cleaning (the spelling only stops being followable). A procB spelling stops being followable at the exec
- If the process dies in the middle of thread-cwd / at, E is left in D (it is removed with D by the OS's cleaning)

## What was not adopted

| Idea | Why not |
|---|---|
| bind / connect in a forked child | the side effects (fd copies, `SIGCHLD`, `pthread_atfork`, another thread's `waitpid(-1)`, on connect the pid the peer sees) reach the whole process, and more users do not want them than do. If the parent does the listen of a bind, the side effects visible to the peer go away, but the invisible ones stay. Placed after thread-cwd-direct and link-file, it would only be used where neither threads nor B can be used |
| use the widened sockaddr for bind | the address is cut in the middle, which breaks the standard libraries of CPython and Go |
| no random name in a bind's spelling (`/proc/self/fd/<fd>/<file name>`, just the file name) | resolved later it hits an unrelated file. The upper library removes it, and the user cannot avoid it |
| clean up a bind's spelling within the call | upper libraries that remove by the `getsockname` spelling, DGRAM replies and operational tools do not reach the original path |
| open B, hold it by fd, then remove it and use it only through the fd in `/proc` (leaving nothing in the base) | nothing can be created inside a removed directory (`ENOENT`, measured) |
| put the PID in the name and have the next process clean up the leftovers | a process that inherits the listener across an exec keeps its PID and is not removed. With PID reuse, a way to check that a live process's things are not removed is needed |
| clean up when a process first uses B, or on every call | it adds steps. Temporary things in `/tmp` are customarily left to the OS's cleaning |
| register an exit handler that removes the process's own D at exit | a library would silently change how the whole process exits (it runs in a forked child too). Go has no such mechanism, so the languages would not match. It does not run on a crash, a kill or an exec |
| create a B with a random name in place of an occupied B | B would grow per process using long paths, and sometimes be removed neither by `sweep` nor by the OS's cleaning |
| have the default connect cache and reuse spellings | it creates hidden state in the process, with no visible time when it is cleaned up, and in a long-lived process symlinks pile up, one per destination. Those who want reuse use `resolve_for_connect` |
| put in the library's API a way for users to choose or combine routes, or functions that change a process-wide default | it would only lead to half-working use through poor combinations, and serves no purpose. A process-wide default is hidden state |
| return route names as a promise | adding or changing a route would be a breaking change. Branch on `Spelling` |

## Further

- How far each condition reaches: [the reach table](./reach/README.md)
- Using fork in your own app: [fork-cwd](./fork-cwd.md)
- How each route is built (for implementers): [SPEC-routes](../docs/SPEC-routes.md)
- The source of the promises: [specification](../docs/SPEC.md)
- Decision records: [docs/decisions](../docs/decisions/INDEX.md)
