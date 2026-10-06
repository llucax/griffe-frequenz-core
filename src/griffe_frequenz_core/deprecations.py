# License: MIT
# Copyright © 2026 Frequenz Energy-as-a-Service GmbH

"""Document deprecations that are expressed as a function call.

The usual way to deprecate a Python API is a decorator, and Griffe already reads
those: [`griffe-warnings-deprecated`](https://mkdocstrings.github.io/griffe-warnings-deprecated/)
turns `@warnings.deprecated` and `@typing_extensions.deprecated` into an admonition
and a label.

Some [`frequenz-core`](https://github.com/frequenz-floss/frequenz-core-python)
helpers cannot use a decorator, so they deprecate through a call instead, and
nothing sees them. This module fills that gap for the two shapes `frequenz-core`
uses. See [`DeprecationsExtension`][griffe_frequenz_core.deprecations.DeprecationsExtension]
for what they look like and how to enable the extension.
"""

from __future__ import annotations

import ast
from collections.abc import Sequence
from typing import Any, NamedTuple

from griffe import (
    Attribute,
    Class,
    Docstring,
    DocstringSectionAdmonition,
    DocstringSectionKind,
    ExprCall,
    ExprKeyword,
    ExprName,
    ExprVarKeyword,
    ExprVarPositional,
    Extension,
    Module,
    get_logger,
)

_logger = get_logger(__name__)


def _literal(node: Any) -> Any:
    """Evaluate a Griffe expression as a Python literal.

    Args:
        node: The expression to evaluate.

    Returns:
        The literal value, or `None` if the expression is not a literal.
    """
    try:
        return ast.literal_eval(str(node))
    except (ValueError, SyntaxError, TypeError):
        return None


def _string(node: Any) -> str | None:
    """Evaluate a Griffe expression as a string literal.

    Args:
        node: The expression to evaluate.

    Returns:
        The string, or `None` if the expression is not a string literal.
    """
    value = _literal(node)
    return value if isinstance(value, str) else None


class _AliasEntry(NamedTuple):
    """What could be read of one alias entry."""

    name: str
    """The deprecated name, in the module defining the alias."""

    new: str | None
    """The fully qualified path of the target, or `None` if it cannot be read."""

    local: bool
    """Whether the target is in the module defining the alias."""

    since: str | None
    """The version the alias is deprecated since, if given and readable."""


def _link(new: str, *, local: bool) -> str:
    """Link a replacement in code font.

    Args:
        new: The fully qualified path of the replacement.
        local: Whether it is in the module of the object being documented, where
            its name alone is enough, as it is for a member of the same class.

    Returns:
        The Markdown cross-reference.
    """
    if local:
        return f"[`{new.rpartition('.')[2]}`][{new}]"
    return f"[`{new}`][]"


def _generic_message(*, since: str | None = None, new_link: str | None = None) -> str:
    """Build a notice out of whatever is known about a deprecation.

    It is only shown in the documentation of the deprecated object itself, so
    it doesn't say which object that is, and it says as much as is known, and
    nothing more.

    Args:
        since: The version the object is deprecated since, if known.
        new_link: The link to its replacement, if known.

    Returns:
        The notice.
    """
    if since is None and new_link is None:
        return "Deprecated. It will be removed in a future release."
    text = "Deprecated." if since is None else f"Deprecated since {since}."
    return text if new_link is None else f"{text} Use {new_link} instead."


