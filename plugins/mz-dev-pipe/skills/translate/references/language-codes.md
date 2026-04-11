# Language Codes — Canonicalization, Detection, Validation

Grep-first reference. Agents never load this file whole. The pipeline's internal canonical form for every language code is **ISO 639-1 two-letter lowercase** (`en`, `ru`, `ja`, `zh`, `fr`, `de`, ...). All three external services the translate skill can reach — MyMemory, LibreTranslate, Wiktionary — accept ISO 639-1 directly without transformation, so canonicalizing at the skill boundary removes every downstream code-shape branch. Use this file to (1) normalize user input into the canonical form, (2) recognize preservable regional variants, (3) run the script-based detection fallback when network detection fails, and (4) validate incoming language tokens against prompt-injection.

## Canonical Form

The canonical set is the ISO 639-1 two-letter lowercase codes listed below. Any value outside this set must be rejected with `unsupported target language: <input>. Canonical form is ISO 639-1 lowercase. See references/language-codes.md for supported values.`

```
en  ru  ja  zh  fr  de  es  it  pt  ar  ko  nl  pl  tr  vi
th  hi  he  uk  cs  sv  no  da  fi  el  hu  ro  id  ms  bg
hr  sk  sl  sr  lt  lv  et  fa  ur  bn  ta  te  ml  kn  mr
gu  pa  am  sw  zu
```

Rationale: MyMemory (`langpair=en|ru`), LibreTranslate (`source`/`target`), and Wiktionary (language section headers via the MediaWiki API) all expect the ISO 639-1 two-letter code. Canonicalizing once removes branching from every caller.

## Normalization Table

Grep for the specific input form the user supplied. Matching is case-insensitive — lowercase the input before grepping. The `Notes` column records lossy collapses and edge cases.

