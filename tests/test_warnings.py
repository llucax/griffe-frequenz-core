# License: MIT
# Copyright © 2026 Frequenz Energy-as-a-Service GmbH

"""Tests for what the deprecations extension warns about.

Any deprecation the documentation shows less well than the deprecations guide
asks for, because something cannot be read statically or because the code
only carries a runtime warning, must fail a strict `mkdocs` build, so it is
logged as a warning. Only the details of why are logged at debug level.
"""

import logging
from typing import Any

import griffe
import pytest
from griffe import Parser

from griffe_frequenz_core.deprecations import DeprecationsExtension

_LOGGER = "griffe_frequenz_core.deprecations"


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return the warnings the extension logged.

    Args:
        caplog: The captured log records.

    Returns:
        The message of every warning logged by the extension.
    """
    return [
        record.message
        for record in caplog.records
        if record.name == _LOGGER and record.levelno == logging.WARNING
    ]


@pytest.mark.parametrize(
    ("code", "warned"),
    [
        (
            "from frequenz.core.enum import Enum, deprecated_member\n"
            "class Status(Enum):\n"
            "    A = deprecated_member(7, _MESSAGE)\n",
            "A: the deprecation message cannot be read statically",
        ),
        (
            "from frequenz.core.enum import Enum, deprecated_member\n"
            "class Status(Enum):\n"
            "    A = deprecated_member(7, 'mod.Status.A is deprecated.')\n",
            "A: there is no notice written for the documentation, so the runtime "
            "warning is shown instead",
        ),
        (
            "from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases\n"
            "__getattr__ = deprecated_aliases(\n"
            "    __name__, DeprecatedAlias('A', new_module='pkg.new', since=SINCE)\n"
            ")\n",
            "A: the notice can't say since which version it is deprecated",
        ),
        (
            "from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases\n"
            "__getattr__ = deprecated_aliases(\n"
            "    __name__, DeprecatedAlias('A', new_module='pkg.new', message='Gone')\n"
            ")\n",
            "A: the notice can't say since which version it is deprecated",
        ),
    ],
    ids=["enum-unreadable", "enum-runtime-only", "alias-unreadable", "alias-message"],
)
def test_a_notice_short_of_the_guide_is_warned_about(
    caplog: pytest.LogCaptureFixture, code: str, warned: str
) -> None:
    """The docs say less than the guide asks for, which a strict build must see."""
    with (
        caplog.at_level(logging.DEBUG, logger=_LOGGER),
        griffe.temporary_visited_module(
            code, extensions=griffe.load_extensions(DeprecationsExtension())
        ),
    ):
        pass
    [warning] = _warnings(caplog)
    assert warned in warning
    assert warning.endswith("; write the `Deprecated:` notice by hand")


@pytest.mark.parametrize("message", ["_MESSAGE", "'mod.Status.A is deprecated.'"])
def test_a_handwritten_notice_silences_the_generated_one(
    caplog: pytest.LogCaptureFixture, message: str
) -> None:
    """With the admonition written by hand, nothing is missing from the docs."""
    code = (
        "from frequenz.core.enum import Enum, deprecated_member\n"
        "class Status(Enum):\n"
        f"    A = deprecated_member(7, {message})\n"
        '    """A status.\n\n    Deprecated:\n        Use B instead.\n    """\n'
    )
    with (
        caplog.at_level(logging.DEBUG, logger=_LOGGER),
        griffe.temporary_visited_module(
            code,
            docstring_parser=Parser.google,
            extensions=griffe.load_extensions(DeprecationsExtension()),
        ),
    ):
        pass
    assert not _warnings(caplog)


def test_a_message_from_another_extension_silences_the_generic_one(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A message an earlier extension found is documented, so nothing is missing."""

    class Earlier(griffe.Extension):
        """Stand in for an extension that runs first and finds a message."""

        def on_attribute_instance(
            self, *, attr: griffe.Attribute, **kwargs: Any
        ) -> None:
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
    with (
        caplog.at_level(logging.DEBUG, logger=_LOGGER),
        griffe.temporary_visited_module(
            code, extensions=griffe.load_extensions(Earlier(), DeprecationsExtension())
        ),
    ):
        pass
    assert not _warnings(caplog)


@pytest.mark.parametrize(
    ("arguments", "warned"),
    [
        ("__name__, *ENTRIES", "are unpacked, leaving them unmarked"),
        ("__name__, ENTRY", "is not a call to a known alias class"),
        (
            "__name__, DeprecatedAlias(NAME, new_module='pkg.new', since='v1')",
            "is not a static string, skipping it",
        ),
        ("__name__, DeprecatedAlias(*ARGS, since='v1')", "are unpacked, skipping it"),
        (
            "__name__, DeprecatedAlias('A', since='v1')",
            "does not take exactly a positional name",
        ),
        (
            "__name__, DeprecatedAlias('A', new_module=TARGET, since='v1')",
            "the target of the alias cannot be read statically",
        ),
        ("__name__, DeprecatedAlias('A', new_module='pkg.new', since='v1')", None),
    ],
)
def test_an_alias_that_cannot_be_fully_documented_is_warned_about(
    caplog: pytest.LogCaptureFixture, arguments: str, warned: str | None
) -> None:
    """An alias missing from the docs, or with its value unresolved, warns.

    So does an entry whose arguments don't bind the way the runtime binds them,
    since the documentation doesn't show it as a deprecation either, while one
    read in full doesn't. The unresolved value also leaves the notice without
    a target, which is warned about separately.
    """
    code = (
        "from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases\n"
        f"__getattr__ = deprecated_aliases({arguments})\n"
    )
    with (
        caplog.at_level(logging.DEBUG, logger=_LOGGER),
        griffe.temporary_visited_module(
            code, extensions=griffe.load_extensions(DeprecationsExtension())
        ),
    ):
        pass
    logged = _warnings(caplog)
    if warned is None:
        assert not logged
    else:
        assert any(warned in message for message in logged)
        assert len(logged) == (2 if "TARGET" in arguments else 1)


@pytest.mark.parametrize(
    ("wrapper", "warned"),
    [
        ("deprecated_member(*ARGS)", "its value is shown as the whole call"),
        ("deprecated_member(1)", "does not take exactly a value and a message"),
        ("deprecated_member(1, 'Gone')", None),
    ],
)
def test_an_enum_member_that_cannot_be_fully_documented_is_warned_about(
    caplog: pytest.LogCaptureFixture, wrapper: str, warned: str | None
) -> None:
    """An enum member whose value or deprecation cannot be shown warns.

    The hand-written notice rules out the warning about a generic message, so
    only the one about the member itself is left.
    """
    code = (
        "from frequenz.core.enum import Enum, deprecated_member\n"
        "class Status(Enum):\n"
        f"    A = {wrapper}\n"
        '    """A status.\n\n    Deprecated:\n        Use B instead.\n    """\n'
    )
    with (
        caplog.at_level(logging.DEBUG, logger=_LOGGER),
        griffe.temporary_visited_module(
            code,
            docstring_parser=Parser.google,
            extensions=griffe.load_extensions(DeprecationsExtension()),
        ),
    ):
        pass
    logged = _warnings(caplog)
    if warned is None:
        assert not logged
    else:
        assert len(logged) == 1
        assert warned in logged[0]
