/*
 * The glue of esp32_p4_eth, made by tools/boards_gen.py from catalog/boards/esp32_p4_eth/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * Every function of boards.h is here: by the data for the parts the board has, returning
 * false for the parts it has not, so the contract of boards.h holds at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "board_sound_es8311.h"
#include "driver/i2s_std.h"
#include "esp_log.h"
#include <stdlib.h>
#include <string.h>

/* Waveshare ESP32-P4-ETH: An ESP32-P4 with 100 Mbit Ethernet on an IP101, an ES8311 with a microphone and a speaker output, a microSD slot, MIPI CSI and DSI connectors, a 40-pin header in the layout of a Pico. No radio.. */

/* The buses of the board. */
static const struct board_i2c_pins board_i2c_pins_of = {.port = I2C_NUM_0, .sda = GPIO_NUM_7, .scl = GPIO_NUM_8}; /* i2c.i2c0 */
static const struct board_i2s_bus board_i2s_i2s0 = {.port = I2S_NUM_0, .mclk = GPIO_NUM_13, .bclk = GPIO_NUM_12, .ws = GPIO_NUM_10, .dout = GPIO_NUM_9, .din = GPIO_NUM_11};

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_table[] = {{"csi.csi0", "lanes", 2}, {"i2c.i2c0", "scl", 8}, {"i2c.i2c0", "sda", 7}, {"i2s.i2s0", "bclk", 12}, {"i2s.i2s0", "din", 11}, {"i2s.i2s0", "dout", 9}, {"i2s.i2s0", "mclk", 13}, {"i2s.i2s0", "ws", 10}, {"rmii.rmii0", "crs_dv", 28}, {"rmii.rmii0", "mdc", 31}, {"rmii.rmii0", "mdio", 52}, {"rmii.rmii0", "ref_clk", 50}, {"rmii.rmii0", "rxd0", 29}, {"rmii.rmii0", "rxd1", 30}, {"rmii.rmii0", "txd0", 34}, {"rmii.rmii0", "txd1", 35}, {"rmii.rmii0", "txen", 49}, {"uart.uart0", "rx", 38}, {"uart.uart0", "tx", 37}, {"sdmmc.sdmmc0", "clk", 43}, {"sdmmc.sdmmc0", "cmd", 44}, {"sdmmc.sdmmc0", "d0", 39}, {"sdmmc.sdmmc0", "d1", 40}, {"sdmmc.sdmmc0", "d2", 41}, {"sdmmc.sdmmc0", "d3", 42}, {"ethernet", "rst", 51}};

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

/* The board's I2C: one master, made by whoever asks first (board_glue_i2c). */
const struct board_i2c_pins *board_i2c_pins(void)
{
    return &board_i2c_pins_of;
}

const struct board_touch_table board_touch_table = {.count = 0};

/* sound: es8311 at 22050 Hz. */
static const struct board_sound_es8311 sound0_codec = {.i2s = &board_i2s_i2s0, .i2c_port = I2C_NUM_0, .address = 0x18, .pa = GPIO_NUM_53,
                                                     .pa_voltage = 5.0f, .codec_dac_voltage = 3.3f, .volume = 25, .rate = 22050};

static bool sound0_start(int index, board_sound_source_t source)
{
    return board_glue_sound_es8311_start(index, &sound0_codec, source);
}

static const struct board_sound_entry sound_entries[] = {{.name = "sound", .rate = 22050, .start = sound0_start}};
static struct board_sound_stream sound_streams[1];
const struct board_sound_table board_sound_table = {.entries = sound_entries, .streams = sound_streams, .count = 1};

static const struct board_button_entry button_entries[] = {{.name = "boot", .pin = 35, .active_low = true}};
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
const struct board_data board_data = {.name = "esp32_p4_eth", .title = "Waveshare ESP32-P4-ETH", .target = "esp32p4"};