| Input form                                                                       | Canonical | Notes                                                                            |
| -------------------------------------------------------------------------------- | --------- | -------------------------------------------------------------------------------- |
| `english`, `English`, `ENGLISH`, `en-US`, `en-GB`, `en_US`, `eng`                | `en`      | Multiple variants collapse to `en`; `eng` is ISO 639-2/T                         |
| `russian`, `Russian`, `RUSSIAN`, `ru-RU`, `ru_RU`, `rus`                         | `ru`      | Human name, case-insensitive; `rus` is ISO 639-2/T                               |
| `chinese`, `Chinese`, `zh-CN`, `zh-Hans`, `zh-Hant`, `zh-TW`, `cn`, `zho`, `chi` | `zh`      | Simplified vs Traditional distinction lost; preserve via `target_variant`        |
| `portuguese`, `Portuguese`, `pt-BR`, `pt-PT`, `por`                              | `pt`      | Brazilian vs European Portuguese distinction lost; preserve via `target_variant` |
| `japanese`, `Japanese`, `ja-JP`, `jpn`, `jp`                                     | `ja`      |                                                                                  |
| `spanish`, `Spanish`, `es-ES`, `es-MX`, `es-AR`, `spa`                           | `es`      | Regional variants collapse                                                       |
| `french`, `French`, `fr-FR`, `fr-CA`, `fra`, `fre`                               | `fr`      | Canadian French collapses; preserve via `target_variant` if meaningful           |
| `german`, `German`, `de-DE`, `de-AT`, `de-CH`, `ger`, `deu`                      | `de`      | Swiss/Austrian variants collapse                                                 |
| `italian`, `Italian`, `it-IT`, `ita`                                             | `it`      |                                                                                  |
| `korean`, `Korean`, `ko-KR`, `kor`                                               | `ko`      |                                                                                  |
| `arabic`, `Arabic`, `ar-SA`, `ar-EG`, `ara`                                      | `ar`      | Modern Standard Arabic assumed; regional varieties collapse                      |
| `dutch`, `Dutch`, `nl-NL`, `nl-BE`, `nld`, `dut`                                 | `nl`      | Flemish collapses to `nl`                                                        |
| `polish`, `Polish`, `pl-PL`, `pol`                                               | `pl`      |                                                                                  |
| `turkish`, `Turkish`, `tr-TR`, `tur`                                             | `tr`      |                                                                                  |
| `vietnamese`, `Vietnamese`, `vi-VN`, `vie`                                       | `vi`      |                                                                                  |
| `thai`, `Thai`, `th-TH`, `tha`                                                   | `th`      |                                                                                  |
| `hindi`, `Hindi`, `hi-IN`, `hin`                                                 | `hi`      |                                                                                  |
| `hebrew`, `Hebrew`, `he-IL`, `iw`, `heb`                                         | `he`      | `iw` is legacy (pre-1989 ISO); prefer `he`                                       |
| `ukrainian`, `Ukrainian`, `uk-UA`, `ukr`                                         | `uk`      |                                                                                  |
| `czech`, `Czech`, `cs-CZ`, `ces`, `cze`                                          | `cs`      |                                                                                  |
| `swedish`, `Swedish`, `sv-SE`, `swe`                                             | `sv`      |                                                                                  |
| `norwegian`, `Norwegian`, `nb`, `nn`, `nb-NO`, `nn-NO`, `nor`                    | `no`      | Bokmål (`nb`) and Nynorsk (`nn`) both collapse to `no`                           |
| `danish`, `Danish`, `da-DK`, `dan`                                               | `da`      |                                                                                  |
| `finnish`, `Finnish`, `fi-FI`, `fin`                                             | `fi`      |                                                                                  |
| `greek`, `Greek`, `el-GR`, `ell`, `gre`                                          | `el`      |                                                                                  |
| `hungarian`, `Hungarian`, `hu-HU`, `hun`                                         | `hu`      |                                                                                  |
| `romanian`, `Romanian`, `ro-RO`, `ron`, `rum`                                    | `ro`      |                                                                                  |
| `indonesian`, `Indonesian`, `id-ID`, `ind`                                       | `id`      | Legacy `in` also maps to `id`                                                    |
| `malay`, `Malay`, `ms-MY`, `msa`, `may`                                          | `ms`      |                                                                                  |
| `bulgarian`, `Bulgarian`, `bg-BG`, `bul`                                         | `bg`      |                                                                                  |
| `serbian`, `Serbian`, `sr-RS`, `sr-Cyrl`, `sr-Latn`, `srp`                       | `sr`      | Cyrillic vs Latin script distinction lost; preserve via `target_variant`         |
| `persian`, `Persian`, `farsi`, `Farsi`, `fa-IR`, `per`, `fas`                    | `fa`      |                                                                                  |
| `bengali`, `Bengali`, `bn-BD`, `bn-IN`, `ben`                                    | `bn`      |                                                                                  |
| `tamil`, `Tamil`, `ta-IN`, `tam`                                                 | `ta`      |                                                                                  |
| `telugu`, `Telugu`, `te-IN`, `tel`                                               | `te`      |                                                                                  |

Add new rows only after verifying the variant is in active use. Do not add rows for dead or synthetic codes.

### Native-Name Reference

A secondary lookup for display in approval-gate plans. Agents grep this table when rendering the target language to the user in the plan artifact. This table is not used for canonicalization — it is display-only.

| Canonical | English name | Native name |
| --------- | ------------ | ----------- |
| `en`      | English      | English     |
| `ru`      | Russian      | Русский     |
| `zh`      | Chinese      | 中文        |
| `ja`      | Japanese     | 日本語      |
| `ko`      | Korean       | 한국어      |
| `ar`      | Arabic       | العربية     |
| `fa`      | Persian      | فارسی       |
| `he`      | Hebrew       | עברית       |
| `hi`      | Hindi        | हिन्दी        |
| `bn`      | Bengali      | বাংলা        |
| `ta`      | Tamil        | தமிழ்        |
| `th`      | Thai         | ไทย         |
| `vi`      | Vietnamese   | Tiếng Việt  |
| `el`      | Greek        | Ελληνικά    |
| `uk`      | Ukrainian    | Українська  |
| `es`      | Spanish      | Español     |
| `fr`      | French       | Français    |
| `de`      | German       | Deutsch     |
| `pt`      | Portuguese   | Português   |
| `it`      | Italian      | Italiano    |
| `nl`      | Dutch        | Nederlands  |
| `pl`      | Polish       | Polski      |
| `tr`      | Turkish      | Türkçe      |

