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
typedef struct board_info {
    const char *name;   /* its directory name, as its data names it */
    const char *title;  /* what the menu of the configuration showed */
    const char *target; /* the chip of it, as CONFIG_IDF_TARGET names it */
} board_info_t;
const board_info_t *board_info(void);

/* The way a display runs along an axis: left to right and top to bottom, or the other way. */
enum { BOARD_DIR_FORWARD = 1, BOARD_DIR_BACKWARD = -1 };

/*
 * A graphics display the board has: the panel set up, the light on, as the board shows it
 * (the orientation its data names), its size in pixels and in millimetres. false when the board
 * has none or it could not be set up; *out untouched then.
 *
 * A character display (HD44780: a 2004 on a PCF8574) is not this: it has no pixels, see
 * board_character_display_init.
 */
typedef struct board_display {
    int   width, height; /* as shown, in pixels */
    int   mm_w, mm_h;    /* as measured with a ruler, as it is shown; 0 when the data has no size */
    int   dir_x, dir_y;  /* its orientation now: BOARD_DIR_FORWARD or BOARD_DIR_BACKWARD */
    bool  swap_xy;       /* and whether its x runs along the columns of the panel */
    const char *name;    /* its name in the data, for the log */
    int   index;         /* its place among the displays of the board */
} board_display_t;
int  board_display_count(void);
bool board_display_init(board_display_t *out);                /* the primary one, as board_display_init_at(0, out) */
bool board_display_init_at(int index, board_display_t *out);  /* 0 is the primary one; a second call gives the same display */

/*
 * The display turned: the panel's own orientation call with these (BOARD_DIR_* values), the
 * width, height and millimetres of *display following. A program that shows
 * the board the other way up flips dir_x and dir_y from what board_display_init left in
 * *display. false when the board has no graphics display, and for displays shown as one screen.
 */
bool board_display_orientation(board_display_t *display, int dir_x, int dir_y, bool swap_xy);

/*
 * A character display (HD44780) the board has or a module on its I2C bus brings (the 2004 on
 * a PCF8574 backpack, CONFIG_BOARD_MODULE_LCD2004_PCF8574): set up, cleared, its light on. false
 * when there is none or it does not respond; *out untouched then.
 */
typedef struct board_character_display {
    int cols, rows; /* its geometry, in characters */
} board_character_display_t;
bool board_character_display_init(board_character_display_t *out);

/*
 * The touch panel of the board, under the display taken before, calibrated by the board's data
 * (a warning when the calibration is not this board's, or a placeholder not yet measured: the
 * touch works, only not as straight). false when the board has no touch panel or it could not
 * be set up. out may be NULL. The task that reads the panel is the program's: this sets the panel
 * up, it does not read it.
 */
typedef struct board_touch {
    int fingers;      /* how many it follows at once */
    int x_max, y_max; /* its largest raw coordinates */
    const char *name; /* its name in the data, for the log */
    int index;        /* its place among the touch panels of the board */
} board_touch_t;
int  board_touch_count(void);
bool board_touch_start(const board_display_t *display, board_touch_t *out); /* the first one over this display */
bool board_touch_start_at(int index, const board_display_t *display, board_touch_t *out); /* a second call gives the same panel */

/*
 * The firmware of the touch panel, for a board whose panel keeps none of its own (the GSL3680
 * of the 10.1-inch Guition): written into it over I2C at every start. The vendor's array
 * carries no licence to give away, so it is not in this component: the program that builds
 * for such a board embeds it (EMBED_FILES in its CMakeLists.txt; DGX-DI's
 * tools/gsl_firmware.py makes the file from the board's package) and gives the embedded bytes
 * here, before board_touch_start. Without it the board builds and runs, its touch off.
 * A second call replaces the first; NULL or a size of 0 takes it back.
 */
void board_touch_firmware_set(const uint8_t *start, size_t size);

/*
 * The sound of the board. board_sound_init sets its hardware up and returns what it is: the
 * header of its adapter gives the handle of the library (boards_esp_codec_dev.h,
 * boards_esp_driver_i2s.h, boards_esp_driver_dac.h), and a program that writes its samples itself
 * stops there. board_sound_start does the same and runs a task of its own that takes the next
 * samples from the program (16 bits a sample, mono, at *rate_out) and sends them to the speaker;
 * the task ends only when the firmware stops. source may be NULL: silence, until the program gives
 * one with board_sound_source. false when the board has no sound or it could not be set up. A
 * second call returns the same sound. How the program makes its samples is its business: this is
 * the hardware of the board and the pacing of the output, nothing of a mixer.
 */
typedef struct board_sound {
    uint32_t    rate;  /* samples a second, 16 bits each, mono */
    const char *name;  /* its name in the data, for the log */
    int         index; /* its place among the sounds of the board */
} board_sound_t;
typedef void (*board_sound_source_t)(void *ctx, int16_t *samples, size_t count); /* ctx: as given to start or source */
int  board_sound_count(void);
bool board_sound_init(board_sound_t *out); /* the first one, as board_sound_init_at(0, out) */
bool board_sound_init_at(int index, board_sound_t *out);
bool board_sound_start(board_sound_source_t source, void *ctx, uint32_t *rate_out); /* the first one */
bool board_sound_start_at(int index, board_sound_source_t source, void *ctx, uint32_t *rate_out);
void board_sound_source(board_sound_source_t source, void *ctx);
void board_sound_source_at(int index, board_sound_source_t source, void *ctx);

/*
 * The board's SPI buses, as its data names them (the name is the host: "spi2" is the chip's
 * SPI2), with pins and speed. A device the program adds goes on one of these buses with its
 * own cs (two PN532 on one bus) or on a host board_spi_taken reports free. board_spi_bus
 * returns NULL when the host has no such bus, and when the bus has only a display: a display
 * driver may keep such a bus between drawings, so a device added to it would wait forever.
 */
typedef struct board_spi_bus {
    int           host;            /* the host of the chip the name claims: SPI2_HOST, SPI3_HOST */
    int           mosi, miso, sclk; /* its pins; -1 (GPIO_NUM_NC) for a line not wired */
    unsigned long hz;              /* 0: none of the bus's own; a device's ask comes on top */
} board_spi_bus_t;
const board_spi_bus_t *board_spi_bus(int host);
bool board_spi_taken(int host);

/*
 * The board's I2C buses, by port, as its data names them ("i2c0" is the chip's port 0). board_i2c
 * returns the master of the board on a port: the first call makes it, from any task, and later calls
 * return the same one, which the parts of the board on that port (a touch panel, a codec) use as well.
 * A device the program adds goes on it with i2c_master_bus_add_device.
 * ESP-IDF takes one master on a port, so a program makes its own only on a port board_i2c_taken
 * reports free. NULL when the board has no bus on that port or the master cannot be made. The type
 * is i2c_master_bus_handle_t of ESP-IDF, named by its tag so this header needs no driver.
 */
struct i2c_master_bus_t;
struct i2c_master_bus_t *board_i2c(int port);
bool board_i2c_taken(int port);

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
