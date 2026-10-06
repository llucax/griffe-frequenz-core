# AGENTS.md

Griffe extensions documenting what `frequenz-core` helpers express through calls. Run `nox` and `mkdocs build --strict` before committing.

## Rules

- Read the documented code statically only: never import or run it, and use only string literals written in the call.
- Mirror `frequenz-core`'s runtime semantics (argument binding, defaults, path resolution) exactly, and check them in `tests/compat` against the pinned core. Don't validate argument values beyond that: documenting is not linting.
- Follow the deprecations guide (frequenz-floss/docs `python/deprecations.md`): the runtime warning is for a terminal, the notice for the docs, saying since which version and linking what to use instead.
- Document as much as can be read, the same way for every helper: mark whatever can be identified, and fill in what can't be read with generic text.
- Never degrade silently: a notice short of what the guide asks for, or anything else the docs can't show in full, logs a warning, so `--strict` fails. Debug logs only explain why.
- Show a runtime warning as the notice only when nothing better can be generated or was written by hand: as written, as Markdown, and with a warning.
- A hand-written notice always wins; on objects the extension marks, move it to the top of the docstring.
- Text the extension writes itself is docs-only: don't repeat the documented symbol's name, and link symbols in code font, as in ``[`pkg.Name`][]``, or ``[`Name`][pkg.Name]`` in the same module.
- Never make links optional: an unresolvable link must be reported.
- Keep README, docstrings, tests and release notes in step with every behavior change.
