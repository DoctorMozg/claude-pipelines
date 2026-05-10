# Placeholder Pattern Catalog

Reference for i18n / format-string placeholders that the translator agent must preserve byte-identical through a translation. Grep-first: locate the section for the pattern family you need, read only that section, and apply its regex. Do not load the whole file into context.

Each section has a one-line description, example inputs, PCRE2-compatible regex (ripgrep-usable), framework origin, nesting note, and substitution guidance. The **Combined ripgrep recipe** section is the one-shot command for enumerating every placeholder.

## i18next double brace

**Example**: `{{var}}`, `{{- unescaped}}`, `{{user.name}}`, `{{count}}`

**Frameworks**: i18next, Handlebars, Mustache, LiquidJS.

**Regex (pcre2)**:

```
\{\{-?\s*[A-Za-z0-9_.]+\s*\}\}
```

**Description**: Double-brace interpolation. The leading `-` marks an i18next "unescaped" variant — preserve it verbatim. Dot notation is legal for namespaced keys.

**Nesting**: Never contains translatable text inside the braces — pure variable reference. Safe for flat substitution.

**Substitution**: Replace each match with `[[Pn]]`.

## ICU single brace

**Example**: `{var}`, `{userName}`, `{0}`

**Frameworks**: ICU MessageFormat, Android string resources, Java `MessageFormat`, iOS Foundation, .NET `string.Format` (shares the same syntax family).

**Regex (pcre2)**:

```
\{[A-Za-z0-9_]+\}
```

**Description**: Single-brace variable reference. Matches identifiers only — intentionally excludes ICU plural/select blocks (those start with `{name, ` and are caught by a different regex below).

**Nesting**: None. Pure variable reference.

**Substitution**: Replace each match with `[[Pn]]`. Does not conflict with Python `str.format` — same syntax, same handling.

## ICU plural block

**Example**:

```
{count, plural, one {# item} other {# items}}
{numFiles, plural, =0 {no files} one {one file} other {# files}}
```

**Frameworks**: ICU MessageFormat, FormatJS, react-intl, Fluent (similar).

**Regex (pcre2, requires `rg -P`)**:

```
\{[A-Za-z0-9_]+,\s*plural,\s*(?:(?:=\d+|zero|one|two|few|many|other)\s*\{[^{}]*\}\s*)+\}
```

**Description**: Plural-selection block. The `#` inside the body is a back-reference to the selector variable. Body text inside each category branch IS translatable, but it must be translated per target-language plural rules, not as free prose.

**Nesting**: **Yes — contains translatable text.** Do NOT flatten with naive substitution. See **Nested-placeholder handling** below. The inner bodies can themselves contain other placeholders (e.g. `{count, plural, one {one {item}} other {# {item}s}}`).

**Substitution**: Extract the entire block as one `[[Pn]]` token, translate the bodies separately per target plural-rule set, reassemble.

## ICU select block

**Example**:

```
{gender, select, male {He replied} female {She replied} other {They replied}}
```

**Frameworks**: ICU MessageFormat, FormatJS, react-intl.

**Regex (pcre2, requires `rg -P`)**:

```
\{[A-Za-z0-9_]+,\s*select,\s*(?:[A-Za-z0-9_]+\s*\{[^{}]*\}\s*)+\}
```

**Description**: Discrete-choice branching block. Each branch body is translatable free prose. Branch labels (`male`, `female`, `other`) are identifiers — never translate them.

**Nesting**: **Yes — contains translatable text.** Same handling as plural. Branch count and labels must survive.

**Substitution**: Extract the entire block as `[[Pn]]`, translate bodies separately, reassemble preserving branch labels.

## ICU skeleton

**Example**: `{val, number, ::percent}`, `{d, date, ::yyyyMMMd}`, `{amount, number, ::currency/USD}`

**Frameworks**: ICU MessageFormat v4+ (skeleton syntax), FormatJS, ICU4J.

**Regex (pcre2)**:

