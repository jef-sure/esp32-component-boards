/*
 * The glue of jc4827w543c, made by tools/boards_gen.py from catalog/boards/jc4827w543c/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * The data of the board as tables, and the functions of the parts it starts: src/ reads the
 * tables, and what the board has not returns false there, so the contract of boards.h holds
 * at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "board_display.h"
#include "board_sound_i2s.h"
#include "board_touch.h"
#include "board_touch_gt911.h"
#include "board_touch_lcd.h"
#include "board_touch_spi.h"
#include "bus/dgx_qspi_esp32.h"
#include "driver/i2s_std.h"
#include "driver/spi_common.h"
#include "drivers/nv3041a.h"

/* Guition JC4827W543C: 4.3-inch 480x272 NV3041A on QSPI, GT911 touch on its own I2C; an ESP32-S3 with 8 MB octal PSRAM. */

/* The buses of the board. */
static const struct board_spi_bus board_spi_spi3 = {.host = SPI3_HOST, .mosi = GPIO_NUM_11, .miso = GPIO_NUM_13, .sclk = GPIO_NUM_12};
static const struct board_i2c_pins board_i2c_buses[] = {
    {.port = I2C_NUM_0, .sda = GPIO_NUM_8, .scl = GPIO_NUM_4}, /* i2c.i2c0 */
};
static const struct board_i2s_bus board_i2s_i2s0 = {.port = I2S_NUM_0, .mclk = GPIO_NUM_NC, .bclk = GPIO_NUM_42, .ws = GPIO_NUM_2, .dout = GPIO_NUM_41, .din = GPIO_NUM_NC};

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_fields[] = {{"spi.spi3", "miso", 13}, {"spi.spi3", "mosi", 11}, {"spi.spi3", "sclk", 12}, {"i2s.i2s0", "bclk", 42}, {"i2s.i2s0", "dout", 41}, {"i2s.i2s0", "ws", 2}, {"qspi.spi2", "d0", 21}, {"qspi.spi2", "d1", 48}, {"qspi.spi2", "d2", 40}, {"qspi.spi2", "d3", 39}, {"qspi.spi2", "hz", 40000000}, {"qspi.spi2", "sclk", 47}, {"i2c.i2c0", "scl", 4}, {"i2c.i2c0", "sda", 8}, {"battery", "in", 5}, {"sd", "cs", 10}, {"sd", "host", SPI3_HOST}};
const struct board_bus_table board_bus_table = {.fields = board_bus_fields, .count = sizeof(board_bus_fields) / sizeof(board_bus_fields[0])};

/* The SPI buses open to the program's devices. A host with only a display on it is not one of them. */
static const struct board_spi_bus *const board_spi_buses[] = {&board_spi_spi3};
/* The hosts the board's buses claim, SPI and QSPI alike: spi2, spi3. */
static const int board_spi_hosts[] = {SPI2_HOST, SPI3_HOST};
const struct board_spi_table board_spi_table = {.buses = board_spi_buses, .count = sizeof(board_spi_buses) / sizeof(board_spi_buses[0]), .taken = board_spi_hosts, .taken_count = sizeof(board_spi_hosts) / sizeof(board_spi_hosts[0])};

/* The board's I2C buses by port: board_glue_i2c makes the master of one at the first ask. */
const struct board_i2c_table board_i2c_table = {.buses = board_i2c_buses, .count = sizeof(board_i2c_buses) / sizeof(board_i2c_buses[0])};

/* lcd: a 480x272 nv3041a on qspi.spi2. */
static dgx_bus_protocols_t *display0_bus(void)
{
    return dgx_qspi_init(SPI2_HOST, SPI_DMA_CH_AUTO, GPIO_NUM_21, GPIO_NUM_48, GPIO_NUM_40, GPIO_NUM_39, GPIO_NUM_47, GPIO_NUM_45, 40000000, 0);
}

static dgx_screen_t *display0_screen(dgx_bus_protocols_t *bus)
{
    return dgx_nv3041a_init(bus, GPIO_NUM_NC, GPIO_NUM_1, 16, DgxScreenRGB);
}

static const struct board_display_panel display_panels[] = {
    {.name = "lcd", .glass_w = 480, .glass_h = 272, .mm_w = 95, .mm_h = 54, .dir_x = DgxScreenLeftRight, .dir_y = DgxScreenTopBottom, .swap_xy = false, .backlight = GPIO_NUM_NC, .backlight_on = 1, .bus = display0_bus, .screen = display0_screen, .orientation = dgx_nv3041a_orientation},
};
static struct board_display_started displays_started[1];
const struct board_display_table board_display_table = {.panels = display_panels, .started = displays_started, .count = 1};

/* touch: gt911 on i2c.i2c0, the calibration of its measured board. */
static const dgx_di_aim_t touch0_aims[] = {{.meant_x = 34, .meant_y = 33, .x = 39, .y = 37}, {.meant_x = 445, .meant_y = 33, .x = 446, .y = 42}, {.meant_x = 34, .meant_y = 236, .x = 38, .y = 234}, {.meant_x = 445, .meant_y = 236, .x = 445, .y = 240}, {.meant_x = 241, .meant_y = 33, .x = 243, .y = 39}, {.meant_x = 241, .meant_y = 236, .x = 242, .y = 237}, {.meant_x = 34, .meant_y = 137, .x = 38, .y = 136}, {.meant_x = 445, .meant_y = 137, .x = 445, .y = 141}, {.meant_x = 241, .meant_y = 137, .x = 242, .y = 139}};
static const struct board_touch_calibration touch0_calibrated = {.aims = touch0_aims, .count = 9, .width = 480, .height = 272, .blink_ms = 0, .gap_ms = 0, .placeholder = false};
static const struct board_touch_panel touch0_panel = {.x_max = 480, .y_max = 272, .rst = GPIO_NUM_38, .irq = GPIO_NUM_3, .i2c_port = I2C_NUM_0, .fingers = 5};
static dgx_di_esp_lcd_touch_t touch0_device;
static const uint8_t touch0_addresses[] = {0x5d};
static const struct board_touch_gt911 touch0_driver = {.panel = &touch0_panel, .calibrated = &touch0_calibrated, .device = &touch0_device, .addresses = touch0_addresses, .address_count = 1, .i2c_hz = 400000};

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

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "jc4827w543c", .title = "Guition JC4827W543C", .target = "esp32s3"};
