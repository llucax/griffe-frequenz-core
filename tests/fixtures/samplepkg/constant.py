# License: MIT
# Copyright © 2026 Frequenz Energy-as-a-Service GmbH

"""An alias entry Griffe cannot read, because it is held in a constant.

Nothing here is executed, so the extension never learns what `_THING` holds.
`Thing` stays unmarked, and the skip has to be logged rather than silent.
"""

from typing import TYPE_CHECKING, TypeAlias

from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases

_THING = DeprecatedAlias(
    "Thing", new_module="samplepkg.newmod", new_name="Widget", since="v1.0.0"
)

if TYPE_CHECKING:
    from samplepkg.newmod import Widget as _Widget

    Thing: TypeAlias = _Widget
    """A thing."""
else:
    __getattr__ = deprecated_aliases(__name__, _THING)
