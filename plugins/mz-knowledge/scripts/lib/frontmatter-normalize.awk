# Normalizes one vault note's frontmatter; the inputs are the vault schema (or /dev/null), then the note.
# Exit 0 prints the closing line number, the change list and the new frontmatter; 1 = already clean; 2 prints why not.

function trim(s) {
  sub(/^[ \t]+/, "", s)
  sub(/[ \t]+$/, "", s)
  return s
}

function is_quoted(s,    q) {
  q = substr(s, 1, 1)
  return length(s) >= 2 && (q == "\"" || q == "'") && substr(s, length(s)) == q
}

function unquote(s,    inner) {
  s = trim(s)
  if (!is_quoted(s)) return s
  inner = substr(s, 2, length(s) - 2)
  if (substr(s, 1, 1) == "'") gsub(/''/, "'", inner)
  return inner
}

# A value the hook may rewrite: no comment, nesting, anchor, tag or escape that it would have to understand.
function supported(raw,    c, inner) {
  raw = trim(raw)
  if (is_quoted(raw)) {
    inner = substr(raw, 2, length(raw) - 2)
    if (substr(raw, 1, 1) == "'") {
      gsub(/''/, "", inner)
      return index(inner, "'") == 0
    }
    return index(inner, "\"") == 0 && index(inner, "\\") == 0
  }
  c = substr(raw, 1, 1)
  if (c != "" && index("#&*!|>%@`[]{}\"'?", c) > 0) return 0
  return raw !~ /^-( |$)/ && index(raw, " #") == 0 && index(raw, ": ") == 0 && raw !~ /:$/
}

function is_key_line(line,    c) {
  c = substr(line, 1, 1)
  if (c == "" || index(" #-[]{}?&*!|>%@`,<\"'", c) > 0) return 0
  return line ~ /^[^:]+:( |$)/
}

function key_of(line) {
  sub(/:([ \t].*)?$/, "", line)
  return unquote(line)
}

function value_of(line) {
  if (!sub(/^[^:]*:[ \t]?/, "", line)) return ""
  return line
}

function is_value_line(line) {
  return line ~ /^ / || line ~ /^-( |$)/
}

# Splits a flow list body ("a, 'b, c', d") on commas outside quotes into trimmed raw tokens[1..n]; returns n.
function split_flow(body, tokens,    i, c, quote, current, n) {
  n = 0
  current = ""
  quote = ""
  for (i = 1; i <= length(body); i++) {
    c = substr(body, i, 1)
    if (quote != "") {
      if (c == quote) quote = ""
    } else if (c == "\"" || c == "'") {
      quote = c
    } else if (c == ",") {
      tokens[++n] = trim(current)
      current = ""
      continue
    }
    current = current c
  }
  if (trim(current) != "" || n > 0) tokens[++n] = trim(current)
  return n
}

function schema_append(type, field, item,    known) {
  item = unquote(item)
  if (item == "") return
  # mawk creates the element on the left of `=` before the right side runs, so the lookup goes first.
  known = (type SUBSEP field) in schema
  schema[type SUBSEP field] = known ? schema[type SUBSEP field] "\n" item : item
}

function bail(why) {
  reason = why
  if (in_end) {
    print reason
    exit 2
  }
  exit
}

# Reads entry e into parsed[1..parsed_n] and sets parsed_kind to list, scalar or empty; 0 when unsupported.
function parse_entry(e,    v, i, line, tokens, n, indent) {
  parsed_n = 0
  v = trim(entry_value[e])
  if (entry_last[e] > entry_first[e]) {
    if (v != "") return 0
    indent = -1
    for (i = entry_first[e] + 1; i <= entry_last[e]; i++) {
      line = fm[i]
      if (line ~ /^ *$/) continue
      if (line !~ /^ *-( |$)/) return 0
      match(line, /^ */)
      if (indent < 0) indent = RLENGTH
      if (RLENGTH != indent) return 0
      sub(/^ *- */, "", line)
      if (!supported(line)) return 0
      parsed[++parsed_n] = unquote(line)
    }
    parsed_kind = "list"
    return 1
  }
  if (v == "" || v == "~" || v == "null") {
    parsed_kind = "empty"
    return 1
  }
  if (v ~ /^\[.*\]$/) {
    n = split_flow(substr(v, 2, length(v) - 2), tokens)
    for (i = 1; i <= n; i++) {
      if (!supported(tokens[i])) return 0
      parsed[++parsed_n] = unquote(tokens[i])
    }
    parsed_kind = "list"
    return 1
  }
  if (!supported(v)) return 0
  parsed[++parsed_n] = unquote(v)
  parsed_kind = "scalar"
  return 1
}

# Splits one scalar into words[1..n] by the list key's rules; aliases such as "Smith, John" are never split.
function split_scalar(s, list_key, words,    n, i, all_hashed) {
  if (list_key == "aliases") {
    words[1] = s
    return 1
  }
  if (index(s, ",") > 0) return split(s, words, /,/)
  n = split(s, words, / +/)
  if (list_key == "cssclasses") return n
  # "#a #b" is two tags, while "AI Ethics" is one tag with a space that becomes "AI-Ethics".
  all_hashed = n >= 2
  for (i = 1; i <= n; i++) if (substr(words[i], 1, 1) != "#") all_hashed = 0
  if (all_hashed) return n
  words[1] = s
  return 1
}

