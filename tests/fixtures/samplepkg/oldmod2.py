# License: MIT
# Copyright © 2026 Frequenz Energy-as-a-Service GmbH

"""Another old home, importing the helpers through a module alias.

The alias gives a message of its own rather than `since`, which is only its
runtime warning, so its notice can't say since which version it is deprecated.
The call passes keyword arguments that don't change the documentation.
"""

from typing import TYPE_CHECKING, TypeAlias

from frequenz.core import warnings as w

if TYPE_CHECKING:
    from samplepkg.newmod import Widget as _Widget

    Thing: TypeAlias = _Widget
    """A thing."""
else:
    __getattr__ = w.deprecated_aliases(
        __name__,
        w.DeprecatedAlias(
            "Thing",
            new_module="samplepkg.newmod",
            new_name="Widget",
            message="{old} moved to {new} in v2.0.0 " "and will be removed in v3.0.0.",
        ),
        category=FutureWarning,
        stacklevel=3,
    )
