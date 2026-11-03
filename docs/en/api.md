# The API: boards.h

`#include "boards.h"`. Every function below exists on every board. A function
for a part the board does not have returns `false` (or `NULL`) and leaves its
output untouched; the program needs no `#if` on the board. `boards.h` names no
library: it gives sizes, millimetres and orientation. The handles of a library
come from the header of its adapter, and from there the program uses that library
directly: `boards_dgx.h`, `boards_dgx_di.h`, `boards_hd44780.h`. Every public
structure has a typedef ending in `_t`, as `board_display_t`; its tag stays, so a
header of the program can declare it ahead (`struct board_display;`).

## What the board is

```c
typedef struct board_info { const char *name, *title, *target; } board_info_t;
const board_info_t *board_info(void);
```

`name` is the directory in `catalog/boards/` (`"cyd_s028r"`), `title` what the menu
showed, `target` the chip as `CONFIG_IDF_TARGET` names it (`"esp32"`, `"esp32s3"`, `"esp32p4"`, `"esp32c3"`). For the log
and for a settings page, not for deciding what to do: ask by kind instead.

## A graphics display

```c
typedef struct board_display {
    int   width, height; /* as shown, in pixels */
    int   mm_w, mm_h;    /* as shown, in millimetres; 0 when the data has no size */
    int   dir_x, dir_y;  /* BOARD_DIR_FORWARD: left to right, top to bottom; BOARD_DIR_BACKWARD: the other way */
    bool  swap_xy;
    const char *name; /* its name in the data, for the log */
    int   index;      /* its place among the displays of the board */
} board_display_t;
int  board_display_count(void);
bool board_display_init(board_display_t *out);
bool board_display_init_at(int index, board_display_t *out);
bool board_display_orientation(board_display_t *display, int dir_x, int dir_y, bool swap_xy);
```

A board may have several displays. `board_display_init` starts the primary one;
`board_display_init_at` takes its place, 0 is the primary one. A second call gives
the same display. Displays the data joins into one screen (`display_groups`) have
a place of their own: starting it starts both and gives one wider screen. Such a
screen does not turn: `board_display_orientation` returns `false`, and each of the
two keeps its own. `board_touch_start` takes the display the touch covers and
returns `false` for another one.

