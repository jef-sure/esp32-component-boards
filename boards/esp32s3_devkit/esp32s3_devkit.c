/*
 * The glue of esp32s3_devkit, made by tools/boards_gen.py from catalog/boards/esp32s3_devkit/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * Every function of boards.h is here: by the data for the parts the board has, returning
 * false for the parts it has not, so the contract of boards.h holds at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "esp_log.h"
#include <stdlib.h>
#include <string.h>

/* ESP32-S3 DevKit, 16 MB, 8 MB PSRAM: A standard ESP32-S3 dev board with two USB-C ports, a CH343 USB bridge on one of them, an RGB LED and a BOOT button. */

/* The buses of the board. */

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_table[] = {{"led", "data", 48}};

bool board_bus_get(const char *bus, const char *field, long *out)
{
    for (size_t i = 0; i < sizeof(board_bus_table) / sizeof(board_bus_table[0]); ++i) {
        if (board_bus_table[i].bus && strcmp(board_bus_table[i].bus, bus) == 0 && strcmp(board_bus_table[i].field, field) == 0) {
            if (out) *out = board_bus_table[i].value;
            return true;
        }
    }
    return false;
}

/* The board has no SPI bus open to the program's devices. */
const struct board_spi_bus *board_spi_bus(int host)
{
    (void)host;
    return NULL;
}

bool board_spi_taken(int host)
{
    (void)host;
    return false;
}

/* The board wires no I2C bus: nothing for board_glue_i2c to make. */
const struct board_i2c_pins *board_i2c_pins(void)
{
    return NULL;
}

const struct board_touch_table board_touch_table = {.count = 0};

const struct board_sound_table board_sound_table = {.count = 0};

static const struct board_button_entry button_entries[] = {{.name = "boot", .pin = 0, .active_low = true}};
const struct board_button_table board_button_table = {.entries = button_entries, .count = 1};

/* What the board has not: the rest of boards.h, returning false, so that the same program
 * links and runs on every board. */
int board_display_count(void)
{
    return 0;
}

bool board_display_init(struct board_display *out)
{
    (void)out;
    return false;
}

bool board_display_init_at(int index, struct board_display *out)
{
    (void)index, (void)out;
    return false;
}

bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy)
{
    (void)display, (void)dir_x, (void)dir_y, (void)swap_xy;
    return false;
}

#if !CONFIG_BOARD_MODULE_CHARACTER_DISPLAY /* a module on the board's bus gives this one instead */
bool board_character_display_init(struct board_character_display *out)
{
    (void)out;
    return false;
}
#endif

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "esp32s3_devkit", .title = "ESP32-S3 DevKit, 16 MB, 8 MB PSRAM", .target = "esp32s3"};
