#pragma once

/*
 * The boards a program of ESP-IDF runs on, described once as data and set up by this component:
 * a directory a board in boards-data/ (its pins, its buses, its peripherals) and the glue to
 * the drivers in boards/ (DGX for a frame buffer display, jef-sure/hd44780 for a character
 * one, DGX-DI for a touch panel, esp_codec_dev or the chip's DAC for sound). The component
 * knows no display by itself: a board may have none, and the display it has is one of its
 * peripherals, not the centre of it.
 *
 * The board is chosen once, by the line CONFIG_BOARD_SELECT_<BOARD>=y that the board's own
 * sdkconfig.defaults carries (tools/board_select.py puts that file into the project): the menu
 * of the configuration (Boards) follows it. The drivers of DGX a panel needs come with the
 * choice (selects), the parts of others (a touch driver, a codec) come by the rules of
 * idf_component.yml on the symbols the Kconfig of the boards defines beside the choice.
 *
 * The program asks for its board by kind, not by name: it never spells the name out, so the
 * same program runs on every board that gives it what it asks for. Every function here exists
 * on every board: one the board has not answers false, and the program goes on without it.
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

/*
 * A frame buffer display (a screen of DGX) the board has: the panel set up, the light on,
 * lying as the board shows it (the orientation its data names), its size in pixels and, for
 * the gestures of a touch and the fonts by the display's measure, in millimetres. false when
 * the board has none or it could not be set up; *out untouched then.
 *
 * A character display (HD44780: a 2004 on a PCF8574) is not this: it has no frame buffer and
 * no pixels, see board_character_display_init.
 */
struct board_display {
    void *screen;        /* dgx_screen_t *: the display to draw on */
    void *bus;           /* dgx_bus_protocols_t *: the bus of the panel, for tuning (dgx_dsi_tune) and its pace (dgx_dsi_frame_us); NULL when none */
    int   width, height; /* as it lies: the screen of the display, in pixels */
    int   mm_w, mm_h;    /* as measured with a ruler, lying as it is shown */
    int   dir_x, dir_y;  /* how it lies now, the values of dgx_orientation_t: 1 left-right / top-bottom, -1 right-left / bottom-top */
    bool  swap_xy;       /* and whether its x runs along the columns of the panel */
};
bool board_display_init(struct board_display *out);

/*
 * The display turned: the panel's own orientation call with these (dgx_orientation_t values,
 * as above), the width, height and millimetres of *display following. A program that shows
 * the board the other way up flips dir_x and dir_y from what board_display_init left in
 * *display. false when the board has no frame buffer display.
 */
bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy);

/*
 * A character display (HD44780) the board has or a module on its I2C bus brings (the 2004 on
 * a PCF8574 backpack, CONFIG_BOARD_MODULE_LCD2004_PCF8574): set up, cleared, its light on,
 * ready for the lcd_* calls of jef-sure/hd44780. false when there is none or it does not
 * answer; *out untouched then.
 */
struct board_character_display {
    void *lcd;       /* hd44780_t *: the display, for lcd_set_cursor, lcd_write_str and the rest of hd44780.h */
    int   cols, rows; /* its geometry, in characters */
};
bool board_character_display_init(struct board_character_display *out);

/*
 * The touch panel of the board as a device of DGX-DI, under the display taken before: the
 * device (a dgx_di_device_t *), and the pointer on it (a dgx_di_pointer_t *, as void * here:
 * DGX-DI names that type without a struct tag, and this header includes nothing of DGX-DI)
 * calibrated by the board's measured calibration (a warning when the calibration is not this
 * board's, or a placeholder not yet measured: the touch works, only not as straight). false
 * when the board has no touch panel or it could not be set up. The task that reads the
 * pointer is the program's (dgx_di_pointer_read): this sets the panel up, it does not read it.
 */
struct dgx_di_device;
bool board_touch_start(const struct board_display *display, struct dgx_di_device **device_out, void **pointer_out);

/*
 * The firmware of the touch panel, for a board whose panel keeps none of its own (the GSL3680
 * of the 10.1-inch Guition): written into it over I2C at every start. The vendor's array
 * carries no licence to give away, so it is not in this component: the program that builds
 * for such a board embeds it (EMBED_FILES in its CMakeLists.txt; DGX-DI's
 * tools/gsl_firmware.py makes the file from the board's package) and defines this function
 * itself, giving the embedded bytes. The component's own is weak and answers false: the
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
bool board_sound_start(board_sound_source_t source, uint32_t *rate_out);
void board_sound_source(board_sound_source_t source);

/*
 * The board's SPI buses, as its data names them (a name claims its host: "spi2" is the
 * chip's SPI2): its pins and its speed. A device the program adds takes a bus of the board
 * (two PN532 on one bus, each its own cs) or a host of the chip that no bus of the board
 * claims; board_spi_taken says which are taken. NULL / false on a board that wires none.
 */
struct board_spi_bus {
    int           host;            /* the host of the chip the name claims: SPI2_HOST, SPI3_HOST */
    int           mosi, miso, sclk; /* its pins; -1 (GPIO_NUM_NC) for a line not wired */
    unsigned long hz;              /* 0: none of the bus's own; a device's ask comes on top */
};
const struct board_spi_bus *board_spi_bus(int host);
bool board_spi_taken(int host);

/*
 * Any number of any bus of the board, by name: the kinds this component sets up and the
 * kinds it only keeps for the program (an sdio of a radio, a uart of a GPS, whatever a
 * board wires, now or later; a new kind needs no change here until it should be set up
 * by the component itself). false when the board has no such bus or no such number.
 */
bool board_bus_get(const char *bus, const char *field, long *out);

/*
 * The button of the board: false when it has none, else *pressed as it is now. The pin is
 * set up at the first call.
 */
bool board_button(bool *pressed);

#ifdef __cplusplus
}
#endif
