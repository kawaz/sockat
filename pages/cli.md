# The sockat command

> English | [日本語](./cli-ja.md)

A command that turns a Unix domain socket path that is too long into a path to the same socket that fits the OS limit. Use it to hand a long path to a program that cannot embed sockat, or to try sockat out before embedding it in your app.

## Install

```sh
brew install kawaz/tap/sockat
```

or:

```sh
cargo install sockat-cli
```

Prebuilt binaries per OS are on the [releases page](https://github.com/kawaz/sockat-rs/releases). The command is named `sockat`.

## Hand the path to another command

```sh
curl --unix-socket "$(sockat /very/long/…/app.sock)" http://localhost/
```

Standard output is the path alone, on one line. The same path always gives the same result. The path works for both bind and connect, and there is nothing to clean up.

## See what path you get

```console
$ sockat /very/long/…/app.sock
/private/tmp/sockat-501/f21ddd85c65f/app.sock

$ sockat --json /very/long/…/app.sock
{
  "path": "/private/tmp/sockat-501/f21ddd85c65f/app.sock",
  "bytes": 45,
  "limit": 103,
  "original": "/very/long/…/app.sock",
  "original_bytes": 145,
  "route": "link-dir",
  "link": "/private/tmp/sockat-501/f21ddd85c65f",
  "target": "/very/long/…",
  "for": ["bind", "connect"],
  "warnings": []
}
```

sockat is not a shortener; it gives a path that fits the limit (`limit`). The path may not look short, but it always fits. A path that already fits is printed unchanged.

## Give a relative path

```console
$ cd /very/long/…
$ sockat ./app.sock
/private/tmp/sockat-501/f21ddd85c65f/app.sock
```

A relative path is printed as an absolute one. Another process using it from another directory still reaches the same socket.

## When the file name is very long

```console
$ sockat /very/long/…/nnnn…nnnn.sock
/private/tmp/sockat-501/7e6cc6be310a
sockat: warning: this path is for connect; not recommended for bind (unlinking this path removes only the symlink, not the socket file)
```

When the file name itself is long, sockat prints a path for connect. It is not recommended for bind (the warning says why).

- For connect, add `--for connect` and no warning is printed
- For bind, add `--for bind`. It is an error when no path usable for bind can be made on that OS

## Change where the links go

```sh
sockat --base /tmp/my-app-1000/sockat /very/long/…/app.sock
```

sockat puts a small symlink in `/tmp/sockat-<uid>/` and prints a path through it. `--base` moves that place to a directory of your own.

## Clean up what is left

```sh
sockat sweep
```

Removes what programs that embed sockat left in the temporary directory and no longer use. The symlinks the `sockat` command placed are reused, so they are kept.

## Shell completion

```sh
sockat completion zsh
```

Prints the completion script to standard output.

## Environment

| Variable | Use |
|---|---|
| `XDG_RUNTIME_DIR` | the next place for the base when it cannot be made in `/tmp` |
| `TMPDIR` | the place after that |

## Exit status

| Exit status | When |
|---|---|
| 0 | the path was printed |
| 1 | no path could be made (the directory is missing, it does not fit the limit, etc.). The reason goes to standard error |
| 2 | wrong arguments |