## Regional Variant Collapse — Explicit Losses

When the canonicalization above collapses multiple variants into one ISO 639-1 code, the following distinctions are lost and cannot be recovered from the canonical form alone. When the user supplies the more specific tag, preserve it separately in a `target_variant` field on the translation unit and pass it to the `pipeline-translator` agent as a hint (not as the canonical target).

- `zh-Hans` (Simplified Chinese) vs `zh-Hant` (Traditional Chinese) — both become `zh`. The target script is lost. Mitigation: preserve `zh-Hans` / `zh-Hant` / `zh-TW` / `zh-HK` in `target_variant` and tell the translator to render Simplified or Traditional characters accordingly.
- `pt-BR` (Brazilian) vs `pt-PT` (European) — both become `pt`. Regional vocabulary, spelling reforms, and verb forms diverge. Mitigation: preserve in `target_variant`.
- `en-US` vs `en-GB` (and `en-AU`, `en-CA`, `en-IN`) — both become `en`. Spelling (`color` / `colour`), vocabulary (`elevator` / `lift`), and punctuation conventions diverge. Mitigation: preserve in `target_variant`.
- `nb` (Bokmål) vs `nn` (Nynorsk) — both become `no`. These are the two official written standards of Norwegian and are not interchangeable. Mitigation: preserve in `target_variant`; if neither is specified, default the translator to Bokmål (the majority written form) and note the assumption.
- `sr-Cyrl` vs `sr-Latn` — both become `sr`. Cyrillic and Latin scripts for Serbian are co-official; choosing one is a substantive decision. Mitigation: preserve in `target_variant`.
- Arabic regional varieties (`ar-EG`, `ar-SA`, `ar-MA`, etc.) — all become `ar`. Modern Standard Arabic is assumed for output. Mitigation: preserve in `target_variant` only when the user has explicitly asked for a dialect; dialect translation quality from free backends is poor and should be flagged.
- `fr-CA` (Canadian French) vs `fr-FR` (European French) — both become `fr`. Vocabulary and idiom diverge. Mitigation: preserve in `target_variant`.
- `de-CH` (Swiss Standard German) vs `de-DE` — both become `de`. Swiss orthography drops `ß`. Mitigation: preserve in `target_variant`.

## Script → Language Fallback Heuristic

When every network-based detection path fails, fall back to a pure-string Unicode-range scan of the first ~500 characters. Count code points per range and pick the range with the highest count. Below each range is the most likely language and a list of alternatives that share the same script — the heuristic cannot disambiguate among them on script alone.

