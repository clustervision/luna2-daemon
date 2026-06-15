Contribution Guidelines
=======================

Coding guidelines
-----------------

These are baseline expectations for code contributed to this project. They are
not exhaustive; when in doubt, match the style of the surrounding code.

Linting and formatting
~~~~~~~~~~~~~~~~~~~~~~~~

- Follow `PEP 8 <https://peps.python.org/pep-0008/>`_ for layout and indentation
  (4 spaces, never tabs).
- Keep lines within 120 characters.
- Run ``pylint`` over your changes before opening a pull request, and fix the
  warnings rather than silencing them.

Naming
~~~~~~

- Use ``snake_case`` for variables, functions, and module names — not
  ``camelCase``.
- Use ``PascalCase`` for class names, and ``UPPER_CASE`` for module-level
  constants.
- Names should describe intent, not implementation. Avoid single-letter names
  except for short-lived loop counters.

Functions and structure
~~~~~~~~~~~~~~~~~~~~~~~~~

- A function should do one thing. If you need the word "and" to describe it,
  split it.
- Keep functions short enough to read without scrolling.
- Add type hints to function signatures.
- Give every module, class, and public function a docstring describing what it
  is for.
- No dead code: no commented-out blocks, unused imports, or unused variables.

Error handling and safety
~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Handle errors explicitly; a failure must be visible, never silently swallowed.
- Validate input at system boundaries (user input, API responses), not inside
  trusted internal code.
- No hardcoded secrets or environment-specific values — use configuration files
  or environment variables.

Logging and comments
~~~~~~~~~~~~~~~~~~~~~~

- Prefer a logger over ``print()`` for anything beyond a throwaway script.
- Comments explain *why* when it is non-obvious, not *what* the code does.

Legal
-----

Contributions and waiver of claims
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By submitting any contribution to this project — including but not limited to
source code, configuration, documentation, patches, or pull requests — you
irrevocably and unconditionally waive any and all claims of ownership,
authorship, compensation, or any other right or interest in that contribution,
both now and at any time in the future.

This waiver applies in full regardless of the capacity in which the
contribution is made. It applies whether you contribute as an individual or on
behalf of, in the name of, or as a representative of any other person, company,
organisation, or other legal entity. No such company or organisation may assert
any claim over a contribution on the basis that the contributor acted in its
name.

A contribution, once submitted, is permanently waived from any claim. This
waiver is perpetual and irrevocable, and cannot be withdrawn, reversed, or
limited at any later date by the contributor or by any party on whose behalf the
contributor acted.

That said, the legal wording above is only there to keep things clear and
unencumbered for everyone. It takes nothing away from how much we value your
help: every contribution, large or small, is genuinely appreciated, and we are
grateful to everyone who takes the time to make this project better.
