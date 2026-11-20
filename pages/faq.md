# sockat Q&A

> English | [日本語](./faq-ja.md)

Questions that come up before using sockat, and their answers. The specification is [SPEC](../docs/SPEC.md); where a path is reached is in [the reach tables](reach/README.md).

Answers marked "after the rework" are about the design that rebuilds the routes ([issue](../docs/issue/2026-11-20-resolve-and-persistent-base.md), Japanese; not implemented yet).

## Basics

### If I shorten the path, do I still need sockat?

No. If you can choose the socket's path, putting it somewhere short is best. sockat is for when you cannot choose the path:

- The environment or a setting decides where it goes (the working directory of a container runtime, a deep state directory, etc.)
- You connect / send to a path the other side chose (passed in an environment variable such as `NOTIFY_SOCKET`)
- A library uses the path its caller passed as is

### What differs from the standard for a long path?

The spelling the kernel keeps (`getsockname`, the listener's address) is no longer the original path. Do not remove or inspect the file by that spelling. Remove it by the original path or with `discard()` ([What is lost in the SPEC](../docs/SPEC.md#what-is-lost)).

## Environment

### Does it work when `$TMPDIR` is long?

Yes. In the design after the rework, the base's spelling is `/proc/<pid>/fd/<fd>/…` on Linux (procB, independent of the length of `$TMPDIR`), and under `/tmp` (tmpB) on OSes without `/proc`. The spelling under `$TMPDIR` (dirB) is used only when it is short. Usually procB or tmpB is usable.

### What about PrivateTmp (`/tmp` isolated by systemd etc.)?

On Linux the procB spelling does not go through `/tmp`, so the peer can follow it even when either side has `/tmp` isolated. macOS has no `/proc`, and isolation like PrivateTmp is rare there. "No `/proc`, and `/tmp` isolated" is a rare combination.

### What about talking to a process with another uid?

A connect resolves the spelling itself, so the peer's uid does not affect whether it is reached. It matters only when the peer follows the bound side's spelling (a DGRAM reply etc.). Another uid cannot follow procB, nor a spelling under a base only the owner can enter (`/run/user/<uid>`, macOS's `$TMPDIR`). In the design after the rework, specifying `usable_cross_uid` chooses a spelling under a base another uid can follow too (under `/tmp` etc.).

### I want containers to talk through a shared volume

The operator decides where a shared volume is mounted, so put the socket at a short path. There is no reason to make it long.

### What about `ProtectProc=invisible` (systemd)?

It hides other users' processes. With the same uid the procB spelling can be followed.

## fork

### Does sockat fork?

Not after the rework. The side effects of fork (copies of every fd, `SIGCHLD`, a mix-up with `waitpid(-1)`, `pthread_atfork`, the pid the peer sees on connect) reach the whole process. Where giving up fork means no longer reaching, and how and with what care to fork in your own application, are in [fork-cwd](fork-cwd.md).

## DGRAM

### Can an unbound socket receive a reply?

No. An unbound socket has no address, so the receiver cannot name where to reply. A sender that wants replies binds too. The exceptions are `socketpair` (a pair connected from the start) and, on Linux with `SO_PASSCRED`, the automatic abstract name. All of these are OS behavior and do not depend on the language.

### Does a reply reach a sender bound to a long path?

Not with the current implementations (they clean up the spelling right after the bind). In the design after the rework it does while the spelling is alive (procB for the same uid, a spelling under `/tmp` for other uids too).

### Does a sender that wants replies need to bind to a long path?

Usually not. The sender chooses its own reply path, so it can put it somewhere short.

## Speed

### Is connecting to the same path many times fast?

After the rework, call `resolve_for_connect` once, use the spelling for as many connects as needed, and `cleanup` when done. The work of making the spelling (creating and removing the directory and the symlink in the base) happens once. The plain `connect` makes and cleans up the spelling on every call and keeps no state in the process.

### Is the plain `connect` heavy?

Usually not. It first tries the routes that need neither writes to a base nor a thread (Linux's `/proc/self/fd/<dirfd>/<name>`, macOS's relative path and widened sockaddr), and a one-off connect from a CLI normally ends there. It goes on to the route that makes a symlink in a base only when the file name is quite long and the thread cwd is unusable too.

### Why doesn't the plain `connect` cache the spelling?

It would put hidden state in the process, the caller could not see when it is cleaned up, and a long-lived process would pile up a symlink per destination. Use resolve to reuse a spelling.

## Cleanup

### When do I call `discard()`?

Before closing the listener. `discard()` removes the file only when the current path still has the bound file's `(st_dev, st_ino)`. While the listener is open the kernel holds the file and its number is not reused, but something removed and recreated after it is closed can get the same number on ext4 or BSD UFS / FFS and cannot be told apart ([findings](../docs/findings/2026-11-19-inode-reuse-after-close.md), Japanese).

### Is it dangerous that others can recreate a spelling after the base is cleaned up?

The standard is the same: once the file at the original path is removed, anyone who can write to that directory can recreate the same path. Do not use an old spelling or path after cleanup.
