# Station

The Amankenzie Station weather app, as one app that works at home and away.
This repo holds only the app's code: no weather data, addresses, coordinates or tokens.
At home it reads the Mac mini live over its secure address; away it reads the online copy
kept in a private repo, using a read-only token stored only on each device.

- `index.html`: the Station app (v1.24). Add it to the Home Screen from Safari.
  - Live from the Mac mini when its secure address answers (checked in under 2 s at start, then every minute).
  - Switches to the online copy by itself when the Mac mini can't be reached (for example on cellular), and back again at home.
  - A notice at the top shows whenever it is on the online copy (how old it is, and that it is read-only).
  - Settings › Data source: **Always use the online copy** switch, Mac mini address, GitHub token (Show, Copy token, Remove token, which asks first).
  - Updates itself: on opening it checks GitHub for a newer version (skipping caches) and reloads.
  - Needs Station server v1.20 or newer on the Mac mini.
- `test.html`: green/red Station Test (v0.1), proves both sources.
- `tools/`: how `index.html` is made from the Station page (`build_app.py`, `station_link.js`) and its browser test (`test_app.py`).

Versions in this repo: Station Test v0.1, Station app v1.21, v1.22, v1.23, v1.24.
