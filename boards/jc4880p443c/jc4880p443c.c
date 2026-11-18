/*
 * The glue of jc4880p443c, made by tools/boards_gen.py from catalog/boards/jc4880p443c/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * The data of the board as tables, and the functions of the parts it starts: src/ reads the
 * tables, and what the board has not returns false there, so the contract of boards.h holds
 * at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "board_radio_esp_hosted.h"
#include "board_sound_es8311.h"
#include "driver/i2s_std.h"

/* Guition JC4880P443C: 4.3-inch 480x800 ST7701S on MIPI-DSI, GT911 touch, ES8311 sound: an ESP32-P4 with Wi-Fi and BLE in an ESP32-C6 on the same module. */

/* The buses of the board. */
static const struct board_i2c_pins board_i2c_buses[] = {
    {.port = I2C_NUM_0, .sda = GPIO_NUM_7, .scl = GPIO_NUM_8}, /* i2c.i2c0 */
};
static const struct board_i2s_bus board_i2s_i2s0 = {.port = I2S_NUM_0, .mclk = GPIO_NUM_13, .bclk = GPIO_NUM_12, .ws = GPIO_NUM_10, .dout = GPIO_NUM_9, .din = GPIO_NUM_48};

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_fields[] = {{"dsi.dsi0", "lane_mbps", 1000}, {"dsi.dsi0", "lanes", 2}, {"dsi.dsi0", "phy_ldo_chan", 3}, {"dsi.dsi0", "phy_ldo_mv", 2500}, {"csi.csi0", "lanes", 2}, {"csi.csi0", "phy_ldo_chan", 3}, {"csi.csi0", "phy_ldo_mv", 2500}, {"i2c.i2c0", "scl", 8}, {"i2c.i2c0", "sda", 7}, {"i2s.i2s0", "bclk", 12}, {"i2s.i2s0", "din", 48}, {"i2s.i2s0", "dout", 9}, {"i2s.i2s0", "mclk", 13}, {"i2s.i2s0", "ws", 10}, {"sdio.sdio0", "clk", 18}, {"sdio.sdio0", "cmd", 19}, {"sdio.sdio0", "d0", 14}, {"sdio.sdio0", "d1", 15}, {"sdio.sdio0", "d2", 16}, {"sdio.sdio0", "d3", 17}, {"sdio.sdio0", "reset", 54}, {"uart.uart0", "rx", 38}, {"uart.uart0", "tx", 37}, {"uart.uart1", "rx", 27}, {"uart.uart1", "tx", 26}, {"sdmmc.sdmmc0", "clk", 43}, {"sdmmc.sdmmc0", "cmd", 44}, {"sdmmc.sdmmc0", "d0", 39}, {"sdmmc.sdmmc0", "d1", 40}, {"sdmmc.sdmmc0", "d2", 41}, {"sdmmc.sdmmc0", "d3", 42}, {"lcd", "backlight", 23}, {"lcd", "rst", 5}, {"rs485", "port", 1}, {"battery", "in", 53}, {"touch", "int", 21}, {"touch", "port", 0}, {"touch", "rst", 22}};
const struct board_bus_table board_bus_table = {.fields = board_bus_fields, .count = sizeof(board_bus_fields) / sizeof(board_bus_fields[0])};

const struct board_spi_table board_spi_table = {.count = 0};

/* The board's I2C buses by port: board_glue_i2c makes the master of one at the first ask. */
const struct board_i2c_table board_i2c_table = {.buses = board_i2c_buses, .count = sizeof(board_i2c_buses) / sizeof(board_i2c_buses[0])};

const struct board_touch_table board_touch_table = {.count = 0};

/* sound: es8311 at 22050 Hz. */
static const struct board_sound_es8311 sound0_es8311 = {.i2s = &board_i2s_i2s0, .i2c_port = I2C_NUM_0, .address = 0x18, .pa = GPIO_NUM_11,
                                                      .pa_voltage = 5.0f, .codec_dac_voltage = 3.3f, .volume = 25};

static const struct board_sound_entry sound_entries[] = {{.name = "sound", .rate = 22050, .init = board_glue_sound_es8311_init, .es8311 = &sound0_es8311}};
static struct board_sound_stream sound_streams[1];
const struct board_sound_table board_sound_table = {.entries = sound_entries, .streams = sound_streams, .count = 1};

static const struct board_button_entry button_entries[] = {{.name = "boot", .pin = 35, .active_low = true}};
const struct board_button_table board_button_table = {.entries = button_entries, .count = 1};

/* radio: an esp32c6 on sdio, by esp-idf/espressif/esp_hosted. The flash step of the component keeps its firmware at the version of the build. */
static const struct board_radio_entry radio_entries[] = {{.name = "radio", .update = true, .start = board_glue_radio_esp_hosted_start}};
const struct board_radio_table board_radio_table = {.entries = radio_entries, .count = 1};

const struct board_ethernet_table board_ethernet_table = {.count = 0};

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "jc4880p443c", .title = "Guition JC4880P443C", .target = "esp32p4"};
