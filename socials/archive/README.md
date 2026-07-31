# Archived socials

Socials retired from the game but kept in source. The loader
(`DLDirectory::nextTypedEntry`) skips subdirectories, so nothing in here is
read at boot -- moving a file back up one level is all it takes to restore it.

## Why these 100

Ranked against 21 months of real player usage (2024-10-27 -> 2026-07-30) from
the command-input log, then filtered:

- **Ranked by distinct players, not total uses.** A social with 24 uses across
  2 players is one pair having fun; 272 uses across 72 players is part of the
  game. Everything archived here was used by **4 players or fewer** over the
  whole span, 23 of them by nobody at all.
- **Socials invoked from code were excluded**, whatever their player usage.
  NPC-fired socials never appear in the command log, so a mob script's social
  looks unused while being load-bearing. 56 of the original 244 are called from
  `dreamland_fenia`, `fenia.examples`, or C++ (`gquest/gangsters/gangmob.cpp`
  alone fires ~12), and none of those are in here.
- **Name collisions were excluded.** `bow`, `scream` and `whip` exist both as
  socials and as generic skills; the log stores the resolved command name, so
  their counts are unattributable.

Each social carries its own help article inline, so the help goes with the
file. Checked before the move: no `{hh` anchor anywhere in the five repos
points at these help ids or keywords, and player-authored `mysocial` entries
are self-contained text that never references a base social.
