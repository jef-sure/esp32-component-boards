/*
 * The glue of jc3248w535, made by tools/boards_gen.py from catalog/boards/jc3248w535/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * The data of the board as tables, and the functions of the parts it starts: src/ reads the
 * tables, and what the board has not returns false there, so the contract of boards.h holds
 * at link.
 */
#include "boards.h"
#include "board_glue.h"
/* jef-sure/dgx before 0.12.7: catalog/boards/jc3248w535/board.json: lcd: its chip has no such library, or not in that version: lcd:esp-idf/jef-sure/dgx */
#if BOARDS_VERSION_JEF_SURE__DGX < BOARDS_VERSION(0, 12, 7)
#error "jc3248w535 needs jef-sure/dgx 0.12.7 or later"
#endif

#include "sdkconfig.h"

#include "board_display.h"
#include "board_sound_i2s.h"
#include "board_touch.h"
#include "board_touch_i2c.h"
#include "board_touch_lcd.h"
#include "board_touch_spi.h"
#include "bus/dgx_qspi_esp32.h"
#include "driver/i2s_std.h"
#include "driver/spi_common.h"
#include "drivers/axs15231b.h"
#include "esp_lcd_axs15231b.h"

/* Guition JC3248W535: 3.5-inch 320x480 AXS15231B on QSPI, its touch in the same chip on I2C; an ESP32-S3 with 16 MB flash and 8 MB octal PSRAM. */

/* The buses of the board. */
static const struct board_spi_bus board_spi_spi3 = {.host = SPI3_HOST, .mosi = GPIO_NUM_11, .miso = GPIO_NUM_13, .sclk = GPIO_NUM_12};
static const struct board_i2c_pins board_i2c_buses[] = {
    {.port = I2C_NUM_0, .sda = GPIO_NUM_4, .scl = GPIO_NUM_8}, /* i2c.i2c0 */
};
static const struct board_i2s_bus board_i2s_i2s0 = {.port = I2S_NUM_0, .mclk = GPIO_NUM_NC, .bclk = GPIO_NUM_42, .ws = GPIO_NUM_2, .dout = GPIO_NUM_41, .din = GPIO_NUM_NC};

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_fields[] = {{"spi.spi3", "miso", 13}, {"spi.spi3", "mosi", 11}, {"spi.spi3", "sclk", 12}, {"i2s.i2s0", "bclk", 42}, {"i2s.i2s0", "dout", 41}, {"i2s.i2s0", "ws", 2}, {"qspi.spi2", "d0", 21}, {"qspi.spi2", "d1", 48}, {"qspi.spi2", "d2", 40}, {"qspi.spi2", "d3", 39}, {"qspi.spi2", "hz", 40000000}, {"qspi.spi2", "sclk", 47}, {"i2c.i2c0", "scl", 8}, {"i2c.i2c0", "sda", 4}, {"battery", "in", 5}, {"sd", "cs", 10}, {"sd", "host", SPI3_HOST}};
const struct board_bus_table board_bus_table = {.fields = board_bus_fields, .count = sizeof(board_bus_fields) / sizeof(board_bus_fields[0])};

/* The SPI buses open to the program's devices. A host with only a display on it is not one of them. */
static const struct board_spi_bus *const board_spi_buses[] = {&board_spi_spi3};
/* The hosts the board's buses claim, SPI and QSPI alike: spi2, spi3. */
static const int board_spi_hosts[] = {SPI2_HOST, SPI3_HOST};
const struct board_spi_table board_spi_table = {.buses = board_spi_buses, .count = sizeof(board_spi_buses) / sizeof(board_spi_buses[0]), .taken = board_spi_hosts, .taken_count = sizeof(board_spi_hosts) / sizeof(board_spi_hosts[0])};

/* The board's I2C buses by port: board_glue_i2c makes the master of one at the first ask. */
const struct board_i2c_table board_i2c_table = {.buses = board_i2c_buses, .count = sizeof(board_i2c_buses) / sizeof(board_i2c_buses[0])};

/* lcd: a 320x480 axs15231b on qspi.spi2. */
static dgx_bus_protocols_t *display0_bus(void)
{
    return dgx_qspi_init(SPI2_HOST, SPI_DMA_CH_AUTO, GPIO_NUM_21, GPIO_NUM_48, GPIO_NUM_40, GPIO_NUM_39, GPIO_NUM_47, GPIO_NUM_45, 40000000, 0);
}

static dgx_screen_t *display0_screen(dgx_bus_protocols_t *bus)
{
    return dgx_axs15231b_init(bus, GPIO_NUM_NC, GPIO_NUM_1, 16, DgxScreenRGB, DGX_AXS15231B_320X480);
}

static const struct board_display_panel display_panels[] = {
    {.name = "lcd", .glass_w = 320, .glass_h = 480, .mm_w = 49, .mm_h = 73, .dir_x = DgxScreenLeftRight, .dir_y = DgxScreenTopBottom, .swap_xy = false, .backlight = GPIO_NUM_NC, .backlight_on = 1, .bus = display0_bus, .screen = display0_screen, .orientation = board_glue_screen_orientation},
};
static struct board_display_started displays_started[1];
const struct board_display_table board_display_table = {.panels = display_panels, .started = displays_started, .count = 1};

/* touch: espressif/esp_lcd_axs15231b on i2c.i2c0, the calibration of its measured board. */
static const dgx_di_aim_t touch0_aims[] = {{.meant_x = 40, .meant_y = 40, .x = 56, .y = 24}, {.meant_x = 279, .meant_y = 40, .x = 288, .y = 32}, {.meant_x = 40, .meant_y = 439, .x = 34, .y = 456}, {.meant_x = 279, .meant_y = 439, .x = 295, .y = 458}, {.meant_x = 160, .meant_y = 40, .x = 170, .y = 17}, {.meant_x = 160, .meant_y = 439, .x = 171, .y = 455}, {.meant_x = 40, .meant_y = 240, .x = 46, .y = 246}, {.meant_x = 279, .meant_y = 240, .x = 296, .y = 246}, {.meant_x = 160, .meant_y = 240, .x = 166, .y = 251}};
static const struct board_touch_calibration touch0_calibrated = {.aims = touch0_aims, .count = 9, .width = 320, .height = 480, .blink_ms = 0, .gap_ms = 0, .placeholder = false};
static const struct board_touch_panel touch0_panel = {.x_max = 320, .y_max = 480, .rst = GPIO_NUM_NC, .irq = GPIO_NUM_3, .i2c_port = I2C_NUM_0, .fingers = 1, .reports_hz = 60};
static dgx_di_esp_lcd_touch_t touch0_device;
static const struct board_touch_i2c touch0_driver = {.panel = &touch0_panel, .calibrated = &touch0_calibrated, .device = &touch0_device, .io = ESP_LCD_TOUCH_IO_I2C_AXS15231B_CONFIG(), .address = 0x3b, .hz = 400000, .create = esp_lcd_touch_new_i2c_axs15231b};

static const struct board_touch_entry touch_entries[] = {{.name = "touch", .over = "lcd", .start = board_glue_touch_i2c_start, .esp_lcd_touch_i2c = &touch0_driver}};
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
const struct board_data board_data = {.name = "jc3248w535", .title = "Guition JC3248W535", .target = "esp32s3"};
