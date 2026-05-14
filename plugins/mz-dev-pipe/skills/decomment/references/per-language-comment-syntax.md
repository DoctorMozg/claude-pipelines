# Per-Language Comment Syntax + Preserve Markers

Grep this file by extension or language name. Each section gives the proposer the comment tokens and the language-specific preserve markers it must respect.

## .py / .pyi (Python)

Line comment: `#`
Block / docstring: triple-quoted strings `"""..."""` or `'''...'''` at start of module/class/function body.
String literals: `"..."`, `'...'`, `f"..."`, `r"..."`, `b"..."`, plus triple-quoted forms.
Preserve markers (drop entire comment/block if any present):

- Sphinx fields: `:param`, `:type`, `:return`, `:returns`, `:raises`, `:yields`
- Google/NumPy: `Args:`, `Returns:`, `Raises:`, `Yields:`, `Examples:`, `Note:`
- Doctest: `>>>`
- Type comments: `# type:`, `# type: ignore`
- Pyright/mypy: `# pyright:`, `# mypy:`
- Linters: `# noqa`, `# pylint:`, `# flake8:`, `# ruff:`, `# fmt:`
- Pragma: `# pragma:`
- Cython: `# cython:`
- Encoding: `# -*- coding:`, `# coding:`
- Editor: `# vim:`, `# emacs:`

Tokenizer notes:

- Triple-quoted strings can be docstrings (first statement of a module/class/function body) OR regular string literals — distinguish by AST position. If unable to AST-parse, treat as docstring only when it is the first non-blank/non-comment statement at module/class/def scope.
- f-string braces `{...}` contain expressions; do not tokenize their interiors as code.

## .sh / .bash / .zsh (Shell)

Line comment: `#`
Block: none (heredocs are NOT comments — `<<EOF ... EOF` blocks are string literals).
String literals: `'...'`, `"..."`, `$'...'`, heredocs `<<EOF`, `<<-EOF`, `<<'EOF'`.
Preserve markers:

- Shebang: `#!` as line 1 (never edit).
- ShellCheck: `# shellcheck disable=`, `# shellcheck source=`
- Encoding: `# coding:`

Tokenizer notes:

- A `#` inside double-quoted or single-quoted string is NOT a comment.
- Heredoc bodies are strings, not comments.

## .ts / .tsx / .js / .jsx / .mjs / .cjs (TypeScript / JavaScript)

Line comment: `//`
Block comment: `/* ... */`
JSDoc: `/** ... */`
String literals: `"..."`, `'...'`, template literals `` `...${expr}...` ``, regex `/.../flags`.
Preserve markers:

- JSDoc tags: `@param`, `@returns`, `@throws`, `@example`, `@deprecated`, `@since`, `@see`, `@template`, `@typedef`, `@callback`
- TS directives: `// @ts-ignore`, `// @ts-expect-error`, `// @ts-nocheck`, `// @ts-check`
- Linters: `// eslint-disable*`, `// prettier-ignore`, `// biome-ignore`, `// rome-ignore`, `// deno-lint-ignore`
- License: `// @license`, `// @preserve`, `// @flow`
- Source maps: `//# sourceMappingURL=`, `//# sourceURL=`

Tokenizer notes:

- Template-literal interiors `${...}` are expressions; the entire backtick-delimited region is a string and `//` inside it is NOT a comment.
- A `/` after an operator can start a regex literal — the regex body is a string, not a comment.

## .rs (Rust)

Line comment: `//`
Block comment: `/* ... */` (NESTED — must count balanced pairs)
Outer doc-comment: `///` (ALWAYS preserve)
Inner doc-comment: `//!` (ALWAYS preserve)
Block doc-comment: `/** ... */` (preserve as docstring)
String literals: `"..."`, raw strings `r"..."`, `r#"..."#`, byte strings `b"..."`, char `'.'`.
Preserve markers:

- Rustdoc sections: `# Examples`, `# Errors`, `# Panics`, `# Safety`, `# Arguments`
- `# Examples` blocks with ` ` \`\`\` are doctests
- Attributes inside doc-comments: `#[doc=...]`
- Allow/deny/warn: `#[allow]`, `#[deny]`, `#[warn]`, `#[expect]`
- `cfg`: `#[cfg(...)]`
- Safety: `// SAFETY:`, `// INVARIANT:`

Tokenizer notes:

- `///` is a doc-comment ONLY when it's three slashes at start of a comment region; `////` is a regular line comment.
- Block comments nest — `/* /* */ */` is one comment.

## .cpp / .cc / .cxx / .c / .h / .hpp / .hxx / .hh (C / C++)

