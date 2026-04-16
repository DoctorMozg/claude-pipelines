# Bases Formula Functions Reference

Grep this file for the function name or category you need — do not load the whole file.

## Date Functions

| Function                      | Returns | Description                      |
| ----------------------------- | ------- | -------------------------------- |
| `date.now()`                  | Date    | Current date and time            |
| `date.today()`                | Date    | Current date (no time component) |
| `date(str)`                   | Date    | Parse string as date             |
| `date.from(year, month, day)` | Date    | Construct date                   |

## Duration Functions

| Function            | Returns  | Description                                                                                                    |
| ------------------- | -------- | -------------------------------------------------------------------------------------------------------------- |
| `dur(amount, unit)` | Duration | Create duration. Units: `y`/`year`, `M`/`month`, `w`/`week`, `d`/`day`, `h`/`hour`, `m`/`minute`, `s`/`second` |

## Duration Properties

Access these on the result of subtracting two dates (e.g., `(date.now() - file.mtime).days`):

`.years`, `.months`, `.weeks`, `.days`, `.hours`, `.minutes`, `.seconds`

## String Functions

| Function                  | Returns | Description                   |
| ------------------------- | ------- | ----------------------------- |
| `lower(str)`              | String  | Lowercase                     |
| `upper(str)`              | String  | Uppercase                     |
| `trim(str)`               | String  | Remove surrounding whitespace |
| `replace(str, from, to)`  | String  | Replace all occurrences       |
| `contains(str, sub)`      | Boolean | Substring check               |
| `startsWith(str, prefix)` | Boolean | Prefix check                  |
| `endsWith(str, suffix)`   | Boolean | Suffix check                  |
| `length(str)`             | Number  | String length                 |
| `slice(str, start, end?)` | String  | Substring                     |
| `split(str, sep)`         | List    | Split to list                 |
| `join(list, sep)`         | String  | Join list to string           |

## Number Functions

| Function              | Returns | Description       |
| --------------------- | ------- | ----------------- |
| `round(n, decimals?)` | Number  | Round to decimals |
| `floor(n)`            | Number  | Floor             |
| `ceil(n)`             | Number  | Ceiling           |
| `abs(n)`              | Number  | Absolute value    |
| `min(a, b)`           | Number  | Minimum           |
| `max(a, b)`           | Number  | Maximum           |

## Boolean / Conditional

| Function               | Returns | Description |
| ---------------------- | ------- | ----------- |
| `if(cond, then, else)` | Any     | Conditional |
| `and(a, b)`            | Boolean | Logical AND |
| `or(a, b)`             | Boolean | Logical OR  |
| `not(a)`               | Boolean | Logical NOT |

## List Functions

| Function           | Returns | Description          |
| ------------------ | ------- | -------------------- |
| `count(list)`      | Number  | Count items          |
| `sum(list)`        | Number  | Sum numbers          |
| `filter(list, fn)` | List    | Filter by predicate  |
| `map(list, fn)`    | List    | Transform items      |
| `flat(list)`       | List    | Flatten nested lists |
| `unique(list)`     | List    | Remove duplicates    |
| `first(list)`      | Any     | First element        |
| `last(list)`       | Any     | Last element         |

## File Functions (filter context)

| Function              | Usage  | Description                    |
| --------------------- | ------ | ------------------------------ |
| `file.hasTag(tag)`    | filter | Notes with this tag            |
| `file.hasLink(note)`  | filter | Notes linking to this note     |
| `file.inFolder(path)` | filter | Notes in this folder           |
| `str.matches(regex)`  | filter | Regex match on any string prop |

## Notes

- Duration arithmetic: `date.now() - file.mtime` returns a `Duration`, not a `Number`.
- Always access `.days` (or `.hours`, `.minutes`, etc.) before using in a numeric context.
- YAML quoting: use single quotes around formula strings that contain double quotes.
