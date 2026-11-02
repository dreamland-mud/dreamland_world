# dreamland_world

[![Stand With Ukraine](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/badges/StandWithUkraine.svg)](https://stand-with-ukraine.pp.ua)

Game data for [DreamLand MUD](https://github.com/dreamland-mud/dreamland_code): the files the server reads at boot that are data, not code. This repository is the public half of the world. It also holds a small set of sample zones for local development. The full live world is not here.

## What is inside

| Folder | Holds |
|---|---|
| `commands`, `socials` | Command definitions and social messages |
| `helps` | Help articles in English, Russian and Ukrainian |
| `races`, `race-aptitudes`, `professions`, `religions`, `clans` | Character races, professions, religions and clans |
| `generic-skills`, `other-skills`, `skill-groups`, `clan-skills`, `card-skills` | Skill definitions |
| `spell` | Spell data tables (damage tiers, flavour) |
| `craft-professions`, `craft-skills`, `craft-wearlocs` | Crafting data |
| `fight`, `bonuses`, `liquids`, `wearlocations`, `behaviors`, `legacy-behaviors` | Combat tuning, item and behavior tables |
| `config`, `ports`, `grammar`, `hometowns`, `prio` | Server settings, listening ports, grammar data, hometowns and command priority lists |
| `languages` | In-game languages such as Khuzdul and Quenia |
| `quests`, `notes`, `descriptions`, `desires` | Autoquest types, note board settings, description tables and character desires |
| `areas.local` | Sample zones, listed in `area.lst.xml` |
| `fenia.local`, `fenia.examples` | Older Fenia scripts and small examples by entity type |
| `scripts` | Lint scripts for the data files |

The server rewrites `gquests/*.xml` itself, so do not edit those by hand. [Data-Configs](https://github.com/dreamland-mud/dreamland_code/wiki/Data-Configs) maps each folder to the code that loads it.

## How it mounts

At runtime this repository is the `share/DL` folder of the server install:

```bash
cd /path/to/runtime
git clone https://github.com/dreamland-mud/dreamland_world.git share/DL
git clone https://github.com/dreamland-mud/dreamland_fenia_public.git share/DL/fenia/public
```

The stock `etc/dreamland.xml` sets `tablePath` to `share/DL` and `areaDir` to `share/DL/areas.local`, so a local server loads only the sample zones. Zones are read once at start, so restart the server after you add or edit one. Most other data can be re-read in the game with `plugin reload most`. Port files in `ports/` need a restart.

The full build steps are in the [dreamland_code README](https://github.com/dreamland-mud/dreamland_code#readme).

## More

* [Data-Configs](https://github.com/dreamland-mud/dreamland_code/wiki/Data-Configs): folder by folder reference
* [Repositories](https://github.com/dreamland-mud/dreamland_code/wiki/Repositories): how the repositories fit together

## License

GPLv3. See `LICENSE`.
