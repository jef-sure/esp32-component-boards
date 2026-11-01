/*
 * The glue of jc8012p4a1c, made by tools/boards_gen.py from catalog/boards/jc8012p4a1c/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * Every function of boards.h is here: by the data for the parts the board has, returning
 * false for the parts it has not, so the contract of boards.h holds at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "board_display.h"
#include "board_sound_es8311.h"
#include "board_touch.h"
#include "board_touch_gsl3680.h"
#include "bus/dgx_dsi_esp32.h"
#include "driver/i2s_std.h"
#include "drivers/jd9365.h"
#include "esp_log.h"
#include <stdlib.h>
#include <string.h>

/* Guition JC8012P4A1C: 10.1-inch 800x1280 JD9365 on MIPI-DSI (lying 1280x800), GSL3680 touch (firmware written into it at start), ES8311 sound. */

/* The buses of the board. */
static const struct board_i2c_pins board_i2c_pins_of = {.port = I2C_NUM_0, .sda = GPIO_NUM_7, .scl = GPIO_NUM_8}; /* i2c.i2c0 */
static const struct board_i2s_bus board_i2s_i2s0 = {.port = I2S_NUM_0, .mclk = GPIO_NUM_13, .bclk = GPIO_NUM_12, .ws = GPIO_NUM_10, .dout = GPIO_NUM_9, .din = GPIO_NUM_11};

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_table[] = {{"dsi.dsi0", "lane_mbps", 1000}, {"dsi.dsi0", "lanes", 2}, {"dsi.dsi0", "phy_ldo_chan", 3}, {"dsi.dsi0", "phy_ldo_mv", 2500}, {"csi.csi0", "lanes", 2}, {"csi.csi0", "phy_ldo_chan", 3}, {"csi.csi0", "phy_ldo_mv", 2500}, {"i2c.i2c0", "scl", 8}, {"i2c.i2c0", "sda", 7}, {"i2s.i2s0", "bclk", 12}, {"i2s.i2s0", "din", 11}, {"i2s.i2s0", "dout", 9}, {"i2s.i2s0", "mclk", 13}, {"i2s.i2s0", "ws", 10}, {"sdio.sdio0", "clk", 18}, {"sdio.sdio0", "cmd", 19}, {"sdio.sdio0", "d0", 14}, {"sdio.sdio0", "d1", 15}, {"sdio.sdio0", "d2", 16}, {"sdio.sdio0", "d3", 17}, {"sdio.sdio0", "reset", 54}, {"uart.uart0", "rx", 38}, {"uart.uart0", "tx", 37}, {"sdmmc.sdmmc0", "clk", 43}, {"sdmmc.sdmmc0", "cmd", 44}, {"sdmmc.sdmmc0", "d0", 39}, {"sdmmc.sdmmc0", "d1", 40}, {"sdmmc.sdmmc0", "d2", 41}, {"sdmmc.sdmmc0", "d3", 42}, {"led", "data", 26}, {"battery", "in", 52}, {"radio", "io2", 6}, {"clock_32k", "xtal_n", 1}, {"clock_32k", "xtal_p", 0}};

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

/* lcd: a 800x1280 jd9365 on dsi.dsi0. */
static dgx_bus_protocols_t *display0_bus(void)
{
    return dgx_dsi_init(0, 2, 1000, 3, 2500);
}

static dgx_screen_t *display0_screen(dgx_bus_protocols_t *bus)
{
    return dgx_jd9365_init(bus, GPIO_NUM_27, 16, DgxScreenRGB, DgxDsiTwoFrames);
}

static const struct board_display_panel display_panels[] = {
    {.name = "lcd", .glass_w = 800, .glass_h = 1280, .mm_w = 136, .mm_h = 217, .dir_x = DgxScreenRightLeft, .dir_y = DgxScreenTopBottom, .swap_xy = true, .backlight = GPIO_NUM_23, .backlight_on = 1, .bus = display0_bus, .screen = display0_screen, .orientation = dgx_jd9365_orientation},
};
static struct board_display_started displays_started[1];
const struct board_display_table board_display_table = {.panels = display_panels, .started = displays_started, .count = 1};

/* touch: gsl3680 on i2c.i2c0, the calibration of its measured board. */
static const dgx_di_aim_t touch0_aims[] = {{.meant_x = 48, .meant_y = 48, .x = 74, .y = 859}, {.meant_x = 751, .meant_y = 48, .x = 77, .y = 69}, {.meant_x = 48, .meant_y = 1231, .x = 1588, .y = 871}, {.meant_x = 751, .meant_y = 1231, .x = 1591, .y = 81}, {.meant_x = 399, .meant_y = 48, .x = 76, .y = 451}, {.meant_x = 399, .meant_y = 1231, .x = 1590, .y = 463}, {.meant_x = 48, .meant_y = 640, .x = 835, .y = 865}, {.meant_x = 751, .meant_y = 640, .x = 839, .y = 75}, {.meant_x = 399, .meant_y = 640, .x = 837, .y = 457}};
static const struct board_touch_calibration touch0_calibrated = {.aims = touch0_aims, .count = 9, .width = 800, .height = 1280, .blink_ms = 22, .gap_ms = 0, .placeholder = false};
static const struct board_touch_panel touch0_panel = {.x_max = 1664, .y_max = 896, .rst = GPIO_NUM_22, .irq = GPIO_NUM_21, .fingers = 5};
static dgx_di_gsl3680_t touch0_device;

static bool touch0_start(int index, const struct board_display *display, struct board_touch *out)
{
    return board_glue_touch_gsl3680_start(&touch0_device, index, &touch0_panel, &touch0_calibrated, display, out);
}

static const struct board_touch_entry touch_entries[] = {{.name = "touch", .over = "lcd", .start = touch0_start}};
static struct board_touch touches_started[1];
static struct board_touch_slot touch_slots[1];
const struct board_touch_slots board_touch_slots = {.slots = touch_slots, .count = 1};
const struct board_touch_table board_touch_table = {.entries = touch_entries, .started = touches_started, .count = 1};

/* sound: es8311 at 22050 Hz. */
static const struct board_sound_es8311 sound0_codec = {.i2s = &board_i2s_i2s0, .i2c_port = I2C_NUM_0, .address = 0x18, .pa = GPIO_NUM_20,
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
#if !CONFIG_BOARD_MODULE_CHARACTER_DISPLAY /* a module on the board's bus gives this one instead */
bool board_character_display_init(struct board_character_display *out)
{
    (void)out;
    return false;
}
#endif

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "jc8012p4a1c", .title = "Guition JC8012P4A1C", .target = "esp32p4"};
