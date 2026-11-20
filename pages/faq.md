# sockat Q&A

> English | [日本語](./faq-ja.md)

Questions that come up before using sockat, and their answers. The specification is [SPEC](../docs/SPEC.md); where a path is reached is in [the reach tables](reach/README.md).

The answers are about the design of [DR-0017](../docs/decisions/DR-0017-resolve-through-persistent-base.md) (Japanese). Each language's implementation is being rebuilt to this design; the behavior of the published versions is in each language repository's README.

## Basics

### If I shorten the path, do I still need sockat?

No. If you can choose the socket's path, putting it somewhere short is best. sockat is for when you cannot choose the path:

- The environment or a setting decides where it goes (the working directory of a container runtime, a deep state directory, etc.)
- You connect / send to a path the other side chose (passed in an environment variable such as `NOTIFY_SOCKET`)
- A library uses the path its caller passed as is

### What differs from the standard for a long path?

The spelling the kernel keeps (`getsockname`, the listener's address) is not the original path but a spelling through D and the symlink E inside the base B. While the spelling lives it points to the same place as the original path, but depending on its kind, removing by it may leave the file, or it may reach nothing. Whether the spelling can be used later is told by the `Spelling` that `_ex` returns. Remove the file by the original path or with `remove()` ([Patterns not to use in the SPEC](../docs/SPEC.md#patterns-not-to-use)).

## Environment

### Does it work when `$TMPDIR` is long?

Yes. B is created in `/tmp` first (the first of `/tmp` → `$XDG_RUNTIME_DIR` → `$TMPDIR` → the socket's directory where it can be created). The spelling is `/proc/<pid>/fd/<fd>/…` on Linux (procB, independent of the base's length), and B's real path elsewhere (short under `/tmp`). `$TMPDIR` is used only when B can be created neither in `/tmp` nor in `$XDG_RUNTIME_DIR`.

### What about PrivateTmp (`/tmp` isolated by systemd etc.)?

On Linux the procB spelling does not go through `/tmp`, so the peer can follow it even when either side has `/tmp` isolated. macOS has no `/proc`, and isolation like PrivateTmp is rare there. "No `/proc`, and `/tmp` isolated" is a rare combination. Whether the peer can follow it is told by `usable_with_private_tmp` of `Spelling`.

### What about talking to a process with another uid?

A connect resolves the spelling itself, so the peer's uid does not affect whether it is reached. It matters only when the peer follows the bound side's spelling (a DGRAM reply etc.). Another uid cannot follow procB, nor a spelling under a base only the owner can enter (`/run/user/<uid>`, macOS's `$TMPDIR`). Specifying `Options.usable_cross_uid` chooses the spelling of a B in a base another uid can follow too (`/tmp` etc.). When that cannot be met, it does not fall back to a spelling that does not meet it but goes on to routes such as the thread cwd (the spelling is `Dangling`), so check the resulting `Spelling`.

### I want to choose the base myself

Pass the path of B itself to `Options.base` (e.g. `/tmp/app-<uid>/sockat`). sockat only creates a D per process inside it, and leaves cleaning B to the app. When B fails the checks it is an error, and it does not fall back to the automatic bases.

### I want containers to talk through a shared volume

The operator decides where a shared volume is mounted, so put the socket at a short path. There is no reason to make it long.

### What about `ProtectProc=invisible` (systemd)?

It hides other users' processes. With the same uid the procB spelling can be followed.

## fork

### Does sockat fork?

No. The side effects of fork (copies of every fd, `SIGCHLD`, a mix-up with `waitpid(-1)`, `pthread_atfork`, the pid the peer sees on connect) reach the whole process. Where only a fork reaches, and how and with what care to fork in your own application, are in [fork-cwd](fork-cwd.md).

## DGRAM

### Can an unbound socket receive a reply?

No. An unbound socket has no address, so the receiver cannot name where to reply. A sender that wants replies binds too. The exceptions are `socketpair` (a pair connected from the start) and, on Linux with `SO_PASSCRED`, the automatic abstract name. All of these are OS behavior and do not depend on the language.

### Does a reply reach a sender bound to a long path?

Yes, while the spelling lives (procB for the same uid, B's real path in `/tmp` for other uids too). It does not with a spelling bound through the thread cwd etc. (`Dangling`), nor after `cleanup`.

### Does a sender that wants replies need to bind to a long path?

Usually not. The sender chooses its own reply path, so it can put it somewhere short.

## Speed

### Is connecting to the same path many times fast?

Call `resolve_for_connect` once, use the spelling for as many connects as needed, and `cleanup` when done. The work of making the spelling (creating and removing the symlink in the base) happens once. The default `connect` keeps no spelling and no D or E in the process (it reuses only B and its fd).

### Is the default `connect` heavy?

Usually not. It first tries the routes that need neither writes to a base nor a thread (Linux's `/proc/self/fd/<dirfd>/<name>`, macOS's relative path and widened sockaddr, FreeBSD's `connectat`), and a one-off connect from a CLI normally ends there. Next it tries a throwaway thread's cwd. It goes on to the route that makes a symlink right under the base B, connects and removes it at once, only when the file name is quite long and the thread cwd is unusable too.

### Why doesn't the default `connect` cache the spelling?

It would put hidden state in the process, the caller could not see when it is cleaned up, and a long-lived process would pile up a symlink per destination. Use resolve to reuse a spelling.

## Cleanup

### What does the default `bind` leave behind?

For a long path, it leaves the process's D and an E pointing to the socket's directory or file in the base B (when bound through the thread cwd etc., E is removed at once and only D stays). The default `bind` returns no way to clean up, so E stays until the process exits and is removed with D by the OS's temporary-directory cleaning (10 days for Linux's `/tmp`, until reboot for macOS's `/tmp`). To clean up, use `remove()` / `cleanup()` of `_ex`, or resolve. The D of dead processes are removed by calling `sweep()` (`sweep_base(path)` for those in the B of `Options.base`).

### When do I call `remove()`?

Before closing the listener. `remove()` removes the file only when the current path still has the bound file's `(st_dev, st_ino)` (it does not close the listener). While the listener is open the kernel holds the file and its number is not reused, but something removed and recreated after it is closed can get the same number on ext4 or BSD UFS / FFS and cannot be told apart ([findings](../docs/findings/2026-11-19-inode-reuse-after-close.md), Japanese).

### Is it dangerous that others can recreate a spelling after the base is cleaned up?

The standard is the same: once the file at the original path is removed, anyone who can write to that directory can recreate the same path. Do not use an old spelling or path after cleanup.
