/*
 * The glue of esp32_c3_oled_042, made by tools/boards_gen.py from catalog/boards/esp32_c3_oled_042/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * The data of the board as tables, and the functions of the parts it starts: src/ reads the
 * tables, and what the board has not returns false there, so the contract of boards.h holds
 * at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "board_display.h"
#include "bus/dgx_i2c_esp32.h"
#include "drivers/ssd1306.h"

/* ESP32-C3 with a 0.42-inch OLED: A small ESP32-C3 board with a 72x40 SSD1306 OLED on I2C: 4 MB flash in the chip, USB-C to the chip, a power LED, a blue LED, BOOT and RST buttons, a ceramic antenna. */

/* The buses of the board. */
static const struct board_i2c_pins board_i2c_buses[] = {
    {.port = I2C_NUM_0, .sda = GPIO_NUM_5, .scl = GPIO_NUM_6}, /* i2c.i2c0 */
};

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_fields[] = {{"i2c.i2c0", "scl", 6}, {"i2c.i2c0", "sda", 5}, {"led", "out", 8}, {"usb", "d_minus", 18}, {"usb", "d_plus", 19}};
const struct board_bus_table board_bus_table = {.fields = board_bus_fields, .count = sizeof(board_bus_fields) / sizeof(board_bus_fields[0])};

const struct board_spi_table board_spi_table = {.count = 0};

/* The board's I2C buses by port: board_glue_i2c makes the master of one at the first ask. */
const struct board_i2c_table board_i2c_table = {.buses = board_i2c_buses, .count = sizeof(board_i2c_buses) / sizeof(board_i2c_buses[0])};

/* oled: a 72x40 ssd1306 on i2c.i2c0. */
static dgx_bus_protocols_t *display0_bus(i2c_master_bus_handle_t i2c)
{
    return dgx_i2c_init_on_bus(i2c, 0x3c, 400000);
}

static dgx_screen_t *display0_screen(dgx_bus_protocols_t *bus)
{
    return dgx_ssd1306_init(bus, SSD1306_72X40, false, GPIO_NUM_NC);
}

static const struct board_display_panel display_panels[] = {
    {.name = "oled", .glass_w = 72, .glass_h = 40, .mm_w = 9, .mm_h = 5, .dir_x = DgxScreenLeftRight, .dir_y = DgxScreenTopBottom, .swap_xy = false, .backlight = GPIO_NUM_NC, .backlight_on = 1, .i2c_port = I2C_NUM_0, .on_i2c = display0_bus, .screen = display0_screen, .orientation = dgx_ssd1306_orientation},
};
static struct board_display_started displays_started[1];
const struct board_display_table board_display_table = {.panels = display_panels, .started = displays_started, .count = 1};

const struct board_touch_table board_touch_table = {.count = 0};

const struct board_sound_table board_sound_table = {.count = 0};

static const struct board_button_entry button_entries[] = {{.name = "boot", .pin = 9, .active_low = true}};
const struct board_button_table board_button_table = {.entries = button_entries, .count = 1};

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "esp32_c3_oled_042", .title = "ESP32-C3 with a 0.42-inch OLED", .target = "esp32c3"};