function clean_item(list_key, item) {
  item = trim(item)
  if (list_key == "tags") {
    sub(/^#+/, "", item)
    item = trim(item)
    gsub(/ +/, "-", item)
    if (conventions["tag_case"] == "lower") item = tolower(item)
  }
  return item
}

function yaml_scalar(s,    first, lower) {
  first = substr(s, 1, 1)
  lower = tolower(s)
  if (index("-?:,[]{}#&*!|>'\"%@` ", first) == 0 && index(s, ": ") == 0 && index(s, " #") == 0 \
      && s !~ /[: ]$/ && s !~ /^[-+.]?[0-9][0-9a-fA-FxXoO._:+-]*$/ \
      && lower !~ /^(true|false|yes|no|y|n|on|off|null|~|\.inf|\.nan)$/)
    return s
  if (index(s, "\\") == 0 && index(s, "\"") == 0) return "\"" s "\""
  gsub(/'/, "''", s)
  return "'" s "'"
}

function entry_text(e,    i, text) {
  text = fm[entry_first[e]]
  for (i = entry_first[e] + 1; i <= entry_last[e]; i++) text = text "\n" fm[i]
  return text
}

function note_change(what) {
  changes = changes == "" ? what : changes ", " what
}

# Merges the singular and plural Obsidian keys into one cleaned block list on the plural key.
function normalize_list(singular, plural,    es, ep, e, j, i, k, n, wn, items, seen, words, item, same, text) {
  es = (singular in key_index) ? key_index[singular] : 0
  ep = (plural in key_index) ? key_index[plural] : 0
  if (!es && !ep) return
  n = 0
  same = 0
  for (j = 1; j <= 2; j++) {
    e = j == 1 ? ep : es
    if (!e) continue
    if (!parse_entry(e)) bail("unsupported " entry_key[e] " value")
    for (i = 1; i <= parsed_n; i++) {
      if (parsed_kind == "scalar") {
        wn = split_scalar(parsed[i], plural, words)
      } else {
        words[1] = parsed[i]
        wn = 1
      }
      for (k = 1; k <= wn; k++) {
        item = clean_item(plural, words[k])
        if (item == "" || item in seen) continue
        seen[item] = 1
        items[++n] = item
      }
    }
    if (e == ep && !es) {
      same = parsed_kind == "empty" || (parsed_kind == "list" && parsed_n == n)
      for (i = 1; same && i <= parsed_n; i++) if (parsed[i] != items[i]) same = 0
    }
  }
  if (same) return
  text = plural ":"
  if (n == 0) text = text " []"
  for (i = 1; i <= n; i++) text = text "\n  - " yaml_scalar(items[i])
  e = ep ? ep : es
  out_text[e] = text
  entry_key[e] = plural
  if (es && ep) {
    dropped[es] = 1
    note_change(singular " merged into " plural)
  } else if (es) {
    note_change(singular " -> " plural " list")
  } else {
    note_change(plural " cleaned")
  }
}

function normalize_created(    e, v) {
  if (!("created" in key_index)) {
    added_text[++added_n] = "created: " today
    added_key[added_n] = "created"
    note_change("added created")
    return
  }
  e = key_index["created"]
  if (entry_last[e] > entry_first[e]) return
  v = unquote(entry_value[e])
  if (v ~ /^[0-9][0-9][0-9][0-9][\/.][0-9][0-9][\/.][0-9][0-9]$/) {
    gsub(/[\/.]/, "-", v)
    out_text[e] = "created: " v
    note_change("created -> " v)
  }
}

function present(k,    i) {
  for (i = 1; i <= entry_n; i++) if (!dropped[i] && entry_key[i] == k) return 1
  for (i = 1; i <= added_n; i++) if (added_key[i] == k) return 1
  return 0
}

function add_schema_stubs(type,    fields, n, i, k) {
  if (!((type SUBSEP "required") in schema)) return
  n = split(schema[type SUBSEP "required"], fields, /\n/)
  for (i = 1; i <= n; i++) {
    k = fields[i]
    if (present(k)) continue
    added_text[++added_n] = (k == "tags" || k == "aliases" || k == "cssclasses") ? k ": []" : k ":"
    added_key[added_n] = k
    note_change("added " k)
  }
}

FILENAME == schema_file {
  line = $0
  sub(/\r$/, "", line)
  if (line ~ /^[ \t]*(#.*)?$/) next
  match(line, /^ */)
  indent = RLENGTH
  body = substr(line, indent + 1)
  if (indent == 0) {
    section = key_of(body)
    type_indent = field_indent = 0
    next
  }
  v = trim(value_of(body))
  sub(/[ \t]+#.*$/, "", v)
  if (section == "conventions") {
    conventions[key_of(body)] = unquote(v)
  } else if (section == "note_types") {
    if (field_indent && indent >= field_indent && body ~ /^-( |$)/) {
      if (schema_field == "required" || schema_field == "optional") schema_append(schema_type, schema_field, substr(body, 3))
    } else if (!type_indent || indent == type_indent) {
      type_indent = indent
      schema_type = key_of(body)
      schema_field = ""
    } else if (indent > type_indent && (!field_indent || indent == field_indent)) {
      field_indent = indent
      schema_field = key_of(body)
      if ((schema_field == "required" || schema_field == "optional") && v ~ /^\[.*\]$/) {
        n = split_flow(substr(v, 2, length(v) - 2), tokens)
        for (i = 1; i <= n; i++) schema_append(schema_type, schema_field, tokens[i])
      }
    }
  }
  next
}

{
  if (FNR == 1) {
    if ($0 == "---\r") bail("CRLF line endings")
    if ($0 != "---") bail("no frontmatter block")
    opened = 1
    next
  }
  if (FNR > max_lines) bail("no closing --- within " max_lines " lines")
  if ($0 == "---") {
    closing_line = FNR
    exit
  }
  if (index($0, "\r")) bail("CRLF line endings")
  if (index($0, "\t")) bail("tab in frontmatter")
  # A template's placeholders resolve when a note is made from it, so a date filled now would be baked in.
  if (index($0, "{{") || index($0, "<%")) bail("template placeholders")
  fm[++fm_n] = $0
}

END {
  in_end = 1
  if (reason == "" && !closing_line) reason = opened ? "frontmatter never closes" : "no frontmatter block"
  if (reason != "") {
    print reason
    exit 2
  }

  for (i = 1; i <= fm_n; i++) {
    line = fm[i]
    if (line ~ /^ *$/) {
      for (j = i + 1; j <= fm_n && fm[j] ~ /^ *$/; j++) continue
      if (entry_n && entry_key[entry_n] != "" && j <= fm_n && is_value_line(fm[j])) {
        entry_last[entry_n] = i
      } else {
        # A blank line between keys stays in place, and keys are never reordered across it.
        entry_n++
        entry_key[entry_n] = ""
        entry_first[entry_n] = entry_last[entry_n] = i
        has_loose_lines = 1
      }
    } else if (line ~ /^ *#/) {
      bail("comment in frontmatter")
    } else if (is_key_line(line)) {
      entry_n++
      entry_key[entry_n] = key_of(line)
      entry_value[entry_n] = value_of(line)
      entry_first[entry_n] = entry_last[entry_n] = i
      if (entry_key[entry_n] in key_index) bail("duplicate key " entry_key[entry_n])
      key_index[entry_key[entry_n]] = entry_n
    } else if (is_value_line(line)) {
      if (!entry_n || entry_key[entry_n] == "") bail("value line outside any key")
      entry_last[entry_n] = i
    } else {
      bail("unsupported line: " line)
    }
  }

  normalize_list("tag", "tags")
  normalize_list("alias", "aliases")
  normalize_list("cssclass", "cssclasses")
  normalize_created()

  type = ""
  if ("type" in key_index && entry_last[key_index["type"]] == entry_first[key_index["type"]]) {
    type = unquote(entry_value[key_index["type"]])
    add_schema_stubs(type)
  }

  order_n = 0
  if (conventions["key_order"] == "schema" && type != "" && !has_loose_lines && (type SUBSEP "required") in schema) {
    wanted = schema[type SUBSEP "required"]
    if ((type SUBSEP "optional") in schema) wanted = wanted "\n" schema[type SUBSEP "optional"]
    wn = split(wanted, wanted_keys, /\n/)
    for (w = 1; w <= wn; w++) {
      for (i = 1; i <= entry_n; i++)
        if (!dropped[i] && !placed_entry[i] && entry_key[i] == wanted_keys[w]) {
          order[++order_n] = "e" i
          placed_entry[i] = 1
        }
      for (i = 1; i <= added_n; i++)
        if (!placed_added[i] && added_key[i] == wanted_keys[w]) {
          order[++order_n] = "a" i
          placed_added[i] = 1
        }
    }
  }
  for (i = 1; i <= entry_n; i++) if (!dropped[i] && !placed_entry[i]) order[++order_n] = "e" i
  for (i = 1; i <= added_n; i++) if (!placed_added[i]) order[++order_n] = "a" i

  original = ""
  for (i = 1; i <= fm_n; i++) original = original (i > 1 ? "\n" : "") fm[i]
  result = ""
  last_entry = 0
  reordered = 0
  for (o = 1; o <= order_n; o++) {
    id = substr(order[o], 2) + 0
    if (substr(order[o], 1, 1) == "e") {
      text = (id in out_text) ? out_text[id] : entry_text(id)
      if (id < last_entry) reordered = 1
      last_entry = id
    } else {
      text = added_text[id]
    }
    result = result (o > 1 ? "\n" : "") text
  }
  if (reordered) note_change("reordered keys to the schema")
  if (result == original) exit 1
  print closing_line
  print changes
  print result
  exit 0
}
