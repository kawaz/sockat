# sockat specification

> English | [日本語](./SPEC-ja.md)

How sockat behaves, independent of the language. Every implementation follows it. The design decisions and the rejected alternatives are in [sockat-rs's DR-0001](https://github.com/kawaz/sockat-rs/blob/main/docs/decisions/DR-0001-long-socket-path-routes.md) (Japanese); what is specific to Rust (types, where `unsafe` lives, tokio) is in [sockat-rs's MANUAL](https://github.com/kawaz/sockat-rs/blob/main/docs/MANUAL.md).

## Terms

| Term | Meaning |
|---|---|
| standard | the language's standard library bind / connect for Unix domain sockets |
| limit | the length of `sun_path` − 1 byte (leaving room for the NUL) |
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
- A language that cannot build the fork route does not provide the `connect_any` variants; its README says "no fork route" in the table
- A language whose standard connect never blocks (Node.js etc.) provides one connect in the standard's own form, with no separate `_nonblocking`
- `connect` / `connect_nonblocking` return `ENAMETOOLONG` when they reach the fork route
- The `connect_any` variants connect even by forking when no other route can be used. The bool is `true` only when the fork route was taken. No pid is returned
- The two non-blocking variants make the socket non-blocking before connecting and return it that way. When the peer's backlog is full they fail without waiting
- A socket the implementation creates itself gets the same settings as one the language's standard creates (close-on-exec, `SO_NOSIGPIPE`, the listen backlog, etc.)
- The socket file is not removed when the listener is closed (as with the standard)

## Short paths

A path the language's standard accepts is handed to it unchanged. Nothing is added and no environment variable is read. A longer path goes to the routes. Most standards accept up to `sun_path` − 1 bytes (below); a language whose standard stops earlier (Java: `sun_path` − 2) uses its standard's own limit.

| OS | `sun_path` − 1 |
|---|---|
| Linux / Android / illumos | 107 bytes |
| macOS / iOS / FreeBSD / NetBSD / OpenBSD | 103 bytes |

## Routes for long paths and their order

A path over the limit is tried on the routes below, in this order per OS, and bound / connected on the first route that can be used.

| OS | Order tried |
|---|---|
| Linux / Android (`/proc` usable) | /proc |
| Linux / Android (`/proc` not usable) | relative path → symlink → fork |
| FreeBSD | bindat |
| macOS | relative path → widened sockaddr → symlink → fork |
| NetBSD / OpenBSD / illumos / other Unix | relative path → symlink → fork |

- A path over the limit whose last component is not a file name (`dir/`, `dir/.`, `dir/..`, `..`) is an invalid-argument error, and nothing is created
- No route changes the calling process's cwd

### The routes

| Route | How | Usable when |
|---|---|---|
| /proc | open the directory `O_PATH \| O_DIRECTORY` and hand `/proc/self/fd/<fd>/<file name>` to the standard | `/proc/self/fd/<fd>` can be stat'ed and the whole spelling is within the limit (a file name up to about 90 bytes) |
| bindat | open the directory `O_RDONLY` and pass the file name to `bindat(2)` / `connectat(2)` | FreeBSD. A file name over 103 bytes is `ENAMETOOLONG` |
| relative path | hand the path relative to the cwd to the standard. Only the string is rewritten; no `chdir` | the original path is absolute and the relative path is within the limit |
| widened sockaddr | pass the original path, failing that the relative path, in a sockaddr whose `sun_len` and address length are `2 + path length` | macOS. The path is at most 253 bytes. `EINVAL` / `ENAMETOOLONG` from the kernel means the route is not usable |
| symlink | create a short symlink in a base directory, hand the spelling through it, remove it at once | the spelling is within the limit (253 on macOS) and there is a safe base where the symlink can be created |
| fork | fork a child that `fchdir`s into the directory fd and binds / connects by the file name | only `bind` and the `connect_any` variants. The file name is within the limit (253 on macOS) |

### Building the relative path

1. If the path starts with a spelling of the cwd (`getcwd`, or `$PWD` when its `stat` `(st_dev, st_ino)` matches that of `.`), strip it, comparing whole components
2. Only when 1 is not within the limit, resolve the socket's directory and the cwd with `realpath` and build a spelling that climbs with `..`
3. Use the shorter. Before using it, check that the relative directory and the original directory have the same `(st_dev, st_ino)`
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

- For each candidate, check the spelling's length and the base's safety before creating anything. A candidate that fails gets nothing and the next is tried
- When the symlink cannot be created (no base, not writable, names exhausted, no random bytes), the next candidate is tried as well

### The fork route

1. The parent creates the socket, holds the directory fd and builds the sockaddr before forking. For a non-blocking connect it makes the socket non-blocking before the fork
2. The child does `fchdir(dirfd)` → `bind` / `connect` by the file name → `_exit(result)` (0 is success, 1–255 an errno)
3. The parent `waitpid`s for that pid only. The listen after a bind is done by the parent

- The child's section uses async-signal-safe calls only (no allocation, locks, or the language's cleanup)
- If `waitpid` fails with `ECHILD` (someone else reaped the status), read the result from the socket: for a bind whether `getsockname` holds a path, for a connect whether `getpeername` succeeds. A failure is a generic error
- How the directory is opened: `O_SEARCH` on macOS (`O_RDONLY` if the kernel answers `EISDIR` / `EINVAL`), the `O_PATH` fd from the /proc route on Linux, `O_RDONLY` elsewhere

