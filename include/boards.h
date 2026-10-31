#pragma once

/*
 * The boards a program of ESP-IDF runs on, described once as data and set up by this component:
 * a directory a board in catalog/boards/ (its pins, its buses, its peripherals) and the glue in
 * boards/. This header names no library. Which library drives a part is in the data, and its
 * adapter in adapters/ gives the handles in a header of its own: boards_dgx.h, boards_dgx_di.h,
 * boards_hd44780.h. A board may have no display, and the display it has is one of its
 * peripherals, not the centre of it.
 *
 * The board is chosen once, by the line CONFIG_BOARD_SELECT_<BOARD>=y that the board's own
 * sdkconfig.defaults carries (tools/board_select.py puts that file into the project): the menu
 * of the configuration (Boards) follows it. The libraries a board needs come by the rules of
 * idf_component.yml on the symbols the Kconfig of the boards defines beside the choice.
 *
 * The program asks for its board by kind, not by name: it never spells the name out, so the
 * same program runs on every board that gives it what it asks for. Every function here exists
 * on every board: one the board has not returns false, and the program goes on without it.
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* What the board the build chose is. */
struct board_info {
    const char *name;   /* its directory name, as its data names it */
    const char *title;  /* what the menu of the configuration showed */
    const char *target; /* the chip of it: esp32, esp32s3, esp32p4 */
};
const struct board_info *board_info(void);

/* The way a display runs along an axis: left to right and top to bottom, or the other way. */
enum { BOARD_DIR_FORWARD = 1, BOARD_DIR_BACKWARD = -1 };

/*
 * A graphics display the board has: the panel set up, the light on, lying as the board shows it
 * (the orientation its data names), its size in pixels and in millimetres. false when the board
 * has none or it could not be set up; *out untouched then.
 *
 * A character display (HD44780: a 2004 on a PCF8574) is not this: it has no pixels, see
 * board_character_display_init.
 */
struct board_display {
    int   width, height; /* as it lies, in pixels */
    int   mm_w, mm_h;    /* as measured with a ruler, as it is shown; 0 when the data has no size */
    int   dir_x, dir_y;  /* how it lies now: BOARD_DIR_FORWARD or BOARD_DIR_BACKWARD */
    bool  swap_xy;       /* and whether its x runs along the columns of the panel */
    const char *name;    /* its name in the data, for the log */
    int   index;         /* its place among the displays of the board */
};
int  board_display_count(void);
bool board_display_init(struct board_display *out);                /* the primary one, as board_display_init_at(0, out) */
bool board_display_init_at(int index, struct board_display *out);  /* 0 is the primary one; a second call gives the same display */

/*
 * The display turned: the panel's own orientation call with these (BOARD_DIR_* values), the
 * width, height and millimetres of *display following. A program that shows
 * the board the other way up flips dir_x and dir_y from what board_display_init left in
 * *display. false when the board has no graphics display, and for displays shown as one screen.
 */
bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy);

/*
 * A character display (HD44780) the board has or a module on its I2C bus brings (the 2004 on
 * a PCF8574 backpack, CONFIG_BOARD_MODULE_LCD2004_PCF8574): set up, cleared, its light on. false
 * when there is none or it does not respond; *out untouched then.
 */
struct board_character_display {
    int cols, rows; /* its geometry, in characters */
};
bool board_character_display_init(struct board_character_display *out);

/*
 * The touch panel of the board, under the display taken before, calibrated by the board's data
 * (a warning when the calibration is not this board's, or a placeholder not yet measured: the
 * touch works, only not as straight). false when the board has no touch panel or it could not
 * be set up. out may be NULL. The task that reads the panel is the program's: this sets the panel
 * up, it does not read it.
 */
struct board_touch {
    int fingers;      /* how many it follows at once */
    int x_max, y_max; /* its largest raw coordinates */
    const char *name; /* its name in the data, for the log */
    int index;        /* its place among the touch panels of the board */
};
int  board_touch_count(void);
bool board_touch_start(const struct board_display *display, struct board_touch *out); /* the first one over this display */
bool board_touch_start_at(int index, const struct board_display *display, struct board_touch *out); /* a second call gives the same panel */

/*
 * The firmware of the touch panel, for a board whose panel keeps none of its own (the GSL3680
 * of the 10.1-inch Guition): written into it over I2C at every start. The vendor's array
 * carries no licence to give away, so it is not in this component: the program that builds
 * for such a board embeds it (EMBED_FILES in its CMakeLists.txt; DGX-DI's
 * tools/gsl_firmware.py makes the file from the board's package) and defines this function
 * itself, giving the embedded bytes. The component's own is weak and returns false: the
 * board builds and runs without the file, its touch off.
 */
bool board_touch_firmware(const uint8_t **start, size_t *size);

/*
 * The sound of the board: its hardware set up and a task of its own taking the next samples
 * from the program (16 bits a sample, mono, at *rate_out) and sending them to the speaker;
 * the task ends only when the firmware stops. source may be NULL: silence, until the program
 * gives one with board_sound_source. false when the board has no sound or it could not be set
 * up. How the program makes its samples is its business: this is the hardware of the board
 * and the pacing of the output, nothing of a mixer.
 */
typedef void (*board_sound_source_t)(int16_t *samples, size_t count);
int  board_sound_count(void);
bool board_sound_start(board_sound_source_t source, uint32_t *rate_out); /* the first one */
bool board_sound_start_at(int index, board_sound_source_t source, uint32_t *rate_out);
void board_sound_source(board_sound_source_t source);
void board_sound_source_at(int index, board_sound_source_t source);

/*
 * The board's SPI buses, as its data names them (the name is the host: "spi2" is the chip's
 * SPI2), with pins and speed. A device the program adds goes on one of these buses with its
 * own cs (two PN532 on one bus) or on a host board_spi_taken reports free. board_spi_bus
 * returns NULL when the host has no such bus, and when the bus has only a display: a display
 * driver may keep such a bus between drawings, so a device added to it would wait forever.
 */
struct board_spi_bus {
    int           host;            /* the host of the chip the name claims: SPI2_HOST, SPI3_HOST */
    int           mosi, miso, sclk; /* its pins; -1 (GPIO_NUM_NC) for a line not wired */
    unsigned long hz;              /* 0: none of the bus's own; a device's ask comes on top */
};
const struct board_spi_bus *board_spi_bus(int host);
bool board_spi_taken(int host);

/*
 * Any number of any bus of the board, by name, and of any device the component does not set
 * up, by its name in the data ("nfc_in", "cs"): the kinds this component sets up and the
 * kinds it only keeps for the program (an sdio of a radio, a uart of a GPS, whatever a
 * board wires, now or later; a new kind needs no change here until it should be set up
 * by the component itself). false when the board has no such bus or no such number.
 */
bool board_bus_get(const char *bus, const char *field, long *out);

/*
 * The buttons of the board: false when there is no such button, else *pressed as it is now. A
 * pin is set up at its first call. board_button is the first one.
 */
int         board_button_count(void);
const char *board_button_name(int index); /* NULL when there is no such button */
bool        board_button(bool *pressed);
bool        board_button_at(int index, bool *pressed);

#ifdef __cplusplus
}
#endif