def _alias_entry_arguments(
    call: ExprCall,
) -> tuple[Any, Any, Any, Any, Any] | None:
    """Find the name, where it points, and `since` or the message of an alias entry.

    The call is bound the way Python binds `DeprecatedAlias(name, /, *,
    new_module=None, new_name=None, since=None, message=None)`, with at least one
    of `new_module` and `new_name` and exactly one of `since` and `message`, so
    the name must be passed positionally and the rest by keyword. A keyword passed
    as `None` counts as not passed, as it does at runtime. Unpacking must already
    have been ruled out, since a `*args` or `**kwargs` would be read as a plain
    argument.

    Args:
        call: The alias entry call to read.

    Returns:
        The expressions passed as the name, `new_module`, `new_name`, `since` and
            the message, with `None` for the ones not passed, or `None` if the
            call does not bind that way: an argument is missing or passed twice,
            passed the wrong way, neither `new_module` nor `new_name` is passed,
            both or neither of `since` and `message` are passed, or there is an
            extra argument.
    """
    keywords = ("new_module", "new_name", "since", "message")
    name: Any = None
    bound: dict[str, Any] = {}
    for argument in call.arguments:
        if isinstance(argument, ExprKeyword):
            if argument.name not in keywords or argument.name in bound:
                return None
            if str(argument.value) != "None":
                bound[argument.name] = argument.value
        elif name is None:
            name = argument
        else:
            return None
    if name is None or not ("new_module" in bound or "new_name" in bound):
        return None
    if ("since" in bound) == ("message" in bound):
        return None
    return (
        name,
        bound.get("new_module"),
        bound.get("new_name"),
        bound.get("since"),
        bound.get("message"),
    )


def _wrapper_arguments(call: ExprCall) -> tuple[Any, Any] | None:
    """Find the value and the message among the arguments of an enum wrapper call.

    The call is bound the way Python binds `deprecated_member(value, message)`,
    so each may be passed positionally or by keyword. Unpacking must already have
    been ruled out, since a `*args` or `**kwargs` would be read as a plain
    argument.

    Args:
        call: The wrapper call to read.

    Returns:
        The expressions passed as the value and as the message, or `None` if
        the call does not bind exactly those two: one is missing or passed
        twice, or there is an extra argument.
    """
    parameters = ("value", "message")
    positions = iter(parameters)
    bound: dict[str, Any] = {}
    for argument in call.arguments:
        name: str | None
        if isinstance(argument, ExprKeyword):
            name, node = argument.name, argument.value
        else:
            name, node = next(positions, None), argument
        if name is None or name not in parameters or name in bound:
            return None
        bound[name] = node
    if len(bound) != 2:
        return None
    return bound["value"], bound["message"]