```
\{[A-Za-z0-9_]+,\s*(?:number|date|time|duration|spellout|ordinal),\s*::[^{}]*\}
```

**Description**: Formatted value with a format skeleton after `::`. Pattern characters inside the skeleton (`yyyyMMMd`, `percent`, `currency/USD`) are machine-readable format codes — never translate.

**Nesting**: No translatable text.

**Substitution**: Replace the whole block with `[[Pn]]`.

## vue-i18n linked messages

**Example**: `@:common.ok`, `@.upper:brand.name`, `@.lower:menu.file`

**Frameworks**: vue-i18n (Vue 2/3 i18n).

**Regex (pcre2)**:

```
@(?:\.[a-z]+)?:[A-Za-z0-9_.]+
```

**Description**: Link to another translation key. `@.upper:` / `@.lower:` / `@.capitalize:` apply post-lookup modifiers. The target key path is a lookup, not prose. **Never translate the key path**, never rewrite the modifier.

**Nesting**: No.

**Substitution**: Replace the whole reference with `[[Pn]]`.

## i18next nested reference

**Example**: `$t(common.here)`, `$t(buttons.save)`, `$t(errors.notFound)`

**Frameworks**: i18next.

**Regex (pcre2)**:

```
\$t\([A-Za-z0-9_.:-]+\)
```

**Description**: Inline lookup of another translation key. Same semantics as vue-i18n linked messages — pure reference, never translated.

**Nesting**: No.

**Substitution**: Replace with `[[Pn]]`.

## react-i18next Trans numbered

**Example**: `Click <0>here</0> to continue`, `Read the <1>manual</1> first`

**Frameworks**: react-i18next (Trans component, JSX children).

**Regex (pcre2)**:

```
<\d+>[^<]*</\d+>
```

**Description**: Position-indexed JSX child placeholder. The digit refers to the i-th child element of the Trans component in source. **Reordering the tags changes which JSX element wraps which text**, so tag order is load-bearing. Inner text IS translatable.

**Nesting**: The text inside `<0>...</0>` is translatable content. Keep the tag wrapper, translate the inside.

**Substitution**: Translate the inner text in place, preserve the exact `<N>...</N>` wrapper and its number. Do not renumber, do not reorder, do not collapse multiple tags.

## react-i18next Trans named

**Example**: `Click <bold>here</bold>`, `Read the <link>manual</link>`

**Frameworks**: react-i18next v3+, FormatJS rich text formatting.

**Regex (pcre2)**:

```
<[A-Za-z][A-Za-z0-9]*>[^<]*</[A-Za-z][A-Za-z0-9]*>
```

**Description**: Named JSX child placeholder. The tag name maps to a component/function in the Trans `components` prop. Inner text IS translatable, tag names are NOT.

**Nesting**: Inner text is translatable. Tag name must match opening and closing — a typo breaks the render.

**Substitution**: Translate the inner text only. Preserve the tag name verbatim. Do not translate `<bold>` as `<жирный>`.

## printf basic

**Example**: `%s`, `%d`, `%f`, `%i`, `%x`, `%.2f`, `%-10s`

**Frameworks**: C `printf`, Python `%` operator, Java `String.format`, Go `fmt.Printf`, Objective-C `NSString stringWithFormat:`.

**Regex (pcre2)**:

```
%[-+0 #]?[0-9]*(?:\.[0-9]+)?[sdifouxXeEgGcp%]
```

**Description**: Classic printf conversion specifier. Flags, width, precision, and type. A bare `%%` is a literal percent — the regex matches it, which is fine: substituting and restoring works correctly.

**Nesting**: No.

**Substitution**: Replace each match with `[[Pn]]`.

## printf positional

**Example**: `%1$s`, `%2$d`, `%3$.2f`

**Frameworks**: Android `strings.xml`, Java `String.format` with explicit argument indices, POSIX `printf`.

**Regex (pcre2)**:

```
%[0-9]+\$[-+0 #]?[0-9]*(?:\.[0-9]+)?[sdifouxXeEgGcp]
```

