# fork-cwd: a forked child moves into the directory to bind / connect

> English | [日本語](./fork-cwd-ja.md)

sockat does not use this technique (kawaz's ruling, 2026-11-20). The side effects of fork (fd copies, `SIGCHLD`, `waitpid(-1)`, `pthread_atfork`, the pid the peer sees on connect) reach the whole process rather than the library that was called, and most users do not want them. This document is for users who fork in their own application where sockat does not reach: the technique, its side effects, and where it reaches.

- Where sockat reaches: [reach](reach/README.md) (the "With fork-cwd" column links to the sections of this document)
- Decisions: [DR-0017](../docs/decisions/DR-0017-resolve-through-persistent-base.md) (not forking, why a bind spelling contains a random name), "the last resort and fork" in the [issue](../docs/issue/2026-11-20-resolve-and-persistent-base.md) (all Japanese)

## Technique

What does not fit `sun_path` is the path string, not the directory's depth. Moving a child process's cwd into the socket's directory (or into a directory holding a short name that points to it) lets it bind / connect with a short relative spelling. A process has one cwd, so only the forked child moves, leaving the calling process's cwd unchanged.

| Step | bind | connect |
|---|---|---|
| 1. The parent prepares | creates the socket and builds the sockaddr. Creates a directory D of its own, holds it by fd, and inside it creates a symlink R with a random name pointing to the socket's directory | creates the socket and builds the sockaddr. Opens the socket's directory and holds its fd. For a non-blocking connect, makes the socket non-blocking |
| 2. fork | same | same |
| 3. The child | `fchdir(Dfd)` → `bind(sock, "R/<file name>")` → `_exit(0 or errno)` | `fchdir(dirfd)` → `connect(sock, "<file name>")` → `_exit(0 or errno)` |
| 4. The parent | `waitpid`s for that pid only, cleans up R and D, then `listen`s | `waitpid`s for that pid only |

- The child and the parent share the same socket (fork copies the fd, but it refers to one socket). What the child binds / connects stays on the parent's socket
- For a bind, the parent always listens. If the child listens, the server peer a client sees is the dead child (measured 2026-11-18 on macOS and Linux; [DR-0017](../docs/decisions/DR-0017-resolve-through-persistent-base.md), Japanese)
- The bind spelling goes through R because the spelling the kernel keeps and returns from `getsockname` is relative to the cwd, and resolved later from another cwd it would hit an unrelated file of the same name ([DR-0017](../docs/decisions/DR-0017-resolve-through-persistent-base.md), Japanese). Once R is cleaned up, the spelling hits nothing. A connect's spelling is left nowhere on the peer, so it needs no R
- If `waitpid` fails with `ECHILD` (someone else reaped the status), read the result from the socket: for a bind whether `getsockname` holds a path, for a connect whether `getpeername` succeeds

File name reached (bytes):

| | Linux / Android / illumos | Apple OSes | BSD |
|---|---|---|---|
| bind (`R/<file name>`) | 96 | 92 | 92 |
| connect (`<file name>`) | 107 | 253 (when the child uses the widened sockaddr; 103 if the kernel does not take it) | 103 |

## Side effects

| Scope | Side effect |
|---|---|
| visible to the peer (connect only) | the peer pid the server sees is that of the exited child. uid / gid are the caller's<br>Linux's `SO_PEERCRED` keeps the child's pid<br>macOS's `LOCAL_PEERPID` turns into the caller's pid once the caller sends |
| not visible to the peer (bind and connect) | until it exits, the child holds copies of every fd. A socket or pipe another thread closes meanwhile stays open, delaying the EOF the peer sees<br>the parent gets `SIGCHLD`<br>`pthread_atfork` handlers run<br>monitoring tools (process lists, audit) see a short-lived child<br>another thread's `waitpid(-1)` or `SIGCHLD` handler may reap the child and mix up the result |
| large processes | fork copies the page tables, so it takes longer for a process with a large virtual memory (not measured)<br>with Linux's `vm.overcommit_memory=2` (strict), fork can fail with `ENOMEM` when the child's commit cannot be reserved. Even with the default `0`, it can be refused when a lot of memory is in use (not verified) |

- A bind has no side effect visible to the peer. The child only binds and the parent listens, so the server's peer information a client sees (macOS's `LOCAL_PEERPID` / `LOCAL_PEEREPID` / audit token, Linux's `SO_PEERCRED` / `SO_PEERPIDFD`) is the parent's from before any send (measured 2026-11-18; [DR-0017](../docs/decisions/DR-0017-resolve-through-persistent-base.md), Japanese)
- On connect the peer pid is the child's, so a forked connect cannot be used when the server authorizes or logs by the peer's pid

## Doing it in your own application

- Use only async-signal-safe calls in the child. `fchdir`, `bind`, `connect` and `_exit` are async-signal-safe (Linux's signal-safety(7); `fchdir` was added in POSIX.1-2008 TC1). No allocation, locks, printf, or the language's cleanup (`exit`, destructors, exceptions): in a multithreaded process, a lock another thread held stays locked in the child
- Build the sockaddr and the path string before the fork
- The parent `waitpid`s for the forked pid (retrying on `EINTR`). Do not use `waitpid(-1)` in other threads
- In a program that sets `SIGCHLD` to `SIG_IGN`, the child is reaped automatically and `waitpid` gives `ECHILD`. Handle it as in "read the result from the socket" above
- For a non-blocking connect, make the socket non-blocking before the fork. `EINPROGRESS` reaches the parent as the child's exit code

Per language:

| Language | Feasible | Why |
|---|---|---|
| C / C++ | yes | `fork` and the steps above can be written directly |
| Rust | yes (`unsafe`) | use `libc::fork`, with no allocation or panic in the child (std's `Command` only does fork + exec). The current sockat-rs implements these steps (in the conformance scene `no-thread-cwd-no-proc-bind`, only rs reaches through fork-cwd; measured 2026-11-20) |
| Python | hard | the child of `os.fork()` keeps running the interpreter and cannot avoid bytecode execution, reference counting or allocation (the section cannot be made async-signal-safe). CPython warns with `DeprecationWarning` on `os.fork()` in a multithreaded process (measured on 3.15.2). To be sure, write the part from fork to `_exit` in a C extension. sockat-py has no fork route |
| Go | no (not with fork alone) | the runtime is multithreaded and `syscall.ForkExec` only has the form that execs right after the fork. The runtime does not run in a raw forked child ("routes outside the SPEC" in sockat-go's README). Instead, starting a small helper program with the socket's directory as its cwd (`os/exec`'s `Cmd.Dir`), passing it the socket's fd (`ExtraFiles`) and having it bind / connect by the file name is possible (fork + exec, so it costs even more; not verified) |

## Where fork-cwd reaches

Where the "With fork-cwd" column of [the reach tables](reach/README.md) has a link. Numbers are bytes, estimated as in the tables (base lengths are typical values).

### bind-linux-without-thread-cwd

A bind on Linux / Android that cannot use the thread cwd.

| Item | Content |
|---|---|
| When | a seccomp filter is in place (the default of docker and systemd's `SystemCallFilter=`), `unshare(CLONE_FS)` is refused, or no thread can be created |
| Where sockat reaches | default bind: with `/proc` usable, proc up to a file name of 79; otherwise not reached<br>bind_ex: link-dir on procB up to 74. Without `/proc`, link-dir up to 71 when a base is writable (61 on dirB in `$XDG_RUNTIME_DIR`, 71 on tmpB in `/tmp`)<br>resolve_for_bind: as bind_ex |
| Where fork reaches | a file name up to 96 (whatever the base; D can be created in the socket's directory too) |
| Its own side effects | none visible to the peer (the parent listens). Where a seccomp filter refuses `fork` / `clone`, fork-cwd cannot be used either |

### bind-apple-without-thread-cwd

A bind on macOS and the other Apple OSes that cannot use the thread cwd (`pthread_fchdir_np` is absent or fails) nor a symlink in a base.

| Item | Content |
|---|---|
| When | `pthread_fchdir_np` is absent or fails, and in addition neither `$TMPDIR` nor `/tmp` is writable, or both are too long for the spelling to fit. On the other Apple OSes, when bind does not follow a symlink, this applies whatever the base |
| Where sockat reaches | default bind: symlink-file, for any file name length when a base exists<br>bind_ex: link-file (dirB, tmpB), for any file name length when a base exists<br>without a base, neither reaches |
| Where fork reaches | a file name up to 92 |
| Its own side effects | none visible to the peer (the parent listens). Do not call Objective-C or CoreFoundation in the child (using them in a child that does not exec after fork is unsafe; not verified) |

### bind-without-thread-cwd-means

A bind on the BSDs other than FreeBSD, illumos and other Unix, where neither the thread cwd, nor `bindat`, nor `/proc` is usable.

| Item | Content |
|---|---|
| When | NetBSD, and other Unix whose bind follows a symlink: when there is no base<br>OpenBSD, illumos, and other Unix that does not follow: always (bind does not follow a symlink, and there is no means) |
| Where sockat reaches | default bind: NetBSD reaches through symlink-file for any length when a base exists. OpenBSD and illumos do not reach<br>bind_ex / resolve_for_bind: NetBSD reaches through link-file when a base exists. OpenBSD reaches a file name of 67, illumos 71, through link-dir on tmpB (when `/tmp` is writable) |
| Where fork reaches | a file name up to 92 (96 on illumos) |
| Its own side effects | none visible to the peer (the parent listens) |

- FreeBSD reaches a file name of 92 with `bindat` (at), and fork-cwd also reaches 92, so fork extends nothing there

### connect-without-place-or-thread-cwd

A connect not reached by the routes that need neither writing nor a thread, that cannot use the thread cwd (or the file name is too long for it), and that has no base for link-file. Typical for a short-lived CLI connecting inside a sandbox.

| Item | Content |
|---|---|
| When | all of the following<br>on Linux with `/proc` usable the file name is over 90; on other OSes neither the original nor the relative path fits the sockaddr (the widened sockaddr on Apple OSes)<br>the thread cwd is not usable (always on FreeBSD, NetBSD, OpenBSD, illumos and other Unix)<br>B can be created in none of `$XDG_RUNTIME_DIR`, `$TMPDIR` and `/tmp`, and on Linux with `/proc` usable the socket's directory is not writable either |
| Where sockat reaches | Linux (with `/proc`): proc-direct up to a file name of 90<br>others: relative up to a relative path of 107 / 103, and on Apple OSes widened up to 253 (Go cannot build widened) |
| Where fork reaches | a file name up to 107 (Linux / illumos), 103 (BSD, other Unix), 253 (Apple OSes, when the child uses the widened sockaddr) |
| Its own side effects | the peer pid the server sees is that of the exited child. Cannot be used with a server that authorizes or logs by the peer's pid |
