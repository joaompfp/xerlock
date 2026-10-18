#!/usr/bin/env bash
# Fetches the MPXJ test data (https://github.com/joniles/mpxj, junit/data/, LGPL-2.1):
# about 609 .mpp files and 150 MSPDI .xml files saved by real Microsoft Project 98-2019,
# plus a few P6 files. Pinned to one commit so the corpus report is reproducible.
#
#   scripts/fetch_msp_corpus.sh            # -> .corpus/mpxj (gitignored; never commit it)
#   .venv/bin/python scripts/msp_corpus.py .corpus/mpxj
#
# A sparse, depth-1 checkout of the junit/data subtree only (about 180 MB).
set -euo pipefail

MPXJ_COMMIT=71304afc7239cbe59f431faebe7148f4cfa49b85
REPO=https://github.com/joniles/mpxj
DEST="$(cd "$(dirname "$0")/.." && pwd)/.corpus/mpxj"

if [ -f "$DEST/.commit" ] && [ "$(cat "$DEST/.commit")" = "$MPXJ_COMMIT" ]; then
  echo "corpus already at $MPXJ_COMMIT in $DEST"
  exit 0
fi

rm -rf "$DEST"
mkdir -p "$DEST"
git -C "$DEST" init -q
git -C "$DEST" remote add origin "$REPO"
git -C "$DEST" sparse-checkout init --no-cone
printf 'junit/data/\n' > "$DEST/.git/info/sparse-checkout"
git -C "$DEST" fetch -q --depth 1 origin "$MPXJ_COMMIT"
git -C "$DEST" checkout -q FETCH_HEAD
echo "$MPXJ_COMMIT" > "$DEST/.commit"
echo "corpus at $MPXJ_COMMIT: $(find "$DEST/junit/data" -iname '*.mpp' | wc -l) .mpp, $(find "$DEST/junit/data" -iname '*.xml' | wc -l) .xml in $DEST"
