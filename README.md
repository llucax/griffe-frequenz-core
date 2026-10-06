# Griffe Extensions for frequenz-core

[![Build Status](https://github.com/frequenz-floss/griffe-frequenz-core/actions/workflows/ci.yaml/badge.svg)](https://github.com/frequenz-floss/griffe-frequenz-core/actions/workflows/ci.yaml)
[![PyPI Package](https://img.shields.io/pypi/v/griffe-frequenz-core)](https://pypi.org/project/griffe-frequenz-core/)
[![Docs](https://img.shields.io/badge/docs-latest-informational)](https://frequenz-floss.github.io/griffe-frequenz-core/)

## Introduction

A collection of [Griffe](https://mkdocstrings.github.io/griffe/) extensions
that teach [mkdocstrings](https://mkdocstrings.github.io/) about
[`frequenz-core`](https://github.com/frequenz-floss/frequenz-core-python)
helpers.

Some of those helpers express information that Griffe cannot recover from
static analysis alone, so the API documentation generated for code using them
comes out incomplete. Each extension here fills one of those gaps, and new
ones are added as more helpers need the same treatment.

The first gap covered is deprecation. `frequenz-core` marks some APIs as
deprecated through a function call instead of a decorator, which neither the
`@deprecated` decorator support in Griffe nor
[`griffe-warnings-deprecated`](https://mkdocstrings.github.io/griffe-warnings-deprecated/)
can detect.

The extensions match fully qualified names as strings and never import
`frequenz-core`, so this package does not depend on it and can document any
project that uses those helpers.

## Installation

Add `griffe-frequenz-core` to the dependencies your documentation is built
with, next to `mkdocstrings`. Then enable each extension you want by its module
path, in the `extensions` option of the mkdocstrings Python handler.

## Documenting deprecations

The `griffe_frequenz_core.deprecations` extension documents the deprecations
`frequenz-core` expresses through a call. It is meant to run next to
`griffe-warnings-deprecated`, which documents the ones expressed through a
decorator:

```yaml
plugins:
  - mkdocstrings:
      handlers:
        python:
          options:
            extensions:
              - griffe_warnings_deprecated
              - griffe_frequenz_core.deprecations
```

Its defaults match `griffe-warnings-deprecated`, so with this configuration
both kinds of deprecation are rendered the same way. Every recognized
deprecation gets:

- a `deprecated` label,
- its notice stored in the object's `deprecated` field,
- an admonition with the notice, at the top of its docstring.

The notice follows the [deprecations
guide](https://github.com/frequenz-floss/docs/blob/v0.x.x/python/deprecations.md):
the runtime warning is written for a terminal, and the notice for the
documentation, so it says since which version the object is deprecated and
links what to use instead, without repeating the object's name. Where the
helper's arguments say that, the notice is generated from them; everywhere
else, it is written by hand, as a `Deprecated:` section in the docstring,
which always replaces the generated one.

When a notice can't say everything the guide asks for, because an argument
cannot be read statically or because the helper only has the runtime
warning, the object still gets one, saying as much as is known, and a warning
is logged, so a strict build fails until the notice is written by hand.

If you have a custom admonition style for deprecations, you can set the `kind`
option to match it.

```yaml
plugins:
  - mkdocstrings:
      handlers:
        python:
          options:
            extensions:
            - griffe_warnings_deprecated:
                kind: deprecated
            - griffe_frequenz_core.deprecations:
                kind: deprecated
```

### Recognized frequenz-core helpers

| `frequenz-core` helper                        | Written as                          | Documented object       |
|-----------------------------------------------|-------------------------------------|-------------------------|
| `frequenz.core.warnings.deprecated_aliases()` | the value of a module `__getattr__` | every alias in the table|
| `frequenz.core.warnings.DeprecatedAlias`      | an entry in that table              | that alias              |
| `frequenz.core.enum.deprecated_member()`      | the value of an enum member         | the enum member         |
| `frequenz.core.enum.DeprecatedMember`         | the value of an enum member         | the enum member         |

Calls are matched by the fully qualified path Griffe resolves from the
module's imports, so an import under another name, such as
`from frequenz.core.enum import deprecated_member as dm`, is recognized too.

### Deprecated module aliases

`deprecated_aliases()` keeps a moved or renamed symbol importable under its old
name through a module `__getattr__`, with the names declared again under
`TYPE_CHECKING` for type checkers. Each alias is a `DeprecatedAlias` entry with
where the symbol is now, as `new_module`, `new_name` or both, and either the
version it is deprecated since or a message of its own:

```python
from typing import TYPE_CHECKING, TypeAlias

from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases

if TYPE_CHECKING:
    from mypkg.newmod import Gadget as _Gadget
    from mypkg.newmod import Widget as _Widget

    Widget: TypeAlias = _Widget
    """A widget that does widget things."""

    Doohickey: TypeAlias = _Gadget
    """A gadget, formerly known as `Doohickey`."""
else:
    __getattr__ = deprecated_aliases(
        __name__,
        DeprecatedAlias("Widget", new_module="mypkg.newmod", since="v1.2.0"),
        DeprecatedAlias(
            "Doohickey", new_module="mypkg.newmod", new_name="Gadget", since="v1.3.0"
        ),
        DeprecatedAlias("Thingamajig", new_name="Widget", since="v1.4.0"),
    )
```

If this is `mypkg.oldmod`, the documentation of `Widget` starts with an
admonition saying "Deprecated since v1.2.0. Use `mypkg.newmod.Widget`
instead.", with the replacement linked, and its value is rendered as
`mypkg.newmod.Widget` instead of the private `_Widget`. `new_name` renames the
symbol as well as moving it, so `Doohickey` points at `mypkg.newmod.Gadget`, and
an entry without `new_module` points at another name in `mypkg.oldmod` itself,
so `Thingamajig`'s notice says "Use `Widget` instead.", linking
`mypkg.oldmod.Widget` by its name alone.

The details of what gets documented:

- Every entry is marked, whether or not its name is declared under
  `TYPE_CHECKING`. A name with no declaration gets a new module attribute, so
  it still appears in the documentation.
- The notice is the `default_message` option, with `{since}` replaced as
  written. It only appears in the documentation, right where the alias is, so
  unlike the runtime warning it doesn't repeat which symbol is deprecated, and
  it links the target in code font.
- An entry's `message` is only its runtime warning, so it doesn't change the
  notice. An entry giving `message` instead of `since` can't say since which
  version it is deprecated, so its notice only says what to use instead, and a
  warning is logged: write the notice by hand in the docstring of the name
  declared under `TYPE_CHECKING`.
- The target is linked with a normal cross-reference, so one that cannot be
  resolved is reported by `mkdocs-autorefs`. For a target in another project,
  add that project's `objects.inv` URL to the Python handler's `inventories`.
- Entries are read one by one, so one that cannot be read is skipped without
  affecting the others. The other arguments of the call, such as `category`
  and `stacklevel`, don't change the documentation.
- The call has to be assigned directly to the module's `__getattr__`. A
  `def __getattr__()` that calls `deprecated_aliases()` inside is not
  recognized, and neither is a `__getattr__` built by anything else.

### Deprecated enum members

`deprecated_member()`, or the `DeprecatedMember` class it returns, wraps the
value of an enum member to deprecate it:

```python
from frequenz.core.enum import DeprecatedMember, Enum, deprecated_member


class TaskStatus(Enum):
    OPEN = 1
    PENDING = deprecated_member(1, "PENDING is deprecated, use OPEN instead")
    WAITING = DeprecatedMember(1, "WAITING is deprecated, use OPEN instead")
```

Both members are marked, and their value is rendered as the real value instead
of the wrapper call, so the documentation shows `PENDING = 1`. The wrapper
only carries the runtime warning, so the notice is written by hand; without
one, the runtime warning is shown as the notice, rendered as Markdown, and a
warning is logged.

A recognized wrapper still marks the member when its message is held in a
variable or returned by a helper. Its value is unwrapped as written, and,
without a hand-written notice, it gets a generic one, "Deprecated. It will be
removed in a future release.", and a warning is logged.

### Hand-written admonitions

When the docstring of a deprecated object already has a deprecation
admonition, the extension doesn't add one, and only adds the label and the
`deprecated` field. It moves the hand-written one to the top of the
docstring, where a generated one goes, since a docstring has to start with its
summary. It counts as a deprecation admonition if it is a `Deprecated:`
section, or an admonition whose title matches the `title` option, ignoring
case. Write one wherever the helper can't generate a complete notice, or when
the generated one is not enough, for example to point at a migration guide:

```python
if TYPE_CHECKING:
    Widget: TypeAlias = _Widget
    """A widget that does widget things.

    Deprecated:
        Deprecated since v1.2.0. Use [`mypkg.newmod.Widget`][] instead, as
        explained in the [migration guide](https://example.com/migration).
    """
```

### Known limitations

Griffe reads the source without running it:

- Alias names, `new_module`, `new_name` and `since` values must be string
  literals written in the call to be documented. An alias whose name is not a
  literal is left unmarked. Any other non-literal argument leaves out of its
  notice what it would have said, since which version or what to use instead,
  and its value is only rewritten when the target is known. The `message` is
  never read.
- An enum message must be a string literal to be shown when there is no
  hand-written notice. A constant, helper call, f-string or string joined with
  `+` is not evaluated; adjacent literals, which Python joins by itself, are
  fine. The enum member is still marked, with a generic notice, and its value
  is unwrapped.
- Each alias entry must be a `DeprecatedAlias(...)` call written among the
  arguments of `deprecated_aliases()`. An entry held in a constant, as in
  `deprecated_aliases(__name__, WIDGET)`, or unpacked, as in
  `deprecated_aliases(__name__, *ALIASES)`, cannot be read, and is left
  unmarked.
- The arguments of `deprecated_member()`, `DeprecatedMember` and
  `DeprecatedAlias` must be written out, not unpacked from `*args` or
  `**kwargs`. A member defined as `deprecated_member(*ARGS)` is marked with a
  generic message and its value is left as written. An alias entry with
  unpacked keyword arguments only has its name read, and one with unpacked
  positional arguments is left unmarked.

- Calls are read the way the runtime binds their arguments, and one that
  doesn't bind is skipped, but argument values are not validated any further:
  documenting the code is not linting it, and its own tests catch a call that
  fails when the module is imported.

Every one of these cases is logged as a warning, so `mkdocs build --strict`
fails instead of the documentation quietly showing less than the code says or
the guide asks for: a notice that doesn't say since which version or what to
use instead, a runtime warning shown as the notice, a value left as written,
or a deprecation left unmarked. A hand-written admonition rules out the ones
about the notice, since the documentation is complete then. Why something
could not be read is logged at debug level, which `mkdocs build --verbose`
shows. A replacement that cannot be linked is reported by `mkdocs-autorefs` in
the same way.

### Options

| Option                     | Default                                     | Effect                                                                  |
|----------------------------|---------------------------------------------|-------------------------------------------------------------------------|
| `kind`                     | `danger`                                    | The kind of the admonition, which is also its CSS class.                |
| `title`                    | `Deprecated`                                | The title of the admonition. An empty title or `null` renders none.     |
| `label`                    | `deprecated`                                | The label added to deprecated objects. `null` adds none.                |
| `alias_table_functions`    | `frequenz.core.warnings.deprecated_aliases` | The paths of the functions that build a module `__getattr__`.           |
| `alias_classes`            | `frequenz.core.warnings.DeprecatedAlias`    | The paths of the callables that build one alias entry.                  |
| `member_wrapper_functions` | `frequenz.core.enum.deprecated_member`, `frequenz.core.enum.DeprecatedMember` | The paths of the callables that wrap a deprecated enum member's value. |
| `default_message`          | `Deprecated since {since}. Use {new_link} instead.` | The notice of an alias: `{new}` is the target's path, `{new_link}` a code font link to it, by its name alone if it is in the same module. |
| `show_target`              | `true`                                      | Render an alias' value as its target, not the private name.             |

The three path options are lists, and setting one replaces its default. To match
a helper of your own as well as the `frequenz-core` one, list both:

```yaml
extensions:
  - griffe_frequenz_core.deprecations:
      alias_table_functions:
        - frequenz.core.warnings.deprecated_aliases
        - mypkg.compat.moved_to
```

A helper of your own is read with the signature of the one it stands in for.
For an alias table that is `deprecated_aliases(module, /, *aliases)`: every
positional argument after the module is an entry, and keyword arguments are
ignored. For an alias entry it is `DeprecatedAlias(name, /, *, new_module=None,
new_name=None, since=None, message=None)`: the name positionally, and by keyword
`new_module`, `new_name` or both, and exactly one of `since` and the message. A
keyword passed as `None` counts as not passed. For an
enum member wrapper it is `deprecated_member(value, message)`, each passed
positionally or by keyword.

They are options so that, if `frequenz-core` renames or moves a helper, you can
point them at the new path without waiting for a release of this package.

There is one deliberate difference from `griffe-warnings-deprecated`: given an
empty `title`, it puts the message in the admonition title, and this
extension does not. The notice contains a link to the target, which does not
belong in a title, and the title is also what tells a hand-written admonition
apart.

## Supported Platforms

The following platforms are officially supported (tested):

- **Python:** 3.11
- **Operating System:** Ubuntu Linux 20.04
- **Architectures:** amd64, arm64

## Contributing

If you want to know how to build this project and contribute to it, please
check out the [Contributing Guide](CONTRIBUTING.md).
