# CHANGES

## 0.0.5 (not released yet)

- On the computer the window is the glass of the display of the board shown, turned as the board is held, with the
  screen at the orientation the board starts with: `board_display_init` gives the width, the height and the
  orientation it gives on the board. The title of the window tells the time on the bus of that board when it is SPI or
  QSPI. This takes DGX 0.10.10 for every board.
- On the computer a task asks the source of the sound, as on a board; the audio thread of SDL asked it before.
- On the computer the flash of a program that has partitions is kept in `build/host/flash.bin` between runs, while the
  partition table of the build is the one it has: NVS keeps what it was given. ESP-IDF made a new file in `/tmp` at
  each run and left it there.
- A sound may have `mixer_volume` in its data, the level of samples in percent of full scale heard comfortable on the
  speaker of the board, and `board_sound_t` gives it to the program (0 when the data has none).
  `examples/sound_level` plays a tone at levels from 5 to 100 percent to hear it.
- The JC8012P4A1C has its level, 50 percent, heard on the board.
- The level the person chose last is kept in NVS by `board_sound_volume_keep`, and `board_sound_init` gives it at the
  next start before the level of the data: how loud is right depends on the room. The component sets NVS up when the
  program has not.

## 0.0.4 (2026-11-06)

- A build whose configuration did not choose the board `BOARD` names stops at the configure with a message: on ESP-IDF
  6 the form `-B ... -D BOARD=<board>` took the chip of the preset `default` and built no board with no error, and so
  did an `sdkconfig` of another board in the build directory. CI checks it.
- On the computer the touch panel is the mouse: pressed on the window it is a finger on the glass, read through
  `board_dgx_di_pointer()` as on a board, with no calibration, and it turns with the display. This takes DGX-DI 0.1.5,
  the first version that builds for the linux target, and the boards take that version too. CI checks that the touch
  of `hello_board` starts on the computer.
- The page says what of the price of a kit is the board and what the parts, on the card and in the README of a
  project.
- The page lists the boards of the presets it has no kit for, those a command named and those whose kit does not fit
  the answers now, each with its radio, and opens a project with the current board its presets have.
- `board_select.py` writes the current board it chooses into `selection.json` too, and records it in the presets: a
  current board chosen on the page is taken in a project made by command, and one a command chose can be changed back
  on the page.
- The recipes take the component as `>=0.0.4`.

## 0.0.3 (2026-11-05)

- On the computer, the board `host`, the display is a window of DGX: the program draws on it through
  `board_dgx_screen()` as on the board it shows. This takes DGX 0.10.8, the first version that builds for the linux
  target, and the boards take that version too. The display is started from `app_main` or from a task with 48 KB of
  stack left; `board_select.py host` gives `app_main` 128 KB. The computer has no touch until DGX-DI builds for the
  linux target.
- CI builds `hello_board` for the computer under ESP-IDF 5.5 and 6.1, runs it with no screen and checks the picture of
  its window.
- The description of the component names no libraries, and the README puts the note on conditional dependencies in bold.
- The recipes take the component as `>=0.0.3`.

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
