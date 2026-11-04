/*
 * The glue of esp32_p4_poe_eth, made by tools/boards_gen.py from catalog/boards/esp32_p4_poe_eth/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * The data of the board as tables, and the functions of the parts it starts: src/ reads the
 * tables, and what the board has not returns false there, so the contract of boards.h holds
 * at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "board_sound_es8311.h"
#include "driver/i2s_std.h"

/* Waveshare ESP32-P4-POE-ETH: The ESP32-P4-ETH sold with a PoE module on its header H7. */

/* The buses of the board. */
static const struct board_i2c_pins board_i2c_buses[] = {
    {.port = I2C_NUM_0, .sda = GPIO_NUM_7, .scl = GPIO_NUM_8}, /* i2c.i2c0 */
};
static const struct board_i2s_bus board_i2s_i2s0 = {.port = I2S_NUM_0, .mclk = GPIO_NUM_13, .bclk = GPIO_NUM_12, .ws = GPIO_NUM_10, .dout = GPIO_NUM_9, .din = GPIO_NUM_11};

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_fields[] = {{"dsi.dsi0", "lanes", 2}, {"csi.csi0", "lanes", 2}, {"i2c.i2c0", "scl", 8}, {"i2c.i2c0", "sda", 7}, {"i2s.i2s0", "bclk", 12}, {"i2s.i2s0", "din", 11}, {"i2s.i2s0", "dout", 9}, {"i2s.i2s0", "mclk", 13}, {"i2s.i2s0", "ws", 10}, {"rmii.rmii0", "crs_dv", 28}, {"rmii.rmii0", "mdc", 31}, {"rmii.rmii0", "mdio", 52}, {"rmii.rmii0", "ref_clk", 50}, {"rmii.rmii0", "rxd0", 29}, {"rmii.rmii0", "rxd1", 30}, {"rmii.rmii0", "txd0", 34}, {"rmii.rmii0", "txd1", 35}, {"rmii.rmii0", "txen", 49}, {"uart.uart0", "rx", 38}, {"uart.uart0", "tx", 37}, {"sdmmc.sdmmc0", "clk", 43}, {"sdmmc.sdmmc0", "cmd", 44}, {"sdmmc.sdmmc0", "d0", 39}, {"sdmmc.sdmmc0", "d1", 40}, {"sdmmc.sdmmc0", "d2", 41}, {"sdmmc.sdmmc0", "d3", 42}, {"ethernet", "rst", 51}, {"usb_serial", "port", 0}, {"xtal_32k", "xi", 1}, {"xtal_32k", "xo", 0}};
const struct board_bus_table board_bus_table = {.fields = board_bus_fields, .count = sizeof(board_bus_fields) / sizeof(board_bus_fields[0])};

const struct board_spi_table board_spi_table = {.count = 0};

/* The board's I2C buses by port: board_glue_i2c makes the master of one at the first ask. */
const struct board_i2c_table board_i2c_table = {.buses = board_i2c_buses, .count = sizeof(board_i2c_buses) / sizeof(board_i2c_buses[0])};

const struct board_touch_table board_touch_table = {.count = 0};

/* sound: es8311 at 22050 Hz. */
static const struct board_sound_es8311 sound0_es8311 = {.i2s = &board_i2s_i2s0, .i2c_port = I2C_NUM_0, .address = 0x18, .pa = GPIO_NUM_53,
                                                      .pa_voltage = 5.0f, .codec_dac_voltage = 3.3f, .volume = 25};

static const struct board_sound_entry sound_entries[] = {{.name = "sound", .rate = 22050, .init = board_glue_sound_es8311_init, .es8311 = &sound0_es8311}};
static struct board_sound_stream sound_streams[1];
const struct board_sound_table board_sound_table = {.entries = sound_entries, .streams = sound_streams, .count = 1};

static const struct board_button_entry button_entries[] = {{.name = "boot", .pin = 35, .active_low = true}};
const struct board_button_table board_button_table = {.entries = button_entries, .count = 1};

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "esp32_p4_poe_eth", .title = "Waveshare ESP32-P4-POE-ETH", .target = "esp32p4"};
