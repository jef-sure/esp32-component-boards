/*
 * The glue of esp32s3_devkit, made by tools/boards_gen.py from catalog/boards/esp32s3_devkit/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * The data of the board as tables, and the functions of the parts it starts: src/ reads the
 * tables, and what the board has not returns false there, so the contract of boards.h holds
 * at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"


/* ESP32-S3 DevKit, 16 MB, 8 MB PSRAM: A standard ESP32-S3 dev board with two USB-C ports, a CH343 USB bridge on one of them, an RGB LED and a BOOT button. */

/* The buses of the board. */

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_fields[] = {{"uart.uart0", "rx", 44}, {"uart.uart0", "tx", 43}, {"led", "data", 48}, {"usb_serial", "port", 0}};
const struct board_bus_table board_bus_table = {.fields = board_bus_fields, .count = sizeof(board_bus_fields) / sizeof(board_bus_fields[0])};

const struct board_spi_table board_spi_table = {.count = 0};

/* The board wires no I2C bus: nothing for board_glue_i2c to make. */
const struct board_i2c_table board_i2c_table = {.count = 0};

const struct board_touch_table board_touch_table = {.count = 0};

const struct board_sound_table board_sound_table = {.count = 0};

static const struct board_button_entry button_entries[] = {{.name = "boot", .pin = 0, .active_low = true}};
const struct board_button_table board_button_table = {.entries = button_entries, .count = 1};

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "esp32s3_devkit", .title = "ESP32-S3 DevKit, 16 MB, 8 MB PSRAM", .target = "esp32s3"};
