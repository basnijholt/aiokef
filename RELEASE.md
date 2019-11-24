# Release Instructions

This document guides a contributor through creating a release of aiokef.

## Preflight checks

### Ensure all tests pass

Locally you can run `tox` to check that all tests pass, and check that tests
against all supported environments are passing also by checking aiokef's
[GitHub actions](https://github.com/basnijholt/aiokef/actions?query=branch%3Amaster+workflow%3Atests).

#### Verify that `AUTHORS.md` is up-to-date

The following command shows the number of commits per author since the last
annotated tag:
```
t=$(git describe --abbrev=0); echo Commits since $t; git shortlog -s $t..
```

## Make the release

Run

```
bumpversion release  # bump version from .devX to release version
git push --tags      # push tagged release to upstream
flit publish         # publish to PyPI
bumpversion patch    # add .devX tag
```

## Start work on the next release

Run

```
bumpversion minor
```

To start work on the next release