**Description**: Positional printf. The `N$` index lets translations reorder arguments without breaking the call site. **Preserve the index** — translating "Hello %1$s, you have %2$d messages" into a language with different word order requires keeping `%1$s` and `%2$d` identical, though their textual position in the sentence may swap.

**Nesting**: No.

**Substitution**: Replace each match with `[[Pn]]`. Reordering of tokens in the translated sentence is allowed and expected.

## iOS / Objective-C

**Example**: `%@`, `%li`, `%lu`, `%qi`, `%1$@`

**Frameworks**: iOS `.strings`, iOS `.stringsdict`, Objective-C `NSString`.

**Regex (pcre2)**:

```
%(?:[0-9]+\$)?[-+0 #]?[0-9]*(?:\.[0-9]+)?(?:@|l[idufxX]|q[idufxX]|[sdifouxXeEgGcp])
```

**Description**: Apple's printf extension. `%@` is `NSObject` via `description`. `%li` / `%lu` / `%qi` are width-qualified integers. Positional form `%1$@` is supported in `.strings` files.

**Nesting**: No.

**Substitution**: Replace each match with `[[Pn]]`.

## Python str.format

**Example**: `{0}`, `{name}`, `{user[id]}`, `{value:.2f}`, `{:>10}`

**Frameworks**: Python `str.format`, f-strings (compile-time, but the placeholder form is identical).

**Regex (pcre2)**:

```
\{[A-Za-z0-9_.\[\]]*(?::[^{}]*)?\}
```

**Description**: Python format-spec brace placeholder. Supports positional (`{0}`), named (`{name}`), attribute access (`{user.name}`), index access (`{user[id]}`), and format spec after `:`. Empty `{}` is legal in `str.format` for positional auto-indexing.

**Nesting**: No translatable text, but the format spec after `:` is machine-readable — never modify.

**Substitution**: Replace each match with `[[Pn]]`. This regex overlaps the **ICU single brace** regex — use one or the other depending on the file's detected format family, not both.

## Ruby / Rails

**Example**: `%{name}`, `%{count}`, `%{user_id}`

**Frameworks**: Ruby `String#%` with named substitutions, Rails i18n (`I18n.t`), Jekyll / Liquid variants.

**Regex (pcre2)**:

```
%\{[A-Za-z_][A-Za-z0-9_]*\}
```

**Description**: Ruby named-substitution form. The `%{...}` literal is distinct from Python `%(...)s` — note the curly braces and the lack of trailing type code.

**Nesting**: No.

**Substitution**: Replace with `[[Pn]]`.

## Python %-format (named)

**Example**: `%(name)s`, `%(count)d`, `%(user_id)05d`

**Frameworks**: Python `%` operator with dict, logging format strings.

**Regex (pcre2)**:

```
%\([A-Za-z_][A-Za-z0-9_]*\)[-+0 #]?[0-9]*(?:\.[0-9]+)?[sdifouxXeEgGcr%]
```

**Description**: Python dict-style `%`-format. Parentheses wrap the key, followed by an optional flag/width/precision and a type code. Looks similar to Ruby `%{name}` at a glance but structurally different — regex classes must not be shared.

**Nesting**: No.

**Substitution**: Replace with `[[Pn]]`.

## Symfony

**Example**: `%name%`, `%count%`, `%user_id%`

**Frameworks**: Symfony `Translator`, PHP `strtr` convention.

**Regex (pcre2)**:

```
%[A-Za-z_][A-Za-z0-9_]*%
```

**Description**: Symfony delimits named placeholders with literal `%` on both sides. A lone `%` is ambiguous with printf — detection should be file-format-driven (check the file is a Symfony translation file before enabling this regex).

**Nesting**: No.

**Substitution**: Replace with `[[Pn]]`.

## .NET composite format

**Example**: `{0}`, `{1:N2}`, `{0,-10:C}`, `{2:yyyy-MM-dd}`