# Every option is a key in `mkdocs.yml`, so they have to stay flat.
class DeprecationsExtension(Extension):  # pylint: disable=too-many-instance-attributes
    """Mark the deprecations `frequenz-core` expresses through a call.

    Two shapes are recognized, and both end up with the same treatment as a
    decorator-based deprecation: a `deprecated` label, the message on the object's
    `deprecated` field, and an admonition inserted at the top of its docstring.

    The first is a table of module-level aliases kept alive by a module
    `__getattr__`:

    ```python
    from typing import TYPE_CHECKING, TypeAlias

    from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases

    if TYPE_CHECKING:
        from mypkg.newmod import Widget as _Widget

        Widget: TypeAlias = _Widget  # plus its usual attribute docstring
    else:
        __getattr__ = deprecated_aliases(
            __name__,
            DeprecatedAlias("Widget", new_module="mypkg.newmod", since="v1.2.0"),
        )
    ```

    Every alias in that table is marked, whether or not it is declared for type
    checkers, with a notice built from `default_message`, saying since which
    version it is deprecated and linking its target. An entry giving `new_name`
    renames as well as moves, and one without `new_module` points at another
    name in its own module. An entry's `message` is only its runtime warning,
    and doesn't change the notice; a hand-written one does.

    The second is an enum member whose value is wrapped:

    ```python
    from frequenz.core.enum import Enum, deprecated_member

    class TaskStatus(Enum):
        OPEN = 1
        PENDING = deprecated_member(1, "PENDING is deprecated, use OPEN instead")
    ```

    Such a member is marked and its rendered value is rewritten from the wrapper
    call back to the real value, so the documentation shows `PENDING = 1`. The
    `DeprecatedMember(1, "...")` form `frequenz-core` also accepts is recognized
    too: a class and a function are both read as a call.

    Warning:
        Griffe never runs the code, so only string literals written directly in
        the call can be read. Whatever cannot be read is left out of a notice
        saying as much as can be, at least that it is deprecated: an alias only
        needs its name to be a literal to be marked, and its value is rewritten
        only if `new_module` and `new_name` are literals. An enum member whose
        message is not a literal is marked too, and its value is unwrapped as
        written, so it shows `CANCELLED = 1` even when the message comes from a
        constant or helper call; one whose wrapper arguments are unpacked from
        `*args` or `**kwargs` keeps its value as written. An alias whose name
        cannot be read is left unmarked: an entry that is not a
        `DeprecatedAlias(...)` call written directly among the arguments of
        `deprecated_aliases()`, such as one held in a constant or unpacked from
        `*args`, or one with a non-literal name or with its positional
        arguments unpacked. Each of these cases is logged at debug level, which
        `mkdocs -v` shows.

    Enable it under the mkdocstrings Python handler, alongside the decorator one:

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

    The defaults match `griffe-warnings-deprecated`, so the two render alike with
    no configuration. Anything that needs changing is an option:

    ```yaml
                extensions:
                  - griffe_frequenz_core.deprecations:
                      kind: deprecated
                      alias_table_functions:
                        - frequenz.core.warnings.deprecated_aliases
                        - mypkg.compat.moved_to
                      alias_classes:
                        - frequenz.core.warnings.DeprecatedAlias
                        - mypkg.compat.Moved
    ```

    Note:
        The paths this extension matches are options rather than constants on
        purpose: if `frequenz-core` renames a helper, point the option at the new
        path instead of waiting for a release of this package.

    Note:
        There is one deliberate difference from `griffe-warnings-deprecated`:
        given an empty `title`, it promotes the message into the admonition's
        title, and this extension does not. The notice here carries a rendered
        cross-reference to the target, which does not belong in a title, and the
        title is also what decides whether a docstring already documents its own
        deprecation. Please do not "fix" this into a bug.
    """

    # Every option is a key in `mkdocs.yml`, so they have to stay flat.
    def __init__(  # pylint: disable=too-many-arguments
        self,
        kind: str = "danger",
        title: str | None = "Deprecated",
        label: str | None = "deprecated",
        *,
        alias_table_functions: Sequence[str] = (
            "frequenz.core.warnings.deprecated_aliases",
        ),
        alias_classes: Sequence[str] = ("frequenz.core.warnings.DeprecatedAlias",),
        member_wrapper_functions: Sequence[str] = (
            "frequenz.core.enum.deprecated_member",
            "frequenz.core.enum.DeprecatedMember",
        ),
        default_message: str = "Deprecated since {since}. Use {new_link} instead.",
        show_target: bool = True,
    ) -> None:
        """Initialize the extension.

        Args:
            kind: The kind of the admonition inserted in the docstring.
            title: The title of that admonition. An empty title renders the
                admonition without one.
            label: The label added to deprecated objects, or `None` to add none.
            alias_table_functions: The fully qualified paths of the functions that
                build a module `__getattr__` out of an alias table. Their calls
                are read as if they had the signature of
                `deprecated_aliases(module, /, *aliases)`: every positional
                argument after the module is an alias entry, and keyword
                arguments are ignored.
            alias_classes: The fully qualified paths of the callables that build
                one alias entry. Their calls are read as if they had the
                signature of `DeprecatedAlias(name, /, *, new_module=None,
                new_name=None, since=None, message=None)`, with at least one of
                `new_module` and `new_name`, and exactly one of `since` and
                `message`.
            member_wrapper_functions: The fully qualified paths of the callables
                that wrap an enum member's value to deprecate it. A class works
                as well as a function, since both are read as a call. Their
                calls are read as if they had the signature of
                `deprecated_member(value, message)`.
            default_message: The template of an alias' notice. `{old}` and
                `{new}` are substituted with the plain paths of the alias and
                its target, `{new_link}` with a code font link to the target,
                showing only its name if it is in the same module, and
                `{since}` with the version, as written. The result is rendered
                as Markdown. It is only shown in the documentation, next to the
                alias, so it doesn't need to say which symbol is deprecated, as
                the runtime warning does.
            show_target: Whether to render an alias' value as the target it points
                at, rather than the private name imported for type checkers.
        """
        super().__init__()
        self.kind = kind
        """The kind of the admonition inserted in the docstring."""
        self.title = title or ""
        """The title of the admonition inserted in the docstring."""
        self.label = label
        """The label added to deprecated objects."""
        self.alias_table_functions = frozenset(alias_table_functions)
        """The paths of the functions that build a `__getattr__` from an alias table."""
        self.alias_classes = frozenset(alias_classes)
        """The paths of the callables that build one alias entry."""
        self.member_wrapper_functions = frozenset(member_wrapper_functions)
        """The paths of the callables that wrap a deprecated enum member's value."""
        self.default_message = default_message
        """The template of an alias' notice."""
        self.show_target = show_target
        """Whether to render an alias' value as the target it points at."""

    def on_module_members(self, *, mod: Module, **kwargs: Any) -> None:
        """Mark every name in the module's alias table, if it has one.

        Args:
            mod: The module whose members were just collected.
            **kwargs: Everything else Griffe passes, all unused.
        """
        call = self._alias_table_call(mod)
        if call is None:
            return
        for entry in self._alias_entries(mod, call):
            text, generic = self._alias_notice(f"{mod.path}.{entry.name}", entry)

            member = mod.members.get(entry.name)
            if not isinstance(member, Attribute):
                # Not declared at all, or declared by an import such as
                # `from new import New as Old` under `TYPE_CHECKING`.
                _logger.debug(
                    "%s.%s is aliased but not declared as an attribute for type "
                    "checkers, adding one",
                    mod.path,
                    entry.name,
                )
                member = Attribute(entry.name, parent=mod)
                mod.set_member(entry.name, member)

            if self.show_target and entry.new is not None:
                member.value = ExprName(entry.new)
            self._mark(member, text, generic=generic)

    def _alias_notice(self, old: str, entry: _AliasEntry) -> tuple[str, bool]:
        """Build the notice of one alias entry.

        The notice comes from `since` and the target only: an entry's `message`
        is only its runtime warning, written for a terminal.

        Args:
            old: The fully qualified path of the alias.
            entry: What could be read of the entry.

        Returns:
            The notice, and whether it is a generic one, saying as much of the
                entry as could be read.
        """
        link = None if entry.new is None else _link(entry.new, local=entry.local)
        if entry.since is not None and link is not None:
            try:
                # `since` is a value, not part of the template, so it is
                # inserted as written, braces included.
                return (
                    self.default_message.format(
                        old=old, new=entry.new, new_link=link, since=entry.since
                    ),
                    False,
                )
            except (AttributeError, IndexError, KeyError, ValueError):
                _logger.debug(
                    "%s: the `default_message` option %r is not a template with "
                    "only {old}, {new}, {new_link} and {since}, using a generic "
                    "notice",
                    old,
                    self.default_message,
                )
                return _generic_message(since=entry.since, new_link=link), True
        missing = []
        if entry.since is None:
            missing.append(
                "since which version it is deprecated, without `since` as a string "
                "literal"
            )
        if link is None:
            missing.append("what to use instead, without a readable target")
        _logger.debug("%s: the notice can't say %s", old, ", nor ".join(missing))
        return _generic_message(since=entry.since, new_link=link), True

    def on_class_members(self, *, cls: Class, **kwargs: Any) -> None:
        """Mark every wrapped enum member of the class, if it has any.

        Args:
            cls: The class whose members were just collected.
            **kwargs: Everything else Griffe passes, all unused.
        """
        for member in cls.members.values():
            value = getattr(member, "value", None)
            if not isinstance(member, Attribute) or not isinstance(value, ExprCall):
                continue
            if value.canonical_path not in self.member_wrapper_functions:
                continue
            # Positions mean nothing once an argument is unpacked: in
            # `deprecated_member(*ARGS, "...")` the second argument is the
            # message, but the first is not the value. The member is still
            # deprecated, so it is marked, but the call is left as written.
            if any(
                isinstance(argument, (ExprVarPositional, ExprVarKeyword))
                for argument in value.arguments
            ):
                _logger.debug(
                    "%s: the deprecation wrapper's arguments are unpacked, "
                    "marking the member with a generic message",
                    member.path,
                )
                self._mark(member, _generic_message(), generic=True)
                continue
            arguments = _wrapper_arguments(value)
            if arguments is None:
                # It would fail at runtime, so it deprecates nothing.
                _logger.debug(
                    "%s: the deprecation wrapper does not take exactly a value "
                    "and a message, leaving the member unmarked",
                    member.path,
                )
                continue
            real_value, message = arguments
            # Show the member's real value, not the wrapper call, even when the
            # message cannot be read: the value is known either way.
            member.value = real_value
            text = _literal(message)
            if isinstance(text, str):
                self._mark(member, text)
                continue
            _logger.debug(
                "%s: deprecation message is not a static string, "
                "marking the member with a generic message",
                member.path,
            )
            self._mark(member, _generic_message(), generic=True)

    def _alias_table_call(self, mod: Module) -> ExprCall | None:
        """Return the module's alias table call, if it has one.

        Args:
            mod: The module to look at.

        Returns:
            The call assigned to the module's `__getattr__`, or `None` if the
            module has no `__getattr__` or it comes from somewhere else.
        """
        value = getattr(mod.members.get("__getattr__"), "value", None)
        if isinstance(value, ExprCall) and value.canonical_path in (
            self.alias_table_functions
        ):
            return value
        return None

    def _alias_entries(self, mod: Module, call: ExprCall) -> list[_AliasEntry]:
        """Extract the alias entries from an alias table call.

        The first positional argument is the module name and is skipped. Every
        other positional argument must be an alias entry call, and keyword
        arguments are ignored, since none of them can carry an entry.

        Args:
            mod: The module the call was found in, used to report what is skipped.
            call: The alias table call to read.

        Returns:
            Every entry whose name could be read, in the order they were written.
        """
        entries: list[_AliasEntry] = []
        module_seen = False
        for argument in call.arguments:
            if isinstance(argument, (ExprKeyword, ExprVarKeyword)):
                continue
            if isinstance(argument, ExprVarPositional):
                # Only `module` could be hidden in there, so it is not skipped
                # anymore: a module name is never an entry anyway.
                module_seen = True
                _logger.debug(
                    "%s: the alias entries in `%s` are unpacked, "
                    "leaving them unmarked",
                    mod.path,
                    argument,
                )
                continue
            if not module_seen:
                module_seen = True
                continue
            entry = self._alias_entry(mod, argument)
            if entry is not None:
                entries.append(entry)
        return entries

    def _alias_entry(self, mod: Module, node: Any) -> _AliasEntry | None:
        """Read one alias entry, as much of it as can be read.

        The name is all that is needed to mark the alias. Where it points, and
        its `since` or message, are only read if they are string literals.

        Args:
            mod: The module the entry was found in, used to report what is skipped.
            node: The expression passed as the entry.

        Returns:
            What could be read of the entry, or `None` if its name cannot be read,
                or if it is not bound the way the runtime binds it.
        """
        if not (
            isinstance(node, ExprCall) and node.canonical_path in self.alias_classes
        ):
            _logger.debug(
                "%s: the alias entry `%s` is not a call to a known alias class, "
                "skipping it",
                mod.path,
                node,
            )
            return None
        if any(isinstance(argument, ExprVarPositional) for argument in node.arguments):
            _logger.debug(
                "%s: the arguments of the alias entry `%s` are unpacked, "
                "skipping it",
                mod.path,
                node,
            )
            return None
        if any(isinstance(argument, ExprVarKeyword) for argument in node.arguments):
            return self._alias_entry_with_unpacked_keywords(mod, node)
        arguments = _alias_entry_arguments(node)
        if arguments is None:
            # It would fail at runtime, so it deprecates nothing.
            _logger.debug(
                "%s: the alias entry `%s` does not take exactly a positional "
                "name, `new_module`, `new_name` or both, and either `since` or a "
                "`message`, skipping it",
                mod.path,
                node,
            )
            return None
        name_node, *other_nodes = arguments
        name = _string(name_node)
        if name is None:
            _logger.debug(
                "%s: the name of the alias entry `%s` is not a static string, "
                "skipping it",
                mod.path,
                node,
            )
            return None
        # The message is only the runtime warning, so it is never read.
        new_module, new_name, since = (
            None if other is None else _string(other) for other in other_nodes[:3]
        )
        unreadable = [
            other is not None and value is None
            for other, value in zip(other_nodes, (new_module, new_name, since))
        ]
        if any(unreadable):
            _logger.debug(
                "%s: an argument of the alias entry `%s` is not a static string, "
                "documenting what can be read",
                mod.path,
                node,
            )
        # Without `new_module` the symbol is still in this module, and without
        # `new_name` it kept its name, as at runtime.
        new = (
            None
            if unreadable[0] or unreadable[1]
            else f"{new_module or mod.path}.{new_name or name}"
        )
        return _AliasEntry(name, new, new_module in (None, mod.path), since)

    def _alias_entry_with_unpacked_keywords(
        self, mod: Module, node: ExprCall
    ) -> _AliasEntry | None:
        """Read the name of an alias entry whose keyword arguments are unpacked.

        Any keyword may be hidden in a `**kwargs`, so only the name is known.

        Args:
            mod: The module the entry was found in, used to report what is skipped.
            node: The entry call.

        Returns:
            The entry with only its name, or `None` if the name cannot be read.
        """
        positional = [
            argument
            for argument in node.arguments
            if not isinstance(argument, (ExprKeyword, ExprVarKeyword))
        ]
        name = _literal(positional[0]) if len(positional) == 1 else None
        if not isinstance(name, str):
            _logger.debug(
                "%s: the arguments of the alias entry `%s` are unpacked, "
                "skipping it",
                mod.path,
                node,
            )
            return None
        _logger.debug(
            "%s: the keyword arguments of the alias entry `%s` are unpacked, "
            "documenting only its name",
            mod.path,
            node,
        )
        return _AliasEntry(name, None, False, None)

    def _mark(self, member: Attribute, text: str, *, generic: bool = False) -> None:
        """Flag one member as deprecated and give it the admonition.

        Args:
            member: The member to mark.
            text: The deprecation message.
            generic: Whether `text` is a generic message standing in for one that
                cannot be read, in which case a message set by someone else is
                used instead, for the admonition too.
        """
        if generic and isinstance(member.deprecated, str):
            # Another extension could read the message, so it is the one shown.
            text = member.deprecated
        member.deprecated = text
        if self.label:
            member.labels.add(self.label)
        if self._already_marked(member):
            return
        if member.docstring is None:
            member.docstring = Docstring("", parent=member)
        member.docstring.parsed.insert(
            0,
            DocstringSectionAdmonition(kind=self.kind, text=text, title=self.title),
        )

    def _already_marked(self, member: Attribute) -> bool:
        """Tell whether the member's docstring already carries the admonition.

        A hand-written admonition is left alone, so a module can say more about
        one particular deprecation than the message template can.

        Args:
            member: The member to check.

        Returns:
            Whether the docstring already has a deprecation admonition.
        """
        if member.docstring is None:
            return False
        for section in member.docstring.parsed:
            if section.kind is DocstringSectionKind.deprecated:
                return True
            if (
                section.kind is DocstringSectionKind.admonition
                and str(getattr(section, "title", "")).strip().lower()
                == self.title.strip().lower()
            ):
                return True
        return False
