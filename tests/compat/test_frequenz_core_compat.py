# License: MIT
# Copyright © 2026 Frequenz Energy-as-a-Service GmbH

"""Compatibility tests against the installed `frequenz-core`.

Every other test in this suite is static: Griffe resolves the helper names out
of a fixture's import statement, so those tests never import `frequenz-core`
and pass with it uninstalled. These are the opposite, and the only ones that
import it. They pin the part of the contract this package depends on but does
not own, by running the real helper and comparing what it does at runtime with
what we put in the documentation.

`test_documented_message_matches_runtime_warning` is the one that earns its
keep. Nothing else would notice if `frequenz-core` started wrapping or
reformatting the message, because the extension reads it out of the syntax
tree and never executes it. That is precisely the drift that would leave the
documentation quietly saying something no user ever sees.

An alias' notice is worded for the documentation and links the new path, so it
is compared with the runtime warning only by what both have to say: since which
version, and what to use instead. Those comparisons strip the reference markup
and nothing else.
"""

import inspect
import re
import warnings
from pathlib import Path
from typing import Any

import frequenz.core.enum
import frequenz.core.warnings
import griffe
import pytest

from griffe_frequenz_core.deprecations import DeprecationsExtension

from . import fixture_aliases, fixture_enum

_FIXTURES = Path(__file__).parent


@pytest.fixture(name="task_status", scope="module")
def task_status_fixture() -> griffe.Class:
    """Load the fixture module with the extension applied.

    Returns:
        The `TaskStatus` class as Griffe sees it.
    """
    module = griffe.load(
        "fixture_enum",
        search_paths=[_FIXTURES],
        extensions=griffe.load_extensions(DeprecationsExtension()),
        docstring_parser=griffe.Parser.google,
    )
    task_status = module["TaskStatus"]
    assert isinstance(task_status, griffe.Class)
    return task_status


@pytest.fixture(name="pending_warning")
def pending_warning_fixture() -> warnings.WarningMessage:
    """Reach the deprecated member and capture the warning it emits.

    Returns:
        The single warning the real `frequenz-core` raised.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _ = fixture_enum.TaskStatus.PENDING

    assert len(caught) == 1, f"expected exactly one warning, got {len(caught)}"
    return caught[0]


def test_real_helper_is_recognized(task_status: griffe.Class) -> None:
    """The extension finds a `deprecated_member()` call written against real core."""
    pending = task_status["PENDING"]

    assert pending.deprecated
    assert "deprecated" in pending.labels
    # The wrapper call is replaced by the value the member really takes.
    assert str(pending.value) == "1"


def test_documented_message_matches_runtime_warning(
    task_status: griffe.Class,
    pending_warning: warnings.WarningMessage,
) -> None:
    """The documented text is exactly the text the runtime warning carries.

    Deliberately compares the two sources against each other rather than
    against a third copy in this file, so the test cannot pass by agreeing with
    a stale expectation.
    """
    assert str(pending_warning.message) == task_status["PENDING"].deprecated
    assert issubclass(pending_warning.category, DeprecationWarning)


def test_admonition_is_rendered(task_status: griffe.Class) -> None:
    """The message reaches the docstring as an admonition, not only as a field."""
    pending = task_status["PENDING"]
    assert pending.docstring is not None
    sections = pending.docstring.parsed

    assert sections[0].kind is griffe.DocstringSectionKind.admonition
    assert sections[0].title == "Deprecated"
    assert sections[0].value.contents == pending.deprecated
    # The member's own prose survives, after the admonition.
    assert [section.kind for section in sections[1:]] == [
        griffe.DocstringSectionKind.text
    ]


@pytest.mark.parametrize(
    "wrapper",
    [frequenz.core.enum.deprecated_member, frequenz.core.enum.DeprecatedMember],
)
def test_wrapper_parameters_are_value_and_message(wrapper: Any) -> None:
    """The keyword names the extension binds are the ones core really takes.

    The extension reads `deprecated_member(value=..., message=...)` by those two
    names, so a rename in core would leave keyword calls unmarked.
    """
    bound = inspect.signature(wrapper).bind(value=1, message="Gone")
    assert bound.arguments == {"value": 1, "message": "Gone"}


def test_plain_member_is_left_alone(task_status: griffe.Class) -> None:
    """A member with no `deprecated_member()` call is untouched, and stays silent."""
    open_member = task_status["OPEN"]

    assert open_member.deprecated is None
    assert "deprecated" not in open_member.labels

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _ = fixture_enum.TaskStatus.OPEN

    assert not caught


def _plain(documented: str) -> str:
    """Strip the code-font references from a documented deprecation message.

    Args:
        documented: The documented deprecation message.

    Returns:
        The message with each ``[`path`][]`` and ``[`name`][path]`` replaced by
            the plain path.
    """
    documented = re.sub(r"\[`[\w.]+`\]\[([\w.]+)\]", r"\1", documented)
    return re.sub(r"\[`([\w.]+)`\]\[\]", r"\1", documented)


@pytest.fixture(name="aliases_module", scope="module")
def aliases_module_fixture() -> griffe.Module:
    """Load the alias fixture with the extension applied, under its runtime name.

    The runtime warning fills `{old}` from the module's `__name__`, so Griffe
    has to know the module by the same dotted path pytest imported it as.

    Returns:
        The fixture module as Griffe sees it.
    """
    name = fixture_aliases.__name__
    search_path = Path(fixture_aliases.__file__).parents[name.count(".")]
    module = griffe.load(
        name,
        search_paths=[search_path],
        extensions=griffe.load_extensions(DeprecationsExtension()),
        docstring_parser=griffe.Parser.google,
    )
    assert isinstance(module, griffe.Module)
    return module


def _alias_warning(name: str) -> warnings.WarningMessage:
    """Reach a deprecated alias and capture the warning it emits.

    Args:
        name: The alias to reach.

    Returns:
        The single warning the real `frequenz-core` raised.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _ = getattr(fixture_aliases, name)

    assert len(caught) == 1, f"expected exactly one warning, got {len(caught)}"
    return caught[0]


