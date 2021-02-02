# apx-changelog

PyPI package to generate changelogs from a git repository.

For examples, look at changelogs of the following projects:

 - https://github.com/uavos/apx-gcs


## Usage

Must be run in the root of a git repository.

```text
usage: changelog.py [-h] --ref REF
                    [--comments]
                    [--out OUT]
                    [--releases RELEASES] 
                    [--log LOG]
                    [--title TITLE]
                    [--ver VER]

Changelog generator for git repository

optional arguments:
  -h, --help           show this help message and exit
  --ref REF            git ref from which to collect changes
  --comments           append comments section
  --out OUT            output filename to store collected changelog markdown text
  --releases RELEASES  releases repository name if different
  --log LOG            filename of changelog file to update
  --title TITLE        project title for changelog file updates
  --ver VER            project version X.Y[.Z] for changelog file updates
  --mkver MKVER        filename to store current version (X.Y.Z)
```

The utility will parse commits and include commit messages starting with the following keywords:

- `feat`: New Features
- `fix`: Bug Fixes
- `refactor`: Refactoring
- `perf`: Performance Enhancements
- `opt`: Optimizations
- `docs`: Documentation Changes
- `chore`: Administration and Chores

Example commit message:

```text
fix: a fix of a bug (closes user/repo#123)
```

Will produce the following section in the changelog output:

```text
# Bug Fixes

* a fix of a bug (closes [`123`](https://github.com/user/repo/issues/123))

```

The issue `user/repo` can be omitted, then the link will point to the current repository.

A multi-line commit message will add `comments` section in changelog, displaying full text of the commit message.

The changelog file specified with the `--log` option can have a template header, written in [`/.changelog`](.changelog) file.

## Repository tags

The git repository can have tags in the format `v1.2` to simplify versioning (`vZ.Y.Z`) using `git.describe('--always', '--tags', '--match=v*.*')`.

Releases must be tagged in the format `release-X.Y.Z`.