`board_display_init` brings the panel up with the light on, oriented as the
board shows it (the data's `original_orientation`), and fills `*out`. The
handles of DGX are in `boards_dgx.h`:

```c
dgx_screen_t        *board_dgx_screen(const board_display_t *display);
dgx_bus_protocols_t *board_dgx_bus(const board_display_t *display);
```

The screen is what `dgx_draw.h` draws on. The bus is for what only the bus knows:
on MIPI-DSI, `dgx_dsi_frame_us()` to pace drawing by the panel's frames and
`dgx_dsi_bench()` / `dgx_dsi_tune()` to measure the board once and keep the numbers
(see [calibration.md](calibration.md)).

`board_display_orientation` turns the display: it calls the panel driver's own
orientation function with these values and updates `width`, `height`, `mm_w`,
`mm_h`, `dir_x`, `dir_y`, `swap_xy`. To show the board the other way up, flip
both directions from what init left:

```c
board_display_orientation(&display, -display.dir_x, -display.dir_y, display.swap_xy);
```

The millimetres are the measured size of the picture as shown: DGX-DI's
gestures and the fonts of DGX use them to make a centimetre a centimetre on
every board.

## A character display

```c
typedef struct board_character_display { int cols, rows; } board_character_display_t;
bool board_character_display_init(board_character_display_t *out);
```

An HD44780 the board has, or a module on its I2C bus brings. The display is
set up, cleared, its backlight on. `board_hd44780(&lcd)` of `boards_hd44780.h`
gives the `hd44780_t *` for `lcd_set_cursor`, `lcd_write_str` and the rest of
`hd44780.h`. Only when the build has one (`CONFIG_BOARD_DISPLAY_HD44780`) is
hd44780 linked, so include the header under that symbol in a program that runs
on boards without.

## The touch panel

```c
typedef struct board_touch { int fingers; int x_max, y_max; const char *name; int index; } board_touch_t;
int  board_touch_count(void);
bool board_touch_start(const board_display_t *display, board_touch_t *out);
bool board_touch_start_at(int index, const board_display_t *display, board_touch_t *out);
```

Sets a panel up under the display taken before, calibrated by the board's measured
calibration. `board_touch_start` takes the first panel that covers this display,
`board_touch_start_at` a panel by its place. A second call gives the same panel. `out`
may be `NULL`. `boards_dgx_di.h` gives the device and the pointer on it:

```c
dgx_di_device_t  *board_dgx_di_device(const board_touch_t *touch);
dgx_di_pointer_t *board_dgx_di_pointer(const board_touch_t *touch);
```

The pointer follows the display's orientation: after
`board_display_orientation` its coordinates are those of the display in its
orientation now. The task that reads it is the program's:

```c
#include "boards_dgx_di.h"
board_touch_t touch;
board_touch_start(&display, &touch);
dgx_di_pointer_t *pointer = board_dgx_di_pointer(&touch);
for (;;) {
    dgx_di_pointer_read(pointer, now_ms);
    int x, y;
    if (dgx_di_pointer_first(pointer, &x, &y)) { /* the first finger, in pixels of the display */ }
    vTaskDelay(pdMS_TO_TICKS(10));
}
```

The warnings in the log: *the calibration is not this board's* means the
calibration in the data was measured on another display size or panel range;
*a placeholder, not measured* means the data has `"measured": false`. The
touch works in both cases, only not straight.

```c
void board_touch_firmware_set(const uint8_t *start, size_t size);
```

The firmware of a panel that keeps none of its own (the GSL3680 of the 10.1-inch
Guition): a program that embeds it gives the bytes here before `board_touch_start`.
Without it the touch of that board is off. See [touch-firmware.md](touch-firmware.md).

## Sound

```c
typedef struct board_sound { uint32_t rate; const char *name; int index; } board_sound_t;
typedef void (*board_sound_source_t)(int16_t *samples, size_t count);
int  board_sound_count(void);
bool board_sound_init(board_sound_t *out);
bool board_sound_init_at(int index, board_sound_t *out);
bool board_sound_start(board_sound_source_t source, uint32_t *rate_out);
bool board_sound_start_at(int index, board_sound_source_t source, uint32_t *rate_out);
void board_sound_source(board_sound_source_t source);
void board_sound_source_at(int index, board_sound_source_t source);
```

The functions without `_at` are for the first output. `board_sound_init` sets the
codec, the amplifier or the DAC up and returns its rate, and the header of its
adapter gives the handle of the library: `board_esp_codec_dev()` in
`boards_esp_codec_dev.h` (an ES8311: write with `esp_codec_dev_write`, set the
volume with `esp_codec_dev_set_out_vol`), `board_i2s_channel()` in
`boards_esp_driver_i2s.h` (an amplifier on I2S), `board_dac_continuous()` in
`boards_esp_driver_dac.h` (the DAC of an ESP32, 8 bits a sample). A program with a
mixer of its own writes there itself and does not call `board_sound_start`.

`board_sound_start` does the same setup and runs a task that asks `source` for the
next `count` samples, 16-bit mono at `*rate_out`, and sends them; the writes block
on the hardware, which sets the pace. `source` may be `NULL` for silence and set
later with `board_sound_source`. The task runs until the firmware stops. A second
call of either returns the same sound, from any task. A mixer, a format other than
16-bit mono are the program's business: this is the hardware and its pacing,
nothing more.

## Buses

```c
typedef struct board_spi_bus { int host, mosi, miso, sclk; unsigned long hz; } board_spi_bus_t;
const board_spi_bus_t *board_spi_bus(int host);
bool board_spi_taken(int host);
bool board_bus_get(const char *bus, const char *field, long *out);
```

For a program that adds a device of its own. `board_spi_bus(SPI3_HOST)` returns
the pins and the speed of the board's SPI bus on that host; a device goes on it
with its own `cs`.

It returns `NULL` when the board has no such bus, and when the bus has only a
display. DGX sets up such a bus and does not release it between drawings, so a
device of the program would wait for the bus forever.

When the board's data puts a touch panel or an SD card on the display's bus, the
component sets the bus up and the display joins it with `dgx_spi_init_on_bus()`.
The display then holds the bus only while it draws. The program's device can be
used between drawings, but not inside a `dgx_screen_progress_up()` batch in the
same task: the display holds the bus until the batch ends.

`board_spi_taken` says whether a host is claimed by any bus of the board, SPI or
QSPI, so a free host can be found.

```c
struct i2c_master_bus_t *board_i2c(int port);   /* i2c_master_bus_handle_t of ESP-IDF */
bool board_i2c_taken(int port);
```

`board_i2c(0)` returns the I2C master of the board on port 0. The first call makes it,
from any task, and later calls return the same master, which the parts of the board on
that bus, as a touch panel or a codec, use as well. A
device the program adds goes on it with `i2c_master_bus_add_device`; a second gamepad
of the same address goes on the other port. ESP-IDF takes one master on a port, so a
program makes its own master only on a port `board_i2c_taken` reports free. NULL when
the board names no bus on that port or the master cannot be made.
`board_bus_get("nfc_in_nfc", "cs", &pin)` gives the lines of a device the component does
not set up, by its name in the data, and the bus it is on: `"host"` (an SPI host, as
`SPI3_HOST`, for `board_spi_bus`), `"port"` (of I2C or a UART) and `"address"` (7 bits,
on I2C, when the data gives it). A program so takes a reader with no pin of the board in
its code:

```c
long host, cs;
const board_spi_bus_t *bus;
if (board_bus_get("nfc_in_nfc", "host", &host) && board_bus_get("nfc_in_nfc", "cs", &cs) && (bus = board_spi_bus((int)host)))
    reader = pn532_spi_init(bus->host, bus->sclk, bus->miso, bus->mosi, cs, 0);
```

`board_bus_get("sdio.sdio0", "clk", &pin)` reads any number of any bus
the data names, including the kinds the component does not set up.

## The buttons

```c
int         board_button_count(void);
const char *board_button_name(int index);
bool        board_button(bool *pressed);
bool        board_button_at(int index, bool *pressed);
```

`false` when the board has none; else the pin is set up at the first call and
`*pressed` is its state now. Debouncing and holds are the program's.

## What to include, what to link

The component links the libraries the chosen board needs (DGX, DGX-DI,
hd44780, the touch driver, esp_codec_dev) and their include paths reach the
program through it. A program that runs on boards with and without a part
includes the adapter's header under the symbol that says the part is there:

```c
#if CONFIG_BOARD_DISPLAY_GRAPHICS
#include "boards_dgx.h"
#include "dgx_draw.h"
#endif
#if CONFIG_BOARD_TOUCH
#include "boards_dgx_di.h"
#endif
#if CONFIG_BOARD_DISPLAY_HD44780
#include "boards_hd44780.h"
#endif
#if CONFIG_BOARD_SOUND_ES8311
#include "boards_esp_codec_dev.h"
#endif
```

A program that always has a display may include these headers unconditionally
and name `jef-sure/dgx` in its own manifest as well.
