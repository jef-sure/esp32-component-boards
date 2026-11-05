# CHANGES

## 0.0.1 (not released yet)

The first release: the boards a program runs on are described once, as data, and the program asks for their hardware
by kind, never by the name of a board.

### Boards

- Ten boards: the CYD S028R (ESP32-2432S028R), Guition JC1060P470C, JC4827W543C and JC8012P4A1C, Waveshare
  ESP32-C3-Zero, ESP32-S3-Zero, ESP32-P4-ETH and ESP32-P4-POE-ETH, an ESP32 DevKit and an ESP32-S3 DevKit. A part
  says in `checked` how it is known: from a schematic, from the code of its maker, or measured on the board.
- Sixteen modules (displays, NFC readers, LED strips, sensors), which the page wires to a board in a board of the
  program. A module of the program's own lies in its `components/local-boards/modules/`: `examples/local_boards` has a
  2004 character LCD on a PCF8574 there.
- A board of a program lies in its `components/local-boards/`, in the layout of `catalog/`, and is read before it.

### The program

- `boards.h`: every function exists on every board, and one for a part the board does not have returns `false`.
- A graphics display through DGX (MIPI-DSI, QSPI, SPI), with its size in pixels and in millimetres and the way it lies;
  two displays shown as one screen. A character display through hd44780. A touch panel as a device of DGX-DI, with the
  calibration of the data. LVGL through DGX-LVGL. Sound: an ES8311 codec, an I2S amplifier or the DAC of the ESP32.
  Buttons. A camera and any bus the board wires, as data the program reads.
- `BOARD_PIXELS` and `BOARD_MM` give the size of the primary display to the CMake of the program.
- The computer as a board: the linux target of ESP-IDF, a window of SDL2 as large as the display of a board.

### Choosing boards

- `tools/board_select.py` names the boards of a project once: `sdkconfig.defaults.<board>` of each with the lines of
  the revision of its chip, `CMakePresets.json` with a preset for each board and `default` for the current one, and a
  lock of the components for each board. ESP-IDF 6 builds by the presets, ESP-IDF 5 by `-B build/<board>`.
  `--current` changes the current board, `--again` makes every file again after the component changes.
- What a board needs comes with the choice: the DGX drivers of its panel, its touch driver and its codec by the rules
  of the manifest; a build for one board downloads nothing of another.

### The page and the tools

- `editor/index.html`: the roles a device needs, and the kits that fit, each a board and the modules it lacks, with
  the wires, the levels, the price as a range and what is not known. A budget, a pinned board or part, tones and PWM,
  chains of LEDs or modules, and what the person has already, which costs nothing. Several kits make the boards of one
  project, one of them current. The page writes a new
  project, or a board of an existing program, into a folder.
- `tools/boards_mcp.py`: the page beside an agent of the person over MCP, or alone with `--serve`. It writes a project
  only into its folder, when the person allows it once or for ever, and not over a file a person changed unless that
  file is ticked.
- `tools/board_project.py`: a new project without the page, or a kit of the page taken back.
- `tools/board_bom.py`: the list of goods of a project with its prices. Prices are in the data; a report in a GitHub
  issue adds one, by `tools/take_report.py`.
- `tools/board_pins.py`, `tools/boards_gen.py`, `tools/check_boards.py`, `tools/check_format.py`: the map of pins, the
  generated glue and the checks of the data.
- CI builds every board under ESP-IDF 5.5 and 6.1, with LVGL, a board of a program with a display and a 2004, two boards in one
  project, and a new project made as the README says.
- Documentation in English and Russian, starting with a quick start: a program on a board from an empty folder.

### Known

- The GSL3680 of the JC8012P4A1C keeps no firmware of its own, and the array of its maker has no licence to give away:
  the program embeds it, see `docs/en/touch-firmware.md`. Without it the board builds and runs with its touch off.
- On the computer the window stays black and there is no touch until DGX and DGX-DI build for the linux target.
- The camera is data only: the component does not start it.