| Unicode range                     | Script                             | Likely language (majority) | Alternatives (same script)                     |
| --------------------------------- | ---------------------------------- | -------------------------- | ---------------------------------------------- |
| `0x0400–0x04FF`                   | Cyrillic                           | `ru`                       | `uk`, `bg`, `sr`, `mk`, `be`                   |
| `0x0600–0x06FF`                   | Arabic                             | `ar`                       | `fa`, `ur`, `ps`, `ku`                         |
| `0x4E00–0x9FFF`                   | CJK Unified Ideographs             | `zh`                       | `ja` (when mixed with kana)                    |
| `0x3040–0x309F`                   | Hiragana                           | `ja`                       | —                                              |
| `0x30A0–0x30FF`                   | Katakana                           | `ja`                       | —                                              |
| `0xAC00–0xD7A3`                   | Hangul Syllables                   | `ko`                       | —                                              |
| `0x0370–0x03FF`                   | Greek and Coptic                   | `el`                       | —                                              |
| `0x0590–0x05FF`                   | Hebrew                             | `he`                       | `yi`                                           |
| `0x0900–0x097F`                   | Devanagari                         | `hi`                       | `mr`, `ne`, `sa`                               |
| `0x0980–0x09FF`                   | Bengali                            | `bn`                       | `as`                                           |
| `0x0A00–0x0A7F`                   | Gurmukhi                           | `pa`                       | —                                              |
| `0x0A80–0x0AFF`                   | Gujarati                           | `gu`                       | —                                              |
| `0x0B00–0x0B7F`                   | Oriya                              | `or`                       | —                                              |
| `0x0B80–0x0BFF`                   | Tamil                              | `ta`                       | —                                              |
| `0x0C00–0x0C7F`                   | Telugu                             | `te`                       | —                                              |
| `0x0C80–0x0CFF`                   | Kannada                            | `kn`                       | —                                              |
| `0x0D00–0x0D7F`                   | Malayalam                          | `ml`                       | —                                              |
| `0x0D80–0x0DFF`                   | Sinhala                            | `si`                       | —                                              |
| `0x0E00–0x0E7F`                   | Thai                               | `th`                       | —                                              |
| `0x0E80–0x0EFF`                   | Lao                                | `lo`                       | —                                              |
| `0x1000–0x109F`                   | Myanmar                            | `my`                       | —                                              |
| `0x10A0–0x10FF`                   | Georgian                           | `ka`                       | —                                              |
| `0x0530–0x058F`                   | Armenian                           | `hy`                       | —                                              |
| `0x1200–0x137F`                   | Ethiopic                           | `am`                       | `ti`                                           |
| `0x1780–0x17FF`                   | Khmer                              | `km`                       | —                                              |
| `0x0000–0x007F` + `0x00A0–0x00FF` | Latin (basic + Latin-1 Supplement) | — (ambiguous)              | ~100 languages — script alone cannot determine |

Explicit limits:

- **Latin-script ambiguity**. Latin script overlaps roughly a hundred languages (English, Spanish, French, German, Italian, Portuguese, Polish, Turkish, Vietnamese, Indonesian, Swahili, Zulu, ...). Script counting alone cannot disambiguate; escalate to the LLM heuristic or the user.
- **CJK without kana**. If only Han ideographs are present with no Hiragana or Katakana, default to `zh`. Mixed Han + kana defaults to `ja`. Hangul presence overrides both to `ko`.
- **Cyrillic majority-language default is Russian**. If the sample contains characters outside the Russian alphabet (`ї`, `є`, `і` for Ukrainian; `ў` for Belarusian; `ђ`, `ћ` for Serbian), bias toward the matching minority language.
- **Arabic script default is MSA (`ar`)**. Presence of characters unique to Persian (`پ`, `چ`, `ژ`, `گ`) biases toward `fa`; presence of `ٹ`, `ڈ`, `ڑ` biases toward `ur`.

## Auto-Detection Tier Pipeline

When the user did not specify `--from <lang>` (or the NL equivalent), run detection in the following fallback order. Each tier has a failure mode that falls through to the next.

1. **LibreTranslate `/detect`** — `WebFetch` to a reachable mirror with a 5-second timeout. Body: `{"q": "<first 500 chars of content>"}`. Success criterion: HTTP 200 + `detectedLanguage.confidence >= 0.6`. Mirrors and reliability are documented in research.md. On any network/timeout/low-confidence failure, fall through.
1. **Script-based heuristic** — the Unicode-range table above. Scan the first 500 chars, count code points per range, pick the range with the highest non-Latin count. If the winning range is Latin, fall through — script alone cannot pick a Latin language.
1. **LLM heuristic** — dispatch a one-shot `pipeline-researcher` or `haiku` agent with the first 500 chars and the prompt "What language is this? Reply with a single ISO 639-1 code only." Accept the response if it is in the canonical set above. On ambiguity, fall through.
1. **Abort with AskUserQuestion** — present a clear error: `Could not auto-detect source language. Please specify --from <lang> (ISO 639-1 code) explicitly.` Never guess past this point.

