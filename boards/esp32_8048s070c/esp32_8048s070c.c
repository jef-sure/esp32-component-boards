/*
 * The glue of esp32_8048s070c, made by tools/boards_gen.py from catalog/boards/esp32_8048s070c/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * The data of the board as tables, and the functions of the parts it starts: src/ reads the
 * tables, and what the board has not returns false there, so the contract of boards.h holds
 * at link.
 */
#include "boards.h"
#include "board_glue.h"
/* jef-sure/dgx before 0.11.6: ek9716: no library this component can start it with: none in the catalog */
#if BOARDS_VERSION_JEF_SURE__DGX < BOARDS_VERSION(0, 11, 6)
#error "esp32_8048s070c needs jef-sure/dgx 0.11.6 or later"
#endif

#include "sdkconfig.h"

#include "board_display.h"
#include "board_sound_i2s.h"
#include "board_touch.h"
#include "board_touch_gt911.h"
#include "board_touch_lcd.h"
#include "board_touch_spi.h"
#include "bus/dgx_rgb_esp32.h"
#include "driver/i2s_std.h"
#include "driver/spi_common.h"
#include "drivers/rgb_panel.h"

/* Sunton ESP32-8048S070C: 7-inch 800x480 EK9716 on parallel RGB, GT911 touch, an I2S amplifier; an ESP32-S3 with 16 MB flash and 8 MB octal PSRAM. */

/* The buses of the board. */
static const struct board_spi_bus board_spi_spi2 = {.host = SPI2_HOST, .mosi = GPIO_NUM_11, .miso = GPIO_NUM_13, .sclk = GPIO_NUM_12};
static const struct board_i2c_pins board_i2c_buses[] = {
    {.port = I2C_NUM_0, .sda = GPIO_NUM_19, .scl = GPIO_NUM_20}, /* i2c.i2c0 */
};
static const struct board_i2s_bus board_i2s_i2s0 = {.port = I2S_NUM_0, .mclk = GPIO_NUM_NC, .bclk = GPIO_NUM_0, .ws = GPIO_NUM_18, .dout = GPIO_NUM_17, .din = GPIO_NUM_NC};

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_fields[] = {{"rgb.rgb0", "data0", 15}, {"rgb.rgb0", "data1", 7}, {"rgb.rgb0", "data2", 6}, {"rgb.rgb0", "data3", 5}, {"rgb.rgb0", "data4", 4}, {"rgb.rgb0", "data5", 9}, {"rgb.rgb0", "data6", 46}, {"rgb.rgb0", "data7", 3}, {"rgb.rgb0", "data8", 8}, {"rgb.rgb0", "data9", 16}, {"rgb.rgb0", "data10", 1}, {"rgb.rgb0", "data11", 14}, {"rgb.rgb0", "data12", 21}, {"rgb.rgb0", "data13", 47}, {"rgb.rgb0", "data14", 48}, {"rgb.rgb0", "data15", 45}, {"rgb.rgb0", "de", 41}, {"rgb.rgb0", "hsync", 39}, {"rgb.rgb0", "hz", 33000000}, {"rgb.rgb0", "pclk", 42}, {"rgb.rgb0", "vsync", 40}, {"i2c.i2c0", "scl", 20}, {"i2c.i2c0", "sda", 19}, {"i2s.i2s0", "bclk", 0}, {"i2s.i2s0", "dout", 17}, {"i2s.i2s0", "ws", 18}, {"spi.spi2", "miso", 13}, {"spi.spi2", "mosi", 11}, {"spi.spi2", "sclk", 12}, {"sd", "cs", 10}, {"sd", "host", SPI2_HOST}};
const struct board_bus_table board_bus_table = {.fields = board_bus_fields, .count = sizeof(board_bus_fields) / sizeof(board_bus_fields[0])};

/* The SPI buses open to the program's devices. A host with only a display on it is not one of them. */
static const struct board_spi_bus *const board_spi_buses[] = {&board_spi_spi2};
/* The hosts the board's buses claim, SPI and QSPI alike: spi2. */
static const int board_spi_hosts[] = {SPI2_HOST};
const struct board_spi_table board_spi_table = {.buses = board_spi_buses, .count = sizeof(board_spi_buses) / sizeof(board_spi_buses[0]), .taken = board_spi_hosts, .taken_count = sizeof(board_spi_hosts) / sizeof(board_spi_hosts[0])};

/* The board's I2C buses by port: board_glue_i2c makes the master of one at the first ask. */
const struct board_i2c_table board_i2c_table = {.buses = board_i2c_buses, .count = sizeof(board_i2c_buses) / sizeof(board_i2c_buses[0])};

