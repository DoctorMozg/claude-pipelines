#!/bin/sh
# Appends a gate artifact under its journal bullet: <private> spans, line-crossing ones included,
# become [redacted], and each non-empty line is indented two spaces. Skills grant this path alone.
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: journal-artifact.sh <artifact file> <journal file>, got $# argument(s)" >&2
  exit 2
fi
if [ ! -r "$1" ] || [ -d "$1" ]; then
  echo "journal-artifact.sh: can't read artifact file '$1'" >&2
  exit 2
fi
if [ ! -d "$(dirname -- "$2")" ]; then
  echo "journal-artifact.sh: journal folder for '$2' doesn't exist; run mkdir -p first" >&2
  exit 2
fi

perl -0777 -pe 's|<private>.*?</private>|[redacted]|gs; s/^(?=.)/  /gm' -- "$1" >>"$2"
printf '\n' >>"$2"