**Frameworks**: .NET `string.Format`, `StringBuilder.AppendFormat`, C# interpolated strings (compile-time; same placeholder shape).

**Regex (pcre2)**:

```
\{[0-9]+(?:,-?[0-9]+)?(?::[^{}]*)?\}
```

**Description**: Zero-indexed positional placeholder with optional alignment (`,-10`) and optional format spec (`:N2`, `:C`, `:yyyy-MM-dd`). Overlaps with **Python str.format** and **ICU single brace** — select based on source format family.

**Nesting**: No translatable text; format spec is machine-readable.

**Substitution**: Replace with `[[Pn]]`.

## Combined ripgrep recipe

One-shot pattern that enumerates every placeholder covered by this catalog. PCRE2 is required for the ICU plural/select alternatives — invoke ripgrep with `-P`.

```
rg -P -o '\{\{-?\s*[A-Za-z0-9_.]+\s*\}\}|\{[A-Za-z0-9_]+,\s*plural,\s*(?:(?:=\d+|zero|one|two|few|many|other)\s*\{[^{}]*\}\s*)+\}|\{[A-Za-z0-9_]+,\s*select,\s*(?:[A-Za-z0-9_]+\s*\{[^{}]*\}\s*)+\}|\{[A-Za-z0-9_]+,\s*(?:number|date|time|duration|spellout|ordinal),\s*::[^{}]*\}|@(?:\.[a-z]+)?:[A-Za-z0-9_.]+|\$t\([A-Za-z0-9_.:-]+\)|<\d+>[^<]*</\d+>|<[A-Za-z][A-Za-z0-9]*>[^<]*</[A-Za-z][A-Za-z0-9]*>|%[0-9]+\$[-+0 #]?[0-9]*(?:\.[0-9]+)?[sdifouxXeEgGcp]|%\([A-Za-z_][A-Za-z0-9_]*\)[-+0 #]?[0-9]*(?:\.[0-9]+)?[sdifouxXeEgGcr%]|%\{[A-Za-z_][A-Za-z0-9_]*\}|%[A-Za-z_][A-Za-z0-9_]*%|%(?:[0-9]+\$)?[-+0 #]?[0-9]*(?:\.[0-9]+)?(?:@|l[idufxX]|q[idufxX]|[sdifouxXeEgGcp])|\{[A-Za-z0-9_.\[\]]*(?::[^{}]*)?\}' <src>
```

Pipe through `sort -u` to get the unique set. Patterns that **require PCRE2 (`-P`)**: ICU plural, ICU select (both use non-capturing groups with quantifiers that the default Rust regex engine does not support in this combined form). The simpler patterns work with the default engine, but run the whole combined regex under `-P` for a single pass.

Alternation order matters. ICU plural / select / skeleton are listed before ICU single brace so the longer structural match wins. react-i18next numbered tags are listed before named tags to avoid the named pattern swallowing numeric-looking inner text edge cases.

## Substitution strategy

1. **Enumerate**. Run the combined recipe with `rg -P -o ... <src>` piped to `sort -u`. Store the ordered unique list as `matches[]`.
1. **Tokenize**. Build a substitution map `{ "[[P0]]": matches[0], "[[P1]]": matches[1], ... }`. Token index is stable within this translation unit.
1. **Substitute**. Replace each occurrence of `matches[i]` in the source text with `[[Pi]]`. Do a longest-first pass — if a shorter match is a substring of a longer one, the longer one must be replaced first.
1. **Translate**. Send the substituted text to the translation model with an explicit instruction: "Preserve every `[[Pn]]` token byte-identical. Do not translate them. Do not reorder unless grammatically required."
1. **Verify**. Count tokens in the translated text. Every `[[P0]]...[[Pn]]` from the map must appear exactly once. A missing token is a hard failure — retry with a stronger prompt or flag `DONE_WITH_CONCERNS`.
1. **Restore**. Replace each `[[Pn]]` in the translation with `matches[n]`. The restored text is the final output.