**Minimum input length**: 20 characters. Below 20 characters, skip all four tiers and require the user to specify source language explicitly — short strings carry too little signal for any heuristic to be reliable.

**Sampling window**: detection reads the first 500 characters of the content, not the whole file. Short samples are cheaper, hit fewer false positives from embedded code fences, and fit MyMemory's 500-byte per-request cap when a spot-check is layered on top. Skip the first line if it looks like a shebang or YAML frontmatter delimiter (`---`); both are locale-neutral noise.

**Early stop on high confidence**. If tier 1 returns a confidence ≥ 0.9 and the language is in the canonical set, stop there and skip tiers 2–4. Never waste LLM dispatches on high-confidence detections.

## Validation Rules

Run these checks before accepting any language token from user input or from a parsed NL request. Fail closed: any violation rejects the entire translation plan.

1. **Canonical-set membership**. After normalization, the target language must be a member of the canonical set listed in `## Canonical Form`. On miss, reject with:

   ```
   unsupported target language: <input>. Canonical form is ISO 639-1 lowercase. See references/language-codes.md for supported values.
   ```

1. **Character allow-list — anti prompt-injection**. Before normalization, validate the raw input against the regex `^[A-Za-z0-9_-]+$`. Reject any input containing whitespace, quotes, backticks, newlines, shell metacharacters, or Unicode escapes. A language token is never longer than ~12 characters and never contains prose — treating it strictly defends the orchestrator prompt from injection via a crafted `--to` argument.

1. **Length cap**. Raw input ≤ 32 characters. Anything longer is not a language token; reject without attempting to normalize.

1. **Variant preservation is opt-in**. When the user supplies a BCP 47 tag with a region or script subtag (`zh-Hans`, `pt-BR`, `en-GB`, `sr-Latn`), store the original tag in a `target_variant` field alongside the canonical `target_lang`, and pass the variant to the translator agent as a hint. The canonical `target_lang` is still the two-letter code — `target_variant` never replaces it.

1. **Source and target must differ**. If normalized source equals normalized target, reject with `source and target languages are identical after normalization: <lang>`. This catches mistakes like `translate en to en-US`.

1. **Lowercase before comparison**. All canonical-set membership checks are against lowercase. Normalize case before the check; never rely on the user to supply lowercase.

1. **Strip region subtags during canonicalization, not before validation**. Run the anti-injection allow-list on the raw input first, then strip the region/script subtags, then check canonical-set membership. Reversing that order would let `zh_Hans; rm -rf /` through the first check by stripping `; rm -rf /` as a "subtag".

## Grep Access Examples

Agents read this file via targeted grep, not whole-file load. Typical access patterns:

```bash
# Normalize a user-supplied variant (case-insensitive match).
grep -Fi '"ja-jp"' references/language-codes.md

# Look up the regional-variant mitigation for Chinese.
grep -A 3 '^- `zh-Hans`' references/language-codes.md

# Pull the script-range row for Devanagari.
grep -F '0x0900' references/language-codes.md

# Retrieve the rejection error template.
grep -A 1 'unsupported target language' references/language-codes.md

# Fetch the native name of a canonical code for plan rendering.
grep -F '| `ru`' references/language-codes.md

# Check whether a three-letter code has a canonical mapping.
grep -Fi '`fra`' references/language-codes.md
```

Each grep should return one to five lines. If a grep returns more, the query is too broad; narrow it with a more specific anchor. If a grep returns zero lines for a value the user supplied, the value is unmapped — reject it through the validation rules above rather than silently falling back.
