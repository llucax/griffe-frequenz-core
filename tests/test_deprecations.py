# License: MIT
# Copyright © 2026 Frequenz Energy-as-a-Service GmbH

"""Tests for the deprecations extension.

The fixtures under `fixtures/` refer to `frequenz-core` helpers but are never
run. Griffe resolves those paths from import statements without importing
`frequenz-core`; only the compatibility tests import the installed test
dependency.
"""

import logging
from pathlib import Path
from typing import Any

import griffe
import pytest
from griffe import (
    Attribute,
    DocstringSectionAdmonition,
    DocstringSectionKind,
    ExprName,
    Module,
    Parser,
)

from griffe_frequenz_core.deprecations import DeprecationsExtension

_FIXTURES = Path(__file__).parent / "fixtures"

_ALIASES = "frequenz.core.warnings.deprecated_aliases"
_ALIAS_CLASS = "frequenz.core.warnings.DeprecatedAlias"
_MEMBERS = "frequenz.core.enum.deprecated_member"
_LOGGER = "griffe_frequenz_core.deprecations"
_GENERIC = "Deprecated. It will be removed in a future release."


def load(
    name: str = "samplepkg", *, parser: Parser = Parser.google, **options: Any
) -> Module:
    """Load a fixture with the extension applied.

    Args:
        name: The fixture package or module to load.
        parser: The docstring style the fixture is written in.
        **options: The extension's options.

    Returns:
        The loaded module.
    """
    loaded = griffe.load(
        name,
        search_paths=[_FIXTURES],
        docstring_parser=parser,
        extensions=griffe.load_extensions(DeprecationsExtension(**options)),
    )
    assert isinstance(loaded, Module)
    return loaded


def attribute(module: Module, path: str) -> Attribute:
    """Return one attribute of a loaded fixture.

    Args:
        module: The loaded fixture.
        path: The dotted path of the attribute inside it.

    Returns:
        The attribute.
    """
    member = module[path]
    assert isinstance(member, Attribute)
    return member


def admonitions(member: Attribute) -> list[DocstringSectionAdmonition]:
    """Return the admonition sections of an attribute's docstring.

    Args:
        member: The attribute to look at.

    Returns:
        Its admonition sections, in order, or an empty list if it has no
        docstring.
    """
    if member.docstring is None:
        return []
    return [
        section
        for section in member.docstring.parsed
        if isinstance(section, DocstringSectionAdmonition)
    ]


@pytest.fixture(name="samplepkg", scope="module")
def samplepkg_fixture() -> Module:
    """Load the sample package once, with the extension's defaults.

    Returns:
        The loaded package.
    """
    return load()


def test_every_alias_in_the_table_is_marked(samplepkg: Module) -> None:
    """All three entries are marked, whatever their docstring looks like."""
    for name in ("Widget", "Doohickey", "MAX_WIDGETS"):
        member = attribute(samplepkg, f"oldmod.{name}")
        assert "deprecated" in member.labels
        assert isinstance(member.deprecated, str)


def test_since_gets_the_default_message(samplepkg: Module) -> None:
    """An entry giving `since` gets the default wording, linking the target."""
    member = attribute(samplepkg, "oldmod.MAX_WIDGETS")
    assert member.deprecated == (
        "Deprecated since v1.4.0. Use [`samplepkg.newmod.MAX_WIDGETS`][] instead."
    )


def test_an_alias_message_is_only_the_runtime_warning(samplepkg: Module) -> None:
    """A message is written for a terminal, so the notice comes from the target.

    Without `since`, the notice can't say since which version, so it only says
    what to use instead.
    """
    member = attribute(samplepkg, "oldmod2.Thing")
    assert member.deprecated == (
        "Deprecated. Use [`samplepkg.newmod.Widget`][] instead."
    )
    assert len(admonitions(member)) == 1


def test_every_alias_has_its_own_message(samplepkg: Module) -> None:
    """Each entry carries its own message, so each can say its own version."""
    for name, version in (
        ("Widget", "v1.2.0"),
        ("Doohickey", "v1.3.0"),
        ("MAX_WIDGETS", "v1.4.0"),
    ):
        member = attribute(samplepkg, f"oldmod.{name}")
        assert str(member.deprecated).startswith(f"Deprecated since {version}. Use ")