**Rationale**: LLMs routinely corrupt `{var}` → `{переменная}`, `%1$s` → `%1 $s`, and collapse `<0>text</0><1>other</1>` into one tag. They rarely touch opaque `[[P0]]`-shaped tokens. Substitution converts preservation from a prompt-obedience gamble into a mechanical invariant.

## Nested-placeholder handling

ICU plural and select blocks are the one class of placeholder where the body text inside `{...}` is itself translatable. A naive regex substitution will either (a) extract the whole block as opaque and lose the inner prose entirely, or (b) try to translate the block and corrupt the ICU structure.

**Strategy**:

1. Extract each plural/select block as a single `[[Pn]]` token — preserve the outer structure for the combined regex pass.
1. Separately, decompose the block into its branches: `{count, plural, one {X} other {Y}}` yields branches `{ one: "X", other: "Y" }`.
1. Translate each branch body independently, requesting target-language plural forms where applicable. **Target-language plural rules differ**:
   - Russian: 4 forms (`one`, `few`, `many`, `other`).
   - Arabic: 6 forms (`zero`, `one`, `two`, `few`, `many`, `other`).
   - Japanese, Chinese, Korean, Vietnamese: 1 form (`other`) — no grammatical plural.
   - English, German, Spanish, French: 2 forms (`one`, `other`).
1. Reassemble: `{count, plural, <forms>}` with the translated bodies, keeping the selector variable name (`count`) and the keyword (`plural`) identical.
1. Restore the assembled block in place of `[[Pn]]` in the final output.

Do NOT pass ICU plural/select blocks through the flat substitution + translate + restore loop. The inner bodies will never be translated, or worse, the outer structure will be mangled. These blocks need structural handling.

## Known gotchas

1. **ICU plural nesting cannot be flattened with a single regex.** Plural and select bodies are translatable prose that may contain further placeholders (`{count, plural, one {one {item}} other {# {item}s}}`). A single substitution pass will either lose the inner text or corrupt the outer frame. Handle structurally, not textually.
1. **react-i18next numbered tags are position-based in JSX.** `<0>`, `<1>`, `<2>` refer to the i-th child element of the source Trans component — renumbering or reordering changes which component wraps which word. Preserve tag numbers and their relative order; only the surrounding prose may move.
1. **vue-i18n `@:key` references are lookups, not text.** The key path (`common.ok`, `buttons.save`) resolves at runtime to another translation entry. Never translate, never rewrite, never change case.
1. **Python `%(name)s` and Ruby `%{name}` look similar but have different regex classes.** Python wraps the key in parentheses and requires a trailing type code (`s`, `d`). Ruby wraps the key in curly braces and has no trailing type code. Do not unify these under one regex — they are distinct pattern families.
1. **Multi-byte UTF-8: `rg -o` counts characters, not bytes.** MyMemory's 500-byte per-request cap is counted in bytes. Cyrillic (2 bytes/char) hits the cap at ~250 visible characters; CJK (3 bytes/char) hits it at ~166. When chunking a substituted string for MT calls, measure the byte length of the UTF-8 encoding, not the character length.
1. **Symfony `%name%` is ambiguous with printf.** A lone `%` followed by letters is both a valid Symfony placeholder and a plausible printf conversion. Enable the Symfony regex only when the source file is detected as a Symfony translation file (YAML/XLIFF with Symfony domain conventions).
1. **Python str.format, ICU single brace, and .NET composite format all use `{...}`.** The three overlap heavily. Select one regex based on the file's detected format family rather than running all three in parallel.

## Grep access hints

Agents should grep this file for specific patterns they need. Examples:

```
rg -A 20 '## ICU plural block' references/placeholder-patterns.md
rg -A 10 '## printf positional' references/placeholder-patterns.md
rg -A 30 '## Combined ripgrep recipe' references/placeholder-patterns.md
```

Never cat or Read the whole file into context — it defeats the purpose of progressive disclosure under SKILL_GUIDELINES.md.