@pytest.mark.parametrize(
    ("name", "target"),
    [
        ("Decimal", "decimal.Decimal"),
        ("Rational", "fractions.Fraction"),
        ("Gadget", f"{fixture_aliases.__name__}.Widget"),
        ("Number", "numbers.Number"),
    ],
)
def test_real_alias_helper_is_recognized(
    aliases_module: griffe.Module, name: str, target: str
) -> None:
    """The extension finds every `DeprecatedAlias` written against real core."""
    alias = aliases_module[name]

    assert alias.deprecated
    assert "deprecated" in alias.labels
    assert alias.value == griffe.ExprName(target)


@pytest.mark.parametrize(
    ("name", "target"),
    [("Rational", "fractions.Fraction"), ("Number", "numbers.Number")],
)
def test_alias_message_is_only_the_runtime_warning(
    aliases_module: griffe.Module, name: str, target: str
) -> None:
    """An alias giving its own message warns with it, but documents its target.

    The message is written for a terminal, so the notice says what to use
    instead, the same target the runtime resolves.
    """
    warning = _alias_warning(name)

    assert str(warning.message).startswith(f"{fixture_aliases.__name__}.{name} ")
    assert issubclass(warning.category, DeprecationWarning)
    assert _plain(str(aliases_module[name].deprecated)) == (
        f"Deprecated. Use {target} instead."
    )


@pytest.mark.parametrize(
    ("name", "since", "target"),
    [
        ("Decimal", "v1.2.0", "decimal.Decimal"),
        ("Gadget", "v1.4.0", f"{fixture_aliases.__name__}.Widget"),
    ],
)
def test_since_alias_documents_the_runtime_version_and_target(
    aliases_module: griffe.Module, name: str, since: str, target: str
) -> None:
    """An alias giving `since` documents the version and target it warns about.

    The documented message is worded for the documentation, so it is not the
    runtime warning, but both have to say the same version and the same
    replacement. `Gadget` gives no `new_module`, so this also checks that both
    resolve it to the module defining the alias.
    """
    runtime = str(_alias_warning(name).message)
    documented = _plain(str(aliases_module[name].deprecated))

    for part in (f"since {since}.", f"Use {target} instead."):
        assert part in runtime
        assert part in documented


def test_alias_entry_parameters_match_the_extension() -> None:
    """`DeprecatedAlias` takes the name by position and the rest by keyword.

    The extension binds `DeprecatedAlias(name, /, *, new_module=None,
    new_name=None, since=None, message=None)`, so a change in how core takes any
    of them would leave entries unmarked.
    """
    parameters = inspect.signature(frequenz.core.warnings.DeprecatedAlias).parameters
    assert {name: parameter.kind for name, parameter in parameters.items()} == {
        "name": inspect.Parameter.POSITIONAL_ONLY,
        "new_module": inspect.Parameter.KEYWORD_ONLY,
        "new_name": inspect.Parameter.KEYWORD_ONLY,
        "since": inspect.Parameter.KEYWORD_ONLY,
        "message": inspect.Parameter.KEYWORD_ONLY,
    }


def test_alias_table_takes_entries_after_the_module() -> None:
    """`deprecated_aliases()` takes the module, then the entries, by position.

    The extension reads every positional argument after the first as an entry
    and ignores keywords, which is only right with this parameter layout.
    """
    parameters = list(
        inspect.signature(frequenz.core.warnings.deprecated_aliases).parameters.values()
    )
    assert [parameter.kind for parameter in parameters[:2]] == [
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.VAR_POSITIONAL,
    ]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters[2:]
    )
