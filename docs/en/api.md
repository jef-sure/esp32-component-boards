# The API: boards.h

`#include "boards.h"`. Every function below exists on every board. A function
for a part the board does not have answers `false` (or `NULL`) and leaves its
output untouched; the program needs no `#if` on the board. The handles the
functions give are those of the libraries that drive the hardware: the program
uses DGX, DGX-DI and hd44780 directly from there.

## What the board is

```c
struct board_info { const char *name, *title, *target; };
const struct board_info *board_info(void);
```

`name` is the directory in `boards-data/` (`"cyd"`), `title` what the menu
showed, `target` the chip (`"esp32"`, `"esp32s3"`, `"esp32p4"`). For the log
and for a settings page, not for deciding what to do: ask by kind instead.

## A frame buffer display

```c
struct board_display {
    void *screen;        /* dgx_screen_t * */
    void *bus;           /* dgx_bus_protocols_t *, NULL when none */
    int   width, height; /* as it lies, in pixels */
    int   mm_w, mm_h;    /* as it lies, in millimetres */
    int   dir_x, dir_y;  /* dgx_orientation_t values: 1 left-right / top-bottom, -1 the other way */
    bool  swap_xy;
};
bool board_display_init(struct board_display *out);
bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy);
```

`board_display_init` brings the panel up with the light on, oriented as the
board shows it (the data's `original_orientation`), and fills `*out`. `screen`
is a DGX screen: `#include "dgx_draw.h"` and draw. `bus` is the DGX bus of the
panel, for what only the bus knows: on MIPI-DSI, `dgx_dsi_frame_us()` to pace
drawing by the panel's frames and `dgx_dsi_bench()` / `dgx_dsi_tune()` to
measure the board once and keep the numbers (see [calibration.md](calibration.md)).

`board_display_orientation` turns the display: it calls the panel driver's own
orientation function with these values and updates `width`, `height`, `mm_w`,
`mm_h`, `dir_x`, `dir_y`, `swap_xy`. To show the board the other way up, flip
both directions from what init left:

```c
board_display_orientation(&display, -display.dir_x, -display.dir_y, display.swap_xy);
```

The millimetres are the measured size of the picture as it lies: DGX-DI's
gestures and the fonts of DGX use them to make a centimetre a centimetre on
every board.

## A character display

```c
struct board_character_display { void *lcd; int cols, rows; };
bool board_character_display_init(struct board_character_display *out);
```

An HD44780 the board has, or a module on its I2C bus brings. The display is
set up, cleared, its backlight on; `lcd` is an `hd44780_t *`:
`#include "hd44780.h"`, then `lcd_set_cursor`, `lcd_write_str` and the rest
of that header. Only when the build has one (`CONFIG_BOARD_DISPLAY_HD44780`)
is hd44780 linked, so include its header under that symbol in a program that
runs on boards without.

## The touch panel

```c
bool board_touch_start(const struct board_display *display,
                       struct dgx_di_device **device_out, void **pointer_out);
```

Sets the panel up under the display taken before and gives the DGX-DI device
(`dgx_di_device_t *`) and the pointer on it (`dgx_di_pointer_t *`, passed as
`void *` because DGX-DI names that type without a struct tag and `boards.h`
includes nothing of DGX-DI), calibrated by the board's measured calibration.
The pointer follows the display's orientation: after
`board_display_orientation` its coordinates are those of the display as it
lies now. The task that reads it is the program's:

```c
#include "dgx_di.h"
struct dgx_di_device *device;
void *pointer;
board_touch_start(&display, &device, &pointer);
for (;;) {
    dgx_di_pointer_read(pointer, now_ms);   /* void * converts to dgx_di_pointer_t * in C */
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
bool board_touch_firmware(const uint8_t **start, size_t *size);
```

The hook for a panel that keeps no firmware of its own (the GSL3680 of the
10.1-inch Guition): the component's version is weak and answers `false`; a
program that embeds the firmware defines this function itself. See
[touch-firmware.md](touch-firmware.md).

## Sound

```c
typedef void (*board_sound_source_t)(int16_t *samples, size_t count);
bool board_sound_start(board_sound_source_t source, uint32_t *rate_out);
void board_sound_source(board_sound_source_t source);
```

`board_sound_start` sets the codec (or the DAC) up and runs a task that asks
`source` for the next `count` samples, 16-bit mono at `*rate_out`, and sends
them; the writes block on the hardware, which sets the pace. `source` may be
`NULL` for silence and set later with `board_sound_source`. The task runs until
the firmware stops. A mixer, a volume, a format other than 16-bit mono are the
program's business: this is the hardware and its pacing, nothing more.

## Buses

```c
struct board_spi_bus { int host, mosi, miso, sclk; unsigned long hz; };
const struct board_spi_bus *board_spi_bus(int host);
bool board_spi_taken(int host);
bool board_bus_get(const char *bus, const char *field, long *out);
```

For a program that adds a device of its own. `board_spi_bus(SPI3_HOST)` gives
the pins and the speed of a plain SPI bus the board wires on that host, or
`NULL`; a device joins it with its own `cs`. `board_spi_taken` says whether a
host is claimed by any bus of the board, SPI or QSPI, so a free host can be
found. `board_bus_get("sdio.sdio0", "clk", &pin)` reads any number of any bus
the data names, including the kinds the component does not set up.

## The button

```c
bool board_button(bool *pressed);
```

`false` when the board has none; else the pin is set up at the first call and
`*pressed` is its state now. Debouncing and holds are the program's.

## What to include, what to link

The component links the libraries the chosen board needs (DGX, DGX-DI,
hd44780, the touch driver, esp_codec_dev) and their include paths reach the
program through it. A program that runs on boards with and without a part
includes the library's header under the symbol that says the part is there:

```c
#if CONFIG_BOARD_DISPLAY_FRAMEBUFFER
#include "dgx_draw.h"
#endif
#if CONFIG_BOARD_TOUCH
#include "dgx_di.h"
#endif
#if CONFIG_BOARD_DISPLAY_HD44780
#include "hd44780.h"
#endif
```

A program that always has a display may include `dgx_draw.h` unconditionally
and name `jef-sure/dgx` in its own manifest as well.
