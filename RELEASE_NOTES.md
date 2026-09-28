# Griffe Extensions for frequenz-core Release Notes

## Summary

This release follows the final `frequenz.core.warnings.deprecated_aliases()` API released in `frequenz-core` v1.5.0, where every alias is a `DeprecatedAlias` entry saying where the symbol is now, with `new_module`, `new_name` or both, and either the version it is deprecated since or a runtime message of its own, so each alias carries its own notice.

It also follows the [deprecations guide](https://github.com/frequenz-floss/docs/blob/v0.x.x/python/deprecations.md), which separates the runtime warning, written for a terminal, from the notice in the documentation, which says since which version and links what to use instead. Notices are generated where the code says that, a hand-written `Deprecated:` notice always replaces a generated one, and anything short of what the guide asks for is logged as a warning.

## Upgrading

- The `default_message` option is now the notice of every alias, and its default changed to `Deprecated since {since}. Use {new_link} instead.`. `{old}` and `{new}` are now plain paths, `{new_link}` is a code font link to the target, showing only its name when the target is in the same module, and the result is rendered as Markdown. If you set it, add `{since}`, and use `{new_link}` or write the link yourself, as in ``[`{new}`][]``.
- An alias' `message` is now only its runtime warning, and no longer its notice: an alias giving `message` instead of `since` is documented as ``Deprecated. Use [`<new>`][] instead.``, with a warning. Write a `Deprecated:` notice by hand in the docstring of the alias declared for type checkers to say more.
- An enum member deprecated with `deprecated_member()` only has a runtime warning, so it now needs a hand-written `Deprecated:` notice. Without one, its runtime warning is still shown as its notice, but a warning is logged.
- Anything the documentation cannot show as the guide asks for is now logged as a warning, so `mkdocs build --strict` fails on it: a notice without the version or the replacement, a runtime warning shown as a notice, a value left as written, a deprecation left unmarked or a call whose arguments don't bind the way the runtime binds them. Write the arguments as string literals, or write the `Deprecated:` notice by hand. Unresolvable alias targets are reported by `mkdocs-autorefs` too; add the target project's inventory to resolve them.

## New Features

- New `alias_classes` option, defaulting to `frequenz.core.warnings.DeprecatedAlias`, listing the callables that build one alias entry, for projects using a helper of their own.
- A hand-written `Deprecated:` notice on an alias or enum member is moved to the top of its docstring, where generated notices go, so all notices are in the same place.

## Bug Fixes

- `griffe_frequenz_core.deprecations` now reads the call shape `frequenz-core` actually released:

  ```python
  __getattr__ = deprecated_aliases(
      __name__,
      DeprecatedAlias("Old", new_module="pkg.new", since="v1.2.0"),
  )
  ```

  v1.0.0 read an earlier dict form, `deprecated_aliases(__name__, {"Old": "pkg.new"}, message="...")`, which never made it into a `frequenz-core` release and is no longer read. Entries are read one by one, so one that cannot be read does not affect the others.

- An alias is documented as ``Deprecated since <since>. Use [`<new>`][] instead.``, without repeating the name of the alias it documents, and linking a target in the same module by its name alone.

- A deprecation whose arguments cannot be read statically is now documented with a generic notice instead of being left unmarked, saying as much as can be read: since which version and what to use instead when those are known, and only that it will be removed in a future release when neither is. For an alias, only its name has to be a string literal, and its value is rewritten to the target when `new_module` and `new_name` can be read. For an enum member, such as `BREAKER = deprecated_member(7, _member_message("BREAKER"))`, its value is now unwrapped too, showing `BREAKER = 7` instead of the whole wrapper call. A hand-written `Deprecated:` notice is kept instead of the generic one, as before.
