/*
 * The glue of esp32_wrover_dev, made by tools/boards_gen.py from catalog/boards/esp32_wrover_dev/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * The data of the board as tables, and the functions of the parts it starts: src/ reads the
 * tables, and what the board has not returns false there, so the contract of boards.h holds
 * at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"


/* ESP32-WROVER-DEV: An ESP32-WROVER-E board with 8 MB PSRAM and a connector for a camera, sold with an OV2640: a CH340 USB bridge on micro-USB, a blue LED on GPIO 2, EN and BOOT buttons. */

/* The buses of the board. */
static const struct board_i2c_pins board_i2c_buses[] = {
    {.port = I2C_NUM_0, .sda = GPIO_NUM_26, .scl = GPIO_NUM_27}, /* i2c.i2c0 */
};

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_fields[] = {{"dvp.dvp0", "data0", 4}, {"dvp.dvp0", "data1", 5}, {"dvp.dvp0", "data2", 18}, {"dvp.dvp0", "data3", 19}, {"dvp.dvp0", "data4", 36}, {"dvp.dvp0", "data5", 39}, {"dvp.dvp0", "data6", 34}, {"dvp.dvp0", "data7", 35}, {"dvp.dvp0", "de", 23}, {"dvp.dvp0", "pclk", 22}, {"dvp.dvp0", "vsync", 25}, {"i2c.i2c0", "scl", 27}, {"i2c.i2c0", "sda", 26}, {"led", "out", 2}, {"camera_sensor", "address", 48}, {"camera_sensor", "port", 0}, {"camera_sensor", "xclk", 21}};
const struct board_bus_table board_bus_table = {.fields = board_bus_fields, .count = sizeof(board_bus_fields) / sizeof(board_bus_fields[0])};

const struct board_spi_table board_spi_table = {.count = 0};

/* The board's I2C buses by port: board_glue_i2c makes the master of one at the first ask. */
const struct board_i2c_table board_i2c_table = {.buses = board_i2c_buses, .count = sizeof(board_i2c_buses) / sizeof(board_i2c_buses[0])};

const struct board_touch_table board_touch_table = {.count = 0};

const struct board_sound_table board_sound_table = {.count = 0};

static const struct board_button_entry button_entries[] = {{.name = "boot", .pin = 0, .active_low = true}};
const struct board_button_table board_button_table = {.entries = button_entries, .count = 1};

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "esp32_wrover_dev", .title = "ESP32-WROVER-DEV", .target = "esp32"};