def test_a_renamed_alias_points_at_its_new_name(samplepkg: Module) -> None:
    """`new_name` renames as well as moves."""
    member = attribute(samplepkg, "oldmod.Doohickey")
    assert member.value == ExprName("samplepkg.newmod.Gadget")
    assert "samplepkg.newmod.Gadget" in str(member.deprecated)


def test_an_alias_without_a_docstring_gets_one(samplepkg: Module) -> None:
    """The admonition still has somewhere to go when there is no docstring."""
    member = attribute(samplepkg, "oldmod.MAX_WIDGETS")
    assert member.docstring is not None
    sections = admonitions(member)
    assert len(sections) == 1
    assert sections[0].value.contents == member.deprecated


def test_the_admonition_goes_first(samplepkg: Module) -> None:
    """A reader sees the deprecation before the prose describing the symbol."""
    member = attribute(samplepkg, "oldmod.Doohickey")
    assert member.docstring is not None
    kinds = [section.kind for section in member.docstring.parsed]
    assert kinds[0] is DocstringSectionKind.admonition


def test_a_handwritten_admonition_is_left_alone(samplepkg: Module) -> None:
    """A module can say more than the template, and keeps the last word."""
    member = attribute(samplepkg, "oldmod.Widget")
    sections = admonitions(member)
    assert len(sections) == 1
    assert "see the migration guide" in sections[0].value.contents
    # The label and the field are still set, only the prose is left as written.
    assert "deprecated" in member.labels
    assert isinstance(member.deprecated, str)


def test_a_handwritten_numpy_section_is_left_alone() -> None:
    """Numpy style expresses the same thing as a section of its own kind."""
    member = attribute(load("numpymod", parser=Parser.numpy), "Widget")
    assert not admonitions(member)
    assert member.docstring is not None
    kinds = [section.kind for section in member.docstring.parsed]
    assert DocstringSectionKind.deprecated in kinds
    assert "deprecated" in member.labels


def test_helpers_imported_through_a_module_alias_are_recognized(
    samplepkg: Module,
) -> None:
    """`w.deprecated_aliases` and `w.DeprecatedAlias` resolve to the real paths."""
    member = attribute(samplepkg, "oldmod2.Thing")
    assert "deprecated" in member.labels
    assert member.value == ExprName("samplepkg.newmod.Widget")


def test_an_alias_hidden_from_type_checkers_is_created(samplepkg: Module) -> None:
    """A table entry with no declaration still gets documented."""
    member = attribute(samplepkg, "edge.Hidden")
    assert "deprecated" in member.labels
    assert member.value == ExprName("samplepkg.newmod.Widget")


def test_an_alias_declared_by_an_import_is_documented_as_an_attribute() -> None:
    """`from new import New as Old` for type checkers is replaced, not skipped."""
    code = (
        "from typing import TYPE_CHECKING\n"
        "from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases\n"
        "if TYPE_CHECKING:\n"
        "    from pkg.new import New as Old\n"
        "else:\n"
        "    __getattr__ = deprecated_aliases(\n"
        "        __name__,\n"
        "        DeprecatedAlias('Old', new_module='pkg.new', new_name='New', "
        "since='v1'),\n"
        "    )\n"
    )
    with griffe.temporary_visited_module(
        code, extensions=griffe.load_extensions(DeprecationsExtension())
    ) as module:
        member = attribute(module, "Old")
        assert "deprecated" in member.labels
        assert member.value == ExprName("pkg.new.New")
        assert len(admonitions(member)) == 1


def test_an_unknown_target_is_still_referenced(samplepkg: Module) -> None:
    """A target nothing knows about is linked anyway, so the link is reported.

    `mkdocs-autorefs` then warns about it, instead of the link silently
    becoming plain text.
    """
    member = attribute(samplepkg, "edge.Outside")
    assert "[`some.external.pkg.Thing`][]" in str(member.deprecated)


def test_an_unrelated_module_getattr_is_untouched(samplepkg: Module) -> None:
    """A module defining its own `__getattr__` must come out unchanged."""
    other = samplepkg["other"]
    assert isinstance(other, Module)
    # Nothing was invented: `Any` is just the import the fixture makes.
    assert set(other.members) == {"Any", "__getattr__", "VALUE"}
    getattr_ = other["__getattr__"]
    assert "deprecated" not in getattr_.labels
    assert not getattr_.deprecated
    value = attribute(other, "VALUE")
    assert "deprecated" not in value.labels
    assert not value.deprecated
    assert admonitions(value) == []


