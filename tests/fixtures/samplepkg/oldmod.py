# License: MIT
# Copyright © 2026 Frequenz Energy-as-a-Service GmbH

"""The old home, keeping the old import paths working.

Three shapes on purpose:

- `Widget`: the documented convention, with a hand-written `Deprecated:`
  admonition that the extension must leave alone.
- `Doohickey`: a renamed alias with a docstring but no admonition.
- `MAX_WIDGETS`: an alias with no docstring at all.
"""

from typing import TYPE_CHECKING, TypeAlias

from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases

if TYPE_CHECKING:
    from samplepkg.newmod import Gadget as _Gadget
    from samplepkg.newmod import Widget as _Widget

    Widget: TypeAlias = _Widget
    """A widget that does widget things.

    Deprecated:
        Deprecated since v1.2.0. Use [`samplepkg.newmod.Widget`][] instead,
        and see the migration guide.
    """

    Doohickey: TypeAlias = _Gadget
    """A gadget, formerly known as `Doohickey`."""

    MAX_WIDGETS: int
else:
    __getattr__ = deprecated_aliases(
        __name__,
        DeprecatedAlias("Widget", new_module="samplepkg.newmod", since="v1.2.0"),
        DeprecatedAlias(
            "Doohickey",
            new_module="samplepkg.newmod",
            new_name="Gadget",
            since="v1.3.0",
        ),
        DeprecatedAlias("MAX_WIDGETS", new_module="samplepkg.newmod", since="v1.4.0"),
    )
