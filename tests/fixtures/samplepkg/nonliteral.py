# License: MIT
# Copyright © 2026 Frequenz Energy-as-a-Service GmbH

"""Deprecations written in a way Griffe cannot read.

Nothing here is executed, so a message or an alias name that is not a string
literal right there in the call cannot be recovered. `Thing` has a message held
in a constant, which doesn't matter, since a message is never documented. The
entry named by a constant has no name Griffe can see, so it is skipped, while
`Kept`, written out in full, is still marked.
"""

from typing import TYPE_CHECKING, TypeAlias

from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases

_MESSAGE = "{old} went away, see {new}."
_LOST = "Lost"

if TYPE_CHECKING:
    from samplepkg.newmod import Gadget as _Gadget
    from samplepkg.newmod import Widget as _Widget

    Thing: TypeAlias = _Widget
    """A thing."""

    Kept: TypeAlias = _Gadget
    """A gadget kept under an old name."""
else:
    __getattr__ = deprecated_aliases(
        __name__,
        DeprecatedAlias(
            "Thing",
            new_module="samplepkg.newmod",
            new_name="Widget",
            message=_MESSAGE,
        ),
        DeprecatedAlias(
            _LOST, new_module="samplepkg.newmod", new_name="Gadget", since="v1.0.0"
        ),
        DeprecatedAlias(
            "Kept", new_module="samplepkg.newmod", new_name="Gadget", since="v1.0.0"
        ),
    )
