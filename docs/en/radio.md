# The radio beside the chip

An ESP32-P4 has no radio. The Guition JC1060P470C and JC8012P4A1C carry an ESP32-C6
beside it, on SDIO, and the P4 reaches its Wi-Fi and Bluetooth through esp_hosted: the
C6 runs esp_hosted as a coprocessor, the program runs it as the host. Both sides should
run one version of esp_hosted; esp_hosted itself says so, and the newer one has the fixes.

## What comes with the board

- `espressif/esp_hosted`, in the range of the component's `idf_component.yml`, and
  `espressif/esp_wifi_remote` on ESP-IDF below 6.1 (6.1 has the Wi-Fi remote in
  `esp_wifi`). A program calls `esp_wifi_*` as on a chip with a radio.
- The settings of the host side, from the data of the board: the Bluetooth controller is
  in the C6, so the NimBLE stack of the program reaches it through esp_hosted.
- `board_radio_start()`, see [the API](api.md): it waits until the C6 answers and says in
  the log when it runs another esp_hosted than the program.
- A step of the flash that brings the C6 to the esp_hosted of the build.

## The firmware of the C6

The firmware of the C6 follows the esp_hosted the build of the program took, as
`dependencies.lock.<board>` keeps it: no second version to choose. A program that wants
another esp_hosted names it in its `main/idf_component.yml` (see
[versions](choosing-a-board.md#versions)), and the C6 follows that one.

Nothing of it is kept in the flash of the board. When the C6 may run another version,
the step of the flash:

1. writes a small update program into the place of the program's app, with the program's
   own bootloader and partition table, so NVS and the other partitions stay;
2. asks the C6 its version over USB;
3. when it differs, builds the image of the C6 from the same esp_hosted and sends it over
   USB to the update program, which passes it to the C6 over SDIO, and asks the version
   again after the C6 restarts.

The flash of the program follows and takes the place back. The update program and the
image are built only when needed, in `build/<board>/board_radio/`.

Measured on the JC1060P470C (ESP-IDF 6.1, esp_hosted 3.0.9 and 3.0.10, 2026-11-15): the first
build of the update program takes 18 s and of the image 21 s, then 0.1 s; a check with no
update adds about 9 s to the flash, an update about 19 s.

The version found is kept by the MAC of the board in
`$XDG_STATE_HOME/jef-sure-boards/radios.json` (`~/.local/state/...`). While the program asks
for that version, the step only reads the MAC from the USB of the chip and costs nothing.
A C6 changed by anything else (another computer, an update by the program itself, esptool
by hand) is not seen: the log of `board_radio_start()` says so, and

```sh
BOARD_RADIO_FORCE=1 idf.py flash
```

checks it again.

### idf.py flash

The component adds its step to the `flash` target; the port is the one `idf.py -p` names.
`ninja flash` with no `ESPPORT` checks nothing.

### Flash in VS Code

The ESP-IDF extension flashes with esptool itself, not through the `flash` target. Before
it, it runs the pre-flash task of the configuration chosen, and `board_select.py` writes
one into the preset of each board with such a radio:

```json
"vendor": {"espressif/vscode-esp-idf": {"settings": [{"type": "tasks", "value": {
    "preFlash": "cmake -E env ESPPORT=${config:idf.port} cmake --build ${config:idf.buildPath} --target board_radio"}}]}}
```

The extension waits for the task and does not flash when it fails. A pre-flash task of
the program's own is not replaced; `board_select.py` then says so.

### Another board on the port

The same file remembers the hardware each board was flashed as. A build for other hardware
stops before anything is written:

```
board_radio: the board on /dev/ttyACM1 (80:F1:B2:D3:3D:1B) was flashed as jc1060p470c from this computer,
and this build is for jc8012p4a1c: choose the board or the port of the build. BOARD_RADIO_FORCE=1 flashes it anyway.
```

esptool refuses an image for another chip revision by itself; this catches boards of one
chip.

### An older version

The step writes the version of the build when the C6 runs a newer one too, and says where
the build took it. With a copy of the registry set in the environment (see
[versions](choosing-a-board.md#versions)) it names the copy as well:

```
board_radio: the radio of 80:F1:B2:D3:3D:1B runs esp_hosted 3.0.10, newer than 3.0.9, which the program has from
/…/clock/dependencies.lock.jc1060p470c: the step writes the older 3.0.9. The build was configured with
IDF_COMPONENT_LOCAL_STORAGE_URL=file:///…/.espressif/tools, and the component manager takes a version that fits from
that storage before the registry. To take the newest of the registry, remove dependencies.lock.jc1060p470c and run
idf.py reconfigure without the variable.
```

Tried on the JC1060P470C on 2026-11-15: the copy of EIM of 2026-10-11 gave esp_hosted
3.0.9, and the lock solved again without it gave 3.0.10, which the step wrote back.

## A C6 with firmware of its own

A board whose C6 runs another firmware (not the esp_hosted of the program) says so in its
data: `"firmware": {"set": "tool"}` on the radio, in a board of the program in
`components/local-boards/` that extends the board of the catalog. The step of the flash
then does nothing, and `board_radio_start()` only says what the C6 runs.

Tried on the JC1060P470C with the handwritten clock on 2026-11-15: Wi-Fi, and the setup of
the network over BLE (NimBLE of the program through esp_hosted) with the C6 brought to 3.0.10
by the step.

The JC8012P4A1C takes the radio and the step from its own data, and CI builds it; neither was
tried on that board yet.

Tried on the JC4880P443C on 2026-11-18: its C6 came with a factory firmware too old to tell its
version, which the update program says as `runs unknown`; the step sent it the image all the
same, and the C6 then ran esp_hosted 3.0.10, the version of the build. The C6 checks a whole
image before it answers, which took that firmware more than 10 s. The update program starts from
the bootloader of the program, so it is built with the revision of the chip and the size of the
L2 cache of the program: on revision 3 of the ESP32-P4 one built for another cache panics before
its first line. Wi-Fi and Bluetooth were not tried on that board.

## What is not there yet

- A radio on SPI or UART: only SDIO.