## How a failing route is treated

- When a route actually binds / connects and fails (`ENOENT`, `EADDRINUSE`, `ECONNREFUSED`, etc.), that error is returned and no later route or base is tried
- The next one is tried only when the route itself cannot be used (too short, `/proc` not usable, the kernel refuses the widened sockaddr, the base is unsafe or the symlink cannot be created)
- `connect` / `connect_nonblocking` open the directory and then return `ENAMETOOLONG` just before the fork route. A missing directory is `ENOENT`

## Where a path stops being reached

When a path over the limit becomes `ENAMETOOLONG` (numbers in bytes).

| OS | `bind` | `connect` variants | `connect_any` variants |
|---|---|---|---|
| Linux (`/proc` present) | file name > 107 | file name does not fit the `/proc` spelling, relative path > 107, and no symlink | file name > 107, and no symlink |
| Linux (no `/proc`) | file name > 107 | relative path > 107, and no symlink | file name > 107, and no symlink |
| FreeBSD | file name > 103 | file name > 103 | file name > 103 |
| macOS | file name > 253 | both the original and the relative path > 253, and no symlink | file name > 253, and no symlink |
| NetBSD / OpenBSD / other BSD | file name > 103 | relative path > 103, and no symlink | file name > 103, and no symlink |
| illumos | file name > 107 | relative path > 107, and no symlink | file name > 107, and no symlink |

- With the symlink route through `/tmp`, a connect reaches the path whatever the directory depth and the file name length
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
| address the kernel reports | `getsockname` / `getpeername` return the spelling used for the bind (a relative path, `/proc/self/fd/...`, a symlink that no longer exists, the file name alone, a truncated path). The caller keeps the original path |
| directory looked up first | /proc, relative path, bindat and fork look up the directory, then pass the file name. A rename or symlink swap in between is not reflected. widened sockaddr and symlink behave as the standard |
| another thread's chdir | the relative route returns a generic error if the cwd stayed changed in between. A change and change back is not seen |
| leftover symlink | if the process dies before removing the symlink, `sockat.XXXXXXXXXX` is left in the base |

## Errors

| Situation | Error |
|---|---|
| no directory / nothing to connect to | `ENOENT` |
| a file already exists where bind would create the socket | `EADDRINUSE` |
| a socket file nobody listens on | `ECONNREFUSED` |
| backlog full | Linux: `EAGAIN` for a non-blocking connect (a blocking one waits); macOS: `ECONNREFUSED` |
| fits no route; for the `connect` variants also when only the fork route would reach it | `ENAMETOOLONG` |
| path over the limit that does not end with a name | invalid argument |
| path containing NUL | invalid argument |
| the cwd changed during the relative route | generic error |
| the forked child did not exit normally, or its status was reaped elsewhere and the socket was not bound / connected | generic error |

- OS errors are returned so that the errno can be read in the language's usual way
- Each implementation chooses the types for "invalid argument" and "generic error"

## What each implementation must do

- Follow the routes and order above. Skip a route the language cannot build (treat it as not usable and go on), and show it in the README as an OS × route table
- Keep the routes out of the public API. Tests force each route by calling it directly from inside the package
- Make the parts that read the environment (symlink base candidates, the location of `/proc/self/fd`, whether macOS takes the widened sockaddr) replaceable from tests
- Link this specification from the README and manual. Before introducing behavior that differs from it, change this specification first

## What implementations test

| Aspect | What to check |
|---|---|
| short path boundary | exactly the limit goes to the standard unchanged; one byte more goes to the routes (check the boundary with the standard itself) |
| location | on each route the socket file is created at the original path and nothing remains in the base |
| traffic | on each route data actually flows between the bound listener and the connected stream |
| standard types | the return values work as the standard types (in languages with async runtimes, hand them over and use them) |
| no retry on failure | `ENOENT` / `EADDRINUSE` / `ECONNREFUSED` are returned and nothing is created on later routes or bases (the later candidate directory's mtime is unchanged) |
| Linux without /proc | with the `/proc/self/fd` location replaced by an empty directory etc., relative path → symlink → fork is followed |
| symlink base | an unsafe base is skipped, a too deep `TMPDIR` falls back to `/tmp`, colliding names are skipped and the attempts stop at 16, the symlink is removed on success and on failure |
| connect and fork | the `connect` variants return `ENAMETOOLONG` when only the fork route reaches; the `connect_any` variants reach and return `true` |
| cwd | the cwd is unchanged after every route; a cwd change during the relative route is a generic error |
| fork | the peer pid behavior; reading the result with `SIGCHLD` set to `SIG_IGN` |
| macOS | a 253-byte path goes through the widened sockaddr |
| non-blocking connect | a full backlog fails without waiting |
| path not ending with a name, NUL | invalid argument, nothing created |
| address the kernel reports | reading it does not fail for a long path |

- The routes differ per OS, so run at least on macOS and Linux. Other Unixes run in CI VMs
- Tests that change process-wide settings such as the cwd or signal handling run inside a child process
- The fork route's child briefly holds copies of every fd, so create "a socket nobody listens on" in a separate process

## Open questions

- Android, Apple OSes other than macOS, and the peer credentials on NetBSD / OpenBSD / illumos are not checked
