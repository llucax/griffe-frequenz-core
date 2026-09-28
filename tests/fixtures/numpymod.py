# License: MIT
# Copyright © 2026 Frequenz Energy-as-a-Service GmbH

"""An alias documenting its own deprecation in numpy style.

Google style turns a `Deprecated:` section into an admonition, numpy style turns
it into a section of its own kind. Both mean the same thing, and the extension
has to keep its hands off either.
"""

from typing import TYPE_CHECKING, TypeAlias

from frequenz.core.warnings import DeprecatedAlias, deprecated_aliases

if TYPE_CHECKING:
    from samplepkg.newmod import Widget as _Widget

    Widget: TypeAlias = _Widget
    """A widget that does widget things.

    Deprecated
    ----------
    1.2.0
        Use ``samplepkg.newmod.Widget`` instead.
    """
else:
    __getattr__ = deprecated_aliases(
        __name__,
        DeprecatedAlias("Widget", new_module="samplepkg.newmod", since="v1.2.0"),
    )
