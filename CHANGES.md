# CHANGES

## 0.0.2 (2026-11-05)

- One example comes with the component from the registry, `hello`, the program of the quick start, and it builds as
  the registry hands it out. The examples of 0.0.1 took the component from a clone and did not configure.
- The recipes take the component as `>=0.0.2`: a caret on a version 0.0.x would take that version alone.
- The README says that every dependency but ESP-IDF is conditional: a build downloads only what the chosen board
  needs, which the list of the registry cannot show.
- `board_select.py` names the version of a copy from the registry in the files it writes; it wrote `?`.

## 0.0.1 (2026-11-05)

The first release. The boards a program runs on are described once, as data; the component sets the hardware of the
chosen board up, and the program asks for its parts by kind, never by the name of a board. Ten boards, the page that
chooses a board and the parts for a device and writes the project, and the tools around them: see the README and the
[quick start](docs/en/quick-start.md).

Known:

- The GSL3680 of the JC8012P4A1C keeps no firmware of its own, and the array of its maker has no licence to give away:
  the program embeds it, see `docs/en/touch-firmware.md`. Without it the board builds and runs with its touch off.
- On the computer the window stays black and there is no touch until DGX and DGX-DI build for the linux target.
- The camera is data only: the component does not start it.