def test_wrapped_enum_members_are_marked(samplepkg: Module) -> None:
    """Both wrapped members get the label, the field and the admonition."""
    for name, message in (
        ("PENDING", "PENDING is deprecated, use OPEN instead"),
        ("STARTED", "STARTED is deprecated, use IN_PROGRESS instead"),
    ):
        member = attribute(samplepkg, f"statuses.TaskStatus.{name}")
        assert "deprecated" in member.labels
        assert member.deprecated == message
        sections = admonitions(member)
        assert len(sections) == 1
        assert sections[0].value.contents == message


def test_the_class_form_of_the_wrapper_is_recognized(samplepkg: Module) -> None:
    """`frequenz-core` accepts `DeprecatedMember(...)` too, and it reads the same."""
    member = attribute(samplepkg, "statuses.TaskStatus.WAITING")
    assert "deprecated" in member.labels
    assert member.deprecated == "WAITING is deprecated, use OPEN instead"
    assert str(member.value) == "1"


def test_a_wrapped_enum_member_shows_its_real_value(samplepkg: Module) -> None:
    """The documentation says `PENDING = 1`, not the wrapper call."""
    assert str(attribute(samplepkg, "statuses.TaskStatus.PENDING").value) == "1"


def test_other_enum_members_are_untouched(samplepkg: Module) -> None:
    """Plain members, and members built by some other call, are left alone."""
    for name in ("OPEN", "IN_PROGRESS", "COMPUTED"):
        member = attribute(samplepkg, f"statuses.TaskStatus.{name}")
        assert "deprecated" not in member.labels
        assert not member.deprecated
        assert admonitions(member) == []


