/*
 * The glue of esp32_c6_supermini, made by tools/boards_gen.py from catalog/boards/esp32_c6_supermini/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * The data of the board as tables, and the functions of the parts it starts: src/ reads the
 * tables, and what the board has not returns false there, so the contract of boards.h holds
 * at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"


/* ESP32-C6 Super Mini: A small ESP32-C6 board: 4 MB flash in the chip, USB-C to the chip, a blue LED and a WS2812, BOOT and RST buttons, a TP4054 charger for a cell on pads, a ceramic antenna. */

/* The buses of the board. */

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_fields[] = {{"usb", "d_minus", 12}, {"usb", "d_plus", 13}, {"led", "out", 15}, {"rgb", "data", 8}};
const struct board_bus_table board_bus_table = {.fields = board_bus_fields, .count = sizeof(board_bus_fields) / sizeof(board_bus_fields[0])};

const struct board_spi_table board_spi_table = {.count = 0};

/* The board wires no I2C bus: nothing for board_glue_i2c to make. */
const struct board_i2c_table board_i2c_table = {.count = 0};

const struct board_touch_table board_touch_table = {.count = 0};

const struct board_sound_table board_sound_table = {.count = 0};

static const struct board_button_entry button_entries[] = {{.name = "boot", .pin = 9, .active_low = true}};
const struct board_button_table board_button_table = {.entries = button_entries, .count = 1};

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "esp32_c6_supermini", .title = "ESP32-C6 Super Mini", .target = "esp32c6"};