Line comment: `//`
Block comment: `/* ... */`
Doxygen: `///`, `//!`, `/** ... */`, `/*! ... */`
String literals: `"..."`, `'.'`, raw `R"delim(...)delim"`, wide `L"..."`, `u8"..."`, `u"..."`, `U"..."`.
Preserve markers:

- Doxygen tags: `@param`, `@return`, `@brief`, `@throws`, `@see`, `\param`, `\return`, etc.
- clang-format: `// clang-format off`, `// clang-format on`
- NOLINT: `// NOLINT`, `// NOLINTNEXTLINE`, `// NOLINTBEGIN`, `// NOLINTEND`
- Coverity, cppcheck pragmas
- License headers in top 30 lines

Tokenizer notes:

- Raw strings `R"delim(...)delim"` can contain anything including `//` — treat as opaque string.
- Trigraphs are obsolete; do not parse.

## .go (Go)

Line comment: `//`
Block comment: `/* ... */`
String literals: `"..."`, `` `...` ``, `'.'` (rune).
Preserve markers:

- Doc comments: a comment immediately preceding a package/type/func declaration is the doc — preserve.
- Build tags: `//go:build`, `// +build` (legacy)
- Codegen: `//go:generate`, `//go:embed`, `//go:linkname`, `//go:noinline`
- nolint: `//nolint:`

Tokenizer notes:

- Backtick strings are raw strings — they contain no comments.

## .java / .kt (Java / Kotlin)

Line comment: `//`
Block comment: `/* ... */`
Javadoc/KDoc: `/** ... */`
String literals: `"..."`, `'.'`, text blocks `"""..."""` (Java 13+, Kotlin multiline).
Preserve markers:

- Javadoc tags: `@param`, `@return`, `@throws`, `@author`, `@since`, `@deprecated`, `@see`, `{@link ...}`, `{@code ...}`
- SuppressWarnings annotations
- License headers
- IntelliJ: `// noinspection`

## .swift (Swift)

Line comment: `//`
Block comment: `/* ... */` (nested allowed)
Doc-comment: `///`, `/** */`
String literals: `"..."`, multiline `"""..."""`, extended `#"..."#`.
Preserve markers:

- Markup: `- Parameter`, `- Parameters:`, `- Returns:`, `- Throws:`, `- Important:`, `- Note:`, `- Warning:`
- `// MARK:`, `// TODO:`, `// FIXME:` — preserve (navigational/WHY)
- `// swift-format-ignore`, `// swiftlint:disable`

## .cs (C#)

Line comment: `//`
Block comment: `/* ... */`
XML doc: `///` or `/** */`
String literals: `"..."`, `@"..."`, `$"..."`, `$@"..."`, raw `"""..."""`.
Preserve markers:

- XML doc tags: `<summary>`, `<param>`, `<returns>`, `<exception>`, `<remarks>`, `<example>`, `<see>`, `<seealso>`, `<typeparam>`, `<inheritdoc>`
- `#pragma warning`, `#nullable enable/disable`
- `// SuppressMessage`

## .rb (Ruby)

Line comment: `#`
Block comment: `=begin ... =end` (must be at column 0)
String literals: `"..."`, `'...'`, `%q{...}`, `%Q{...}`, heredocs `<<HEREDOC`.
Preserve markers:

- YARD tags: `@param`, `@return`, `@raise`, `@example`, `@see`, `@since`, `@deprecated`
- Magic comments: `# frozen_string_literal:`, `# encoding:`, `# coding:`, `# warn_indent:`
- Rubocop: `# rubocop:disable`, `# rubocop:enable`
- TypeProf/Sorbet: `# typed:`

## .php (PHP)

Line comment: `//`, `#`
Block comment: `/* ... */`
PHPDoc: `/** ... */`
String literals: `"..."`, `'...'`, heredocs `<<<EOT`, nowdocs `<<<'EOT'`.
Preserve markers:

- PHPDoc tags: `@param`, `@return`, `@throws`, `@var`, `@method`, `@property`, `@api`, `@internal`, `@deprecated`, `@since`
- License headers

## Common WHY tokens (every language)

Drop any comment/block if any line contains (case-insensitive):
`because`, `since`, `due to`, `workaround`, `hack`, `XXX`, `FIXME`, `HACK`, `bug`, `issue`, `RFC`, `CVE`, `kernel`, `regression`, `compatibility`, `legacy`, `historical`, `deprecated`, `previously`, `originally`, `intentionally`, `deliberately`.

Plus tokens of the form: year (`19XX` or `20XX`), `#NNNN`, `JIRA-NNNN`, `gh-NNNN`, any URL (`http://`, `https://`).

## Common license markers (top 30 lines of file)

`Copyright`, `License`, `SPDX-License-Identifier`, `Licensed under`, `(c)` + year, `All rights reserved`.