def test_a_non_literal_enum_message_gets_a_generic_notice(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Griffe never runs the module, so a message in a constant is unreadable."""
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        package = load()
    member = attribute(package, "statuses.TaskStatus.CANCELLED")
    generic = _GENERIC
    assert member.deprecated == generic
    assert "deprecated" in member.labels
    assert [section.value.contents for section in admonitions(member)] == [generic]
    assert any(
        "CANCELLED" in record.message and "not a static string" in record.message
        for record in caplog.records
    )
    assert str(member.value) == "1"


@pytest.mark.parametrize(
    ("wrapper", "value", "message"),
    [
        ("deprecated_member(7, _member_message('A'))", "7", None),
        ("deprecated_member(value=7, message=_member_message('A'))", "7", None),
        ("deprecated_member(message=_member_message('A'), value=7)", "7", None),
        ("deprecated_member(7, _MESSAGE)", "7", None),
        ("deprecated_member(_BASE + 1, _MESSAGE)", "_BASE + 1", None),
        ("DeprecatedMember(7, _member_message('A'))", "7", None),
        ("deprecated_member(7, 'Gone')", "7", "Gone"),
        ("DeprecatedMember(message='Gone', value=7)", "7", "Gone"),
    ],
)
def test_an_enum_wrapper_unwraps_its_value_whatever_the_message(
    wrapper: str, value: str, message: str | None
) -> None:
    """The value is shown as written, even if the message cannot be read.

    A hand-written notice is kept exactly once either way, instead of the
    generic one an unreadable message gets.
    """
    code = (
        "from frequenz.core.enum import DeprecatedMember, Enum, deprecated_member\n"
        "class Status(Enum):\n"
        f"    A = {wrapper}\n"
        '    """A status.\n\n    Deprecated:\n        Use B instead.\n    """\n'
    )
    with griffe.temporary_visited_module(
        code,
        docstring_parser=Parser.google,
        extensions=griffe.load_extensions(DeprecationsExtension()),
    ) as module:
        member = attribute(module, "Status.A")
        assert str(member.value) == value
        assert member.deprecated == (_GENERIC if message is None else message)
        assert "deprecated" in member.labels
        sections = admonitions(member)
        assert len(sections) == 1
        assert sections[0].title == "Deprecated"
        assert sections[0].value.contents == "Use B instead."


@pytest.mark.parametrize(("label", "added"), [("old", {"old"}), (None, set())])
def test_a_non_literal_enum_message_uses_the_configured_label(
    label: str | None, added: set[str]
) -> None:
    """The label option applies to a generic notice too."""
    code = (
        "from frequenz.core.enum import Enum, deprecated_member\n"
        "class Status(Enum):\n"
        "    A = deprecated_member(7, _member_message('A'))\n"
    )
    with griffe.temporary_visited_module(
        code, extensions=griffe.load_extensions(DeprecationsExtension(label=label))
    ) as module:
        member = attribute(module, "Status.A")
        assert member.deprecated == _GENERIC
        assert member.labels & {"old", "deprecated"} == added
        assert len(admonitions(member)) == 1


def test_a_non_literal_enum_message_keeps_an_existing_message() -> None:
    """A message another extension already found is used instead of a generic one.

    The admonition says the same as the field, so the two never disagree.
    """

    class Earlier(griffe.Extension):
        """Stand in for an extension that runs first and finds a message."""

        def on_attribute_instance(self, *, attr: Attribute, **kwargs: Any) -> None:
            """Give every attribute a message.

            Args:
                attr: The attribute just created.
                **kwargs: Everything else Griffe passes, all unused.
            """
            attr.deprecated = "Use B."

    code = (
        "from frequenz.core.enum import Enum, deprecated_member\n"
        "class Status(Enum):\n"
        "    A = deprecated_member(7, _MESSAGE)\n"
    )
    with griffe.temporary_visited_module(
        code,
        extensions=griffe.load_extensions(Earlier(), DeprecationsExtension()),
    ) as module:
        member = attribute(module, "Status.A")
        assert member.deprecated == "Use B."
        assert [section.value.contents for section in admonitions(member)] == ["Use B."]


@pytest.mark.parametrize(
    "arguments",
    ["1, message='Gone'", "value=1, message='Gone'", "message='Gone', value=1"],
)
def test_enum_wrapper_keyword_arguments_are_understood(arguments: str) -> None:
    """The value and the message may be passed by keyword, in any order."""
    code = (
        "from frequenz.core.enum import Enum, deprecated_member\n"
        "class Status(Enum):\n"
        f"    A = deprecated_member({arguments})\n"
    )
    with griffe.temporary_visited_module(
        code, extensions=griffe.load_extensions(DeprecationsExtension())
    ) as module:
        member = attribute(module, "Status.A")
        assert member.deprecated == "Gone"
        assert "deprecated" in member.labels
        assert str(member.value) == "1"


@pytest.mark.parametrize("arguments", ["*ARGS, 'Gone'", "*ARGS", "1, 'Gone', **KWARGS"])
def test_an_unpacked_enum_wrapper_call_is_marked_as_written(
    caplog: pytest.LogCaptureFixture, arguments: str
) -> None:
    """Arguments whose positions cannot be trusted get a generic notice.

    `*ARGS, 'Gone'` is the dangerous one: counted naively, its second argument
    is a valid message, and the member would be documented as `A = *ARGS`.
    """
    code = (
        "from frequenz.core.enum import Enum, deprecated_member\n"
        "class Status(Enum):\n"
        f"    A = deprecated_member({arguments})\n"
    )
    with (
        caplog.at_level(logging.DEBUG, logger=_LOGGER),
        griffe.temporary_visited_module(
            code, extensions=griffe.load_extensions(DeprecationsExtension())
        ) as module,
    ):
        member = attribute(module, "Status.A")
        assert member.deprecated == _GENERIC
        assert "deprecated" in member.labels
        assert str(member.value) == f"deprecated_member({arguments})"
    assert any(
        "Status.A" in record.message and "arguments are unpacked" in record.message
        for record in caplog.records
    )


@pytest.mark.parametrize(
    ("arguments", "logged"),
    [
        ("1", "does not take exactly a value and a message"),
        ("message='Gone'", "does not take exactly a value and a message"),
        ("1, 'Gone', 2", "does not take exactly a value and a message"),
        ("1, value=2, message='Gone'", "does not take exactly a value and a message"),
        ("1, msg='Gone'", "does not take exactly a value and a message"),
    ],
)
def test_an_unreadable_enum_wrapper_call_is_skipped_loudly(
    caplog: pytest.LogCaptureFixture, arguments: str, logged: str
) -> None:
    """A call that would fail at runtime deprecates nothing, and that is logged."""
    code = (
        "from frequenz.core.enum import Enum, deprecated_member\n"
        "class Status(Enum):\n"
        f"    A = deprecated_member({arguments})\n"
    )
    with (
        caplog.at_level(logging.DEBUG, logger=_LOGGER),
        griffe.temporary_visited_module(
            code, extensions=griffe.load_extensions(DeprecationsExtension())
        ) as module,
    ):
        member = attribute(module, "Status.A")
        assert not member.deprecated
        assert "deprecated" not in member.labels
        assert str(member.value) == f"deprecated_member({arguments})"
    assert any(
        "Status.A" in record.message and logged in record.message
        for record in caplog.records
    )


def test_a_non_literal_alias_message_is_not_needed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The message is never read, so the notice says what the target says."""
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        package = load()
    member = attribute(package, "nonliteral.Thing")
    assert member.deprecated == "Deprecated. Use [`samplepkg.newmod.Widget`][] instead."
    assert "deprecated" in member.labels
    assert not any("message=_MESSAGE" in record.message for record in caplog.records)


def test_a_non_literal_alias_name_is_skipped_loudly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An entry whose name is not a literal names nothing Griffe can mark."""
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        package = load()
    assert "Lost" not in package["nonliteral"].members
    assert any(
        "DeprecatedAlias(_LOST, " in record.message
        and "is not a static string" in record.message
        for record in caplog.records
    )


def test_a_skipped_entry_does_not_affect_the_others(samplepkg: Module) -> None:
    """Entries are read one by one, so the readable one is still marked."""
    member = attribute(samplepkg, "nonliteral.Kept")
    assert "deprecated" in member.labels
    assert str(member.deprecated).startswith("Deprecated since v1.0.0. Use ")


def test_an_alias_entry_in_a_constant_is_skipped_loudly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An entry held in a constant cannot be read, so it must be logged."""
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        package = load()
    member = attribute(package, "constant.Thing")
    assert not member.deprecated
    assert "deprecated" not in member.labels
    assert any(
        record.message
        == "samplepkg.constant: the alias entry `_THING` is not a call to a known "
        "alias class, skipping it"
        for record in caplog.records
    )


_ENTRY = "DeprecatedAlias('Thing', new_module='pkg.new', since='v1')"


@pytest.mark.parametrize(
    ("arguments", "logged"),
    [
        ("__name__, *ENTRIES", "the alias entries in `*ENTRIES` are unpacked"),
        (
            "__name__, {'Thing': 'pkg.new'}",
            "is not a call to a known alias class",
        ),
        (
            "__name__, Moved('Thing', new_module='pkg.new', message='{old} gone.')",
            "is not a call to a known alias class",
        ),
        (
            "__name__, DeprecatedAlias(*ARGS, new_module='pkg.new', message='Gone')",
            "are unpacked, skipping it",
        ),
        (
            "__name__, DeprecatedAlias('Thing', **KWARGS)",
            "are unpacked, skipping it",
        ),
        (
            "__name__, DeprecatedAlias('Thing', new_module='pkg.new')",
            "does not take exactly a positional name",
        ),
        (
            "__name__, DeprecatedAlias('Thing', message='{old} gone.')",
            "does not take exactly a positional name",
        ),
        (
            "__name__, DeprecatedAlias('Thing', new_module=None, new_name=None, "
            "message='{old} gone.')",
            "does not take exactly a positional name",
        ),
        (
            "__name__, DeprecatedAlias(name='Thing', new_module='pkg.new', message='Gone')",
            "does not take exactly a positional name",
        ),
        (
            "__name__, DeprecatedAlias('Thing', 'pkg.new', message='Gone')",
            "does not take exactly a positional name",
        ),
        (
            "__name__, DeprecatedAlias('Thing', new_module='pkg.new', message='Gone', "
            "since='v1')",
            "does not take exactly a positional name",
        ),
        (
            "__name__, DeprecatedAlias('Thing', new_module='pkg.new', since='v1', "
            "until='v2')",
            "does not take exactly a positional name",
        ),
        (
            "__name__, DeprecatedAlias('Thing', new_module='pkg.new', since=SINCE)",
            "is not a static string",
        ),
        (
            "__name__, DeprecatedAlias('Thing', new_module=TARGET, message='Gone')",
            "is not a static string",
        ),
        (
            "__name__, DeprecatedAlias('Thing', new_name=NAME, message='Gone')",
            "is not a static string",
        ),
    ],
)
def test_an_unreadable_alias_entry_is_skipped_loudly(
    caplog: pytest.LogCaptureFixture, arguments: str, logged: str
) -> None:
    """Every way of writing an entry that cannot be read is reported."""
    code = (
        "from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases\n"
        "from mypkg.compat import Moved\n"
        f"__getattr__ = deprecated_aliases({arguments})\n"
    )
    with (
        caplog.at_level(logging.DEBUG, logger=_LOGGER),
        griffe.temporary_visited_module(
            code, extensions=griffe.load_extensions(DeprecationsExtension())
        ) as module,
    ):
        assert "Thing" not in module.members
    assert any(logged in record.message for record in caplog.records)


@pytest.mark.parametrize(
    "arguments",
    [
        f"__name__, {_ENTRY}",
        f"__name__, {_ENTRY}, category=FutureWarning, stacklevel=3",
        f"__name__, {_ENTRY}, **KWARGS",
        f"*ARGS, {_ENTRY}",
        f"__name__, *ENTRIES, {_ENTRY}",
    ],
)
def test_entries_written_out_are_read_whatever_surrounds_them(arguments: str) -> None:
    """Keywords and unpacking around an entry don't hide it."""
    code = (
        "from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases\n"
        f"__getattr__ = deprecated_aliases({arguments})\n"
    )
    with griffe.temporary_visited_module(
        code, extensions=griffe.load_extensions(DeprecationsExtension())
    ) as module:
        member = attribute(module, "Thing")
        assert "deprecated" in member.labels
        assert (
            member.deprecated == "Deprecated since v1. Use [`pkg.new.Thing`][] instead."
        )


@pytest.mark.parametrize(
    ("entry", "new"),
    [
        ("DeprecatedAlias('Thing', new_name='Other', since='v1')", "Other"),
        (
            "DeprecatedAlias('Thing', new_module=None, new_name='Other', since='v1')",
            "Other",
        ),
        (
            "DeprecatedAlias('Thing', new_module='pkg.new', new_name=None, "
            "since='v1', message=None)",
            None,
        ),
    ],
    ids=["in-place", "in-place-explicit-none", "explicit-none"],
)
def test_a_missing_new_module_or_name_defaults_as_at_runtime(
    entry: str, new: str | None
) -> None:
    """No `new_module` is the module defining the alias, no `new_name` its name.

    A keyword passed as `None` counts as not passed, as it does at runtime. A
    target in the same module is linked by its name alone.
    """
    code = (
        "from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases\n"
        f"__getattr__ = deprecated_aliases(__name__, {entry})\n"
    )
    with griffe.temporary_visited_module(
        code, extensions=griffe.load_extensions(DeprecationsExtension())
    ) as module:
        path = f"{module.path}.{new}" if new else "pkg.new.Thing"
        link = f"[`{new}`][{path}]" if new else f"[`{path}`][]"
        member = attribute(module, "Thing")
        assert member.value == ExprName(path)
        assert member.deprecated == f"Deprecated since v1. Use {link} instead."


def test_since_is_inserted_as_written() -> None:
    """`since` is a value, not a template, so braces in it reach the text as is."""
    code = (
        "from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases\n"
        "__getattr__ = deprecated_aliases(\n"
        "    __name__, DeprecatedAlias('Thing', new_module='pkg.new', since='{v1}')\n"
        ")\n"
    )
    with griffe.temporary_visited_module(
        code, extensions=griffe.load_extensions(DeprecationsExtension())
    ) as module:
        member = attribute(module, "Thing")
        assert str(member.deprecated).startswith("Deprecated since {v1}. Use ")


def test_a_bad_default_message_is_skipped_loudly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A configured template with unknown fields cannot mark `since` entries."""
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        package = load(default_message="{old} is gone in {version}.")
    assert not attribute(package, "oldmod.MAX_WIDGETS").deprecated
    assert any(
        "samplepkg.oldmod.MAX_WIDGETS: " in record.message
        and "is not a template with only {old}, {new}, {new_link} and {since}"
        in record.message
        for record in caplog.records
    )


def test_the_module_argument_is_not_an_entry() -> None:
    """Only the arguments after the module are entries, even if it looks like one."""
    code = (
        "from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases\n"
        f"__getattr__ = deprecated_aliases({_ENTRY.replace('Thing', 'Wrong')}, "
        f"{_ENTRY})\n"
    )
    with griffe.temporary_visited_module(
        code, extensions=griffe.load_extensions(DeprecationsExtension())
    ) as module:
        assert "Thing" in module.members
        assert "Wrong" not in module.members


def test_the_defaults_match_griffe_warnings_deprecated() -> None:
    """Configured beside the decorator extension, both render the same."""
    extension = DeprecationsExtension()
    assert extension.kind == "danger"
    assert extension.title == "Deprecated"
    assert extension.label == "deprecated"


def test_the_admonition_is_configurable() -> None:
    """A project wanting its own admonition style can ask for one."""
    package = load(kind="deprecated", title="No longer supported", label="old")
    member = attribute(package, "oldmod.MAX_WIDGETS")
    assert member.labels == {"old", "module-attribute"}
    sections = admonitions(member)
    assert len(sections) == 1
    assert sections[0].value.kind == "deprecated"
    assert sections[0].title == "No longer supported"


def test_the_label_can_be_dropped() -> None:
    """Passing no label leaves the object's labels as Griffe found them."""
    member = attribute(load(label=None), "oldmod.MAX_WIDGETS")
    assert member.labels == {"module-attribute"}
    assert isinstance(member.deprecated, str)


def test_show_target_keeps_the_private_name_when_off() -> None:
    """Turning it off leaves the assignment Griffe read from the source."""
    member = attribute(load(show_target=False), "oldmod.Widget")
    assert member.value == ExprName("_Widget")


def test_the_default_message_is_configurable() -> None:
    """A project may word the documented message its own way."""
    package = load(
        default_message="{old} is gone since {since}, see {new} or {new_link}."
    )
    member = attribute(package, "oldmod.MAX_WIDGETS")
    assert member.deprecated == (
        "samplepkg.oldmod.MAX_WIDGETS is gone since v1.4.0, see "
        "samplepkg.newmod.MAX_WIDGETS or [`samplepkg.newmod.MAX_WIDGETS`][]."
    )
    # An entry without `since` can't use it.
    assert attribute(package, "oldmod2.Thing").deprecated == (
        "Deprecated. Use [`samplepkg.newmod.Widget`][] instead."
    )


def test_only_the_configured_paths_match() -> None:
    """Pointed somewhere else, the extension finds nothing to mark."""
    package = load(
        alias_table_functions=["mypkg.compat.moved_to"],
        alias_classes=["mypkg.compat.Moved"],
        member_wrapper_functions=["mypkg.compat.retired"],
    )
    assert "deprecated" not in attribute(package, "oldmod.Widget").labels
    assert not attribute(package, "oldmod2.Thing").deprecated
    assert not attribute(package, "statuses.TaskStatus.PENDING").deprecated
    # `Hidden` exists only because the extension creates it.
    assert "Hidden" not in package["edge"].members


def test_extra_paths_can_be_added() -> None:
    """A project may match its own helpers as well as the frequenz-core ones."""
    package = load(
        alias_table_functions=[_ALIASES, "mypkg.compat.moved_to"],
        alias_classes=[_ALIAS_CLASS, "mypkg.compat.Moved"],
        member_wrapper_functions=[_MEMBERS, "mypkg.compat.retired"],
    )
    assert "deprecated" in attribute(package, "oldmod.Widget").labels
    assert "deprecated" in attribute(package, "statuses.TaskStatus.PENDING").labels


def test_only_the_configured_alias_classes_match() -> None:
    """An entry built by an unconfigured class is skipped, a configured one read."""
    code = (
        "from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases\n"
        "from mypkg.compat import Moved\n"
        "__getattr__ = deprecated_aliases(\n"
        "    __name__,\n"
        "    Moved('Mine', new_module='pkg.new', message='{old} gone.'),\n"
        "    DeprecatedAlias('Core', new_module='pkg.new', message='{old} gone.'),\n"
        ")\n"
    )
    extension = DeprecationsExtension(alias_classes=["mypkg.compat.Moved"])
    with griffe.temporary_visited_module(
        code, extensions=griffe.load_extensions(extension)
    ) as module:
        assert "deprecated" in attribute(module, "Mine").labels
        assert "Core" not in module.members