/* lcd: a 800x480 ek9716 on rgb.rgb0. */
static const dgx_rgb_pins_t display0_pins = {.pclk = GPIO_NUM_42, .hsync = GPIO_NUM_39, .vsync = GPIO_NUM_40, .de = GPIO_NUM_41, .disp = GPIO_NUM_NC, .data = {GPIO_NUM_15, GPIO_NUM_7, GPIO_NUM_6, GPIO_NUM_5, GPIO_NUM_4, GPIO_NUM_9, GPIO_NUM_46, GPIO_NUM_3, GPIO_NUM_8, GPIO_NUM_16, GPIO_NUM_1, GPIO_NUM_14, GPIO_NUM_21, GPIO_NUM_47, GPIO_NUM_48, GPIO_NUM_45}};
static dgx_bus_protocols_t *display0_bus(void)
{
    return dgx_rgb_init(&display0_pins, 33000000);
}

static dgx_screen_t *display0_screen(dgx_bus_protocols_t *bus)
{
    return dgx_rgb_panel_init(bus, &dgx_rgb_panel_jc8048b070n, GPIO_NUM_NC, GPIO_NUM_2, 16, DgxScreenRGB, DgxRgbTwoFrames);
}

static const struct board_display_panel display_panels[] = {
    {.name = "lcd", .glass_w = 800, .glass_h = 480, .mm_w = 154, .mm_h = 86, .dir_x = DgxScreenLeftRight, .dir_y = DgxScreenTopBottom, .swap_xy = false, .backlight = GPIO_NUM_NC, .backlight_on = 1, .bus = display0_bus, .screen = display0_screen, .orientation = board_glue_screen_orientation},
};
static struct board_display_started displays_started[1];
const struct board_display_table board_display_table = {.panels = display_panels, .started = displays_started, .count = 1};

/* touch: gt911 on i2c.i2c0, the calibration of its measured board. */
/* The calibration below is a placeholder, not measured on a board: the touch works, only not
 * straight; board_touch_start says so. Measure the board (dgx_di_calibrate_measure) and put the
 * numbers in the data. */
static const dgx_di_aim_t touch0_aims[] = {{.meant_x = 48, .meant_y = 48, .x = 48, .y = 48}, {.meant_x = 751, .meant_y = 48, .x = 751, .y = 48}, {.meant_x = 48, .meant_y = 431, .x = 48, .y = 431}, {.meant_x = 751, .meant_y = 431, .x = 751, .y = 431}};
static const struct board_touch_calibration touch0_calibrated = {.aims = touch0_aims, .count = 4, .width = 800, .height = 480, .blink_ms = 0, .gap_ms = 0, .placeholder = true};
static const struct board_touch_panel touch0_panel = {.x_max = 800, .y_max = 480, .rst = GPIO_NUM_38, .irq = GPIO_NUM_NC, .i2c_port = I2C_NUM_0, .fingers = 5};
static dgx_di_esp_lcd_touch_t touch0_device;
static const uint8_t touch0_addresses[] = {0x5d, 0x14};
static const struct board_touch_gt911 touch0_driver = {.panel = &touch0_panel, .calibrated = &touch0_calibrated, .device = &touch0_device, .addresses = touch0_addresses, .address_count = 2, .i2c_hz = 400000};

static const struct board_touch_entry touch_entries[] = {{.name = "touch", .over = "lcd", .start = board_glue_touch_gt911_start, .gt911 = &touch0_driver}};
static struct board_touch touches_started[1];
static struct board_touch_slot touch_slots[1];
const struct board_touch_slots board_touch_slots = {.slots = touch_slots, .count = 1};
const struct board_touch_table board_touch_table = {.entries = touch_entries, .started = touches_started, .count = 1};

/* sound: i2s at 22050 Hz. */

static const struct board_sound_entry sound_entries[] = {{.name = "sound", .rate = 22050, .init = board_glue_sound_i2s_init, .i2s = &board_i2s_i2s0}};
static struct board_sound_stream sound_streams[1];
const struct board_sound_table board_sound_table = {.entries = sound_entries, .streams = sound_streams, .count = 1};

static const struct board_button_entry button_entries[] = {{.name = "boot", .pin = 0, .active_low = true}};
const struct board_button_table board_button_table = {.entries = button_entries, .count = 1};

const struct board_radio_table board_radio_table = {.count = 0};

const struct board_ethernet_table board_ethernet_table = {.count = 0};

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "esp32_8048s070c", .title = "Sunton ESP32-8048S070C", .target = "esp32s3"};
