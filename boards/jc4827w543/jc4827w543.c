/*
 * The glue of jc4827w543, made by tools/boards_gen.py from boards-data/jc4827w543/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * Every function of boards.h is here: by the data for the parts the board has, answering
 * false for the parts it has not, so the contract of boards.h holds at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "bus/dgx_qspi_esp32.h"
#include "dgx_di.h"
#include "dgx_di_esp_lcd_touch.h"
#include "drivers/nv3041a.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_touch_gt911.h"
#include "esp_log.h"
#include <stdlib.h>
#include <string.h>

/* Guition JC4827W543: 4.3-inch 480x272 NV3041A on QSPI, GT911 touch on its own I2C; an ESP32-S3 with 8 MB octal PSRAM. */

/* The pins of the board, each named by the part it serves: a bus's own, a device's
 * strobes (cs, dc, rst, backlight, an amplifier's pa). */
static const struct board_i2c_pins board_i2c_pins_of = {.port = I2C_NUM_0, .sda = GPIO_NUM_8, .scl = GPIO_NUM_4}; /* i2c.i2c0 */
#define PIN_CS GPIO_NUM_45
#define PIN_LCD_BACKLIGHT GPIO_NUM_1
#define PIN_TOUCH_RST GPIO_NUM_38
#define PIN_TOUCH_INT GPIO_NUM_3

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_table[] = {{"qspi.spi2", "d0", 21}, {"qspi.spi2", "d1", 48}, {"qspi.spi2", "d2", 40}, {"qspi.spi2", "d3", 39}, {"qspi.spi2", "hz", 40000000}, {"qspi.spi2", "sclk", 47}, {"i2c.i2c0", "scl", 4}, {"i2c.i2c0", "sda", 8}};

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

/* The board wires no SPI bus of the plain kind: none to hand out. */
const struct board_spi_bus *board_spi_bus(int host)
{
    (void)host;
    return NULL;
}

/* The hosts the board's buses claim, SPI and QSPI alike: spi2. */
bool board_spi_taken(int host)
{
    static const int taken[] = {SPI2_HOST};
    for (size_t i = 0; i < sizeof(taken) / sizeof(taken[0]); ++i)
        if (taken[i] == host) return true;
    return false;
}

/* The board's I2C: one master, made by whoever asks first (board_glue_i2c). */
const struct board_i2c_pins *board_i2c_pins(void)
{
    return &board_i2c_pins_of;
}

/* The display: a 480x272 nv3041a on qspi.spi2, the glass 95x54 mm as the controller
 * scans it; lying as the board shows it, 480x272, 95x54 mm. */
enum { GLASS_W = 480, GLASS_H = 272, GLASS_MM_W = 95, GLASS_MM_H = 54 };

/* How the display lies after an orientation call: its size follows the swap of its axes. */
static void display_lies(struct board_display *d, int dir_x, int dir_y, bool swap_xy)
{
    d->dir_x = dir_x, d->dir_y = dir_y, d->swap_xy = swap_xy;
    d->width = swap_xy ? GLASS_H : GLASS_W, d->height = swap_xy ? GLASS_W : GLASS_H;
    d->mm_w = swap_xy ? GLASS_MM_H : GLASS_MM_W, d->mm_h = swap_xy ? GLASS_MM_W : GLASS_MM_H;
}

bool board_display_init(struct board_display *out)
{
    if (!out) return false;
    dgx_bus_protocols_t *bus = dgx_qspi_init(SPI2_HOST, SPI_DMA_CH_AUTO, GPIO_NUM_21, GPIO_NUM_48, GPIO_NUM_40, GPIO_NUM_39, GPIO_NUM_47, PIN_CS, 40000000, 0); /* qspi.spi2 */
    if (!bus) return false;
    dgx_screen_t *screen = dgx_nv3041a_init(bus, GPIO_NUM_NC, PIN_LCD_BACKLIGHT, 16, DgxScreenRGB);
    if (!screen) {
        bus->dispose(bus);
        return false;
    }
    dgx_nv3041a_orientation(screen, DgxScreenLeftRight, DgxScreenTopBottom, false); /* as the board shows it; a program turns it its own way after */
    out->screen = screen;
    out->bus = bus;
    display_lies(out, DgxScreenLeftRight, DgxScreenTopBottom, false);
    return true;
}

bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy)
{
    if (!display || !display->screen) return false;
    dgx_nv3041a_orientation((dgx_screen_t *)display->screen, (dgx_orientation_t)dir_x, (dgx_orientation_t)dir_y, swap_xy);
    display_lies(display, dir_x, dir_y, swap_xy);
    return true;
}

/* The touch: a GT911 on the board's I2C bus, 5 fingers, the calibration of its measured board. */
static const dgx_di_calibration_t touch_calibration = {.version = 1, .size = sizeof(dgx_di_calibration_t), .x_min = 0, .x_max = 479, .y_min = 0, .y_max = 271, .width = 480, .height = 272, .flags = 3, .knots_x = 3, .knots_y = 3, .rounds = 3, .affine = {65793, 585, -8323, 570, 69648, -1428555}, .x = {{35, 34}, {237, 240}, {446, 445}}, .y = {{35, 34}, {135, 136}, {237, 237}}, .down_ms = 0, .up_ms = 30, .blink_ms = 0, .gap_ms = 0, .off_tenths = 121, .worst_tenths = 180, .left_tenths = 16, .left_worst_tenths = 40};
static dgx_di_esp_lcd_touch_t touch_panel;

bool board_touch_start(const struct board_display *display, struct dgx_di_device **device_out, void **pointer_out)
{
    if (!display || !display->screen) return false;
    i2c_master_bus_handle_t bus = board_glue_i2c();
    if (!bus) return false;
    static const uint8_t address[] = {ESP_LCD_TOUCH_IO_I2C_GT911_ADDRESS};
    const esp_lcd_touch_config_t config = {.x_max = 479, .y_max = 271, .rst_gpio_num = PIN_TOUCH_RST, .int_gpio_num = PIN_TOUCH_INT};
    esp_lcd_touch_handle_t handle = NULL;
    for (int i = 0; i < (int)(sizeof(address) / sizeof(address[0])) && !handle; ++i) {
        esp_lcd_panel_io_handle_t io;
        esp_lcd_panel_io_i2c_config_t io_config = ESP_LCD_TOUCH_IO_I2C_GT911_CONFIG();
        io_config.dev_addr = address[i], io_config.scl_speed_hz = 400000;
        if (esp_lcd_new_panel_io_i2c(bus, &io_config, &io) != ESP_OK) continue;
        if (esp_lcd_touch_new_i2c_gt911(io, &config, &handle) != ESP_OK) esp_lcd_panel_io_del(io); /* off the bus: the next address */
    }
    if (!handle) {
        ESP_LOGE("board", "no touch panel answers on the board's I2C bus");
        return false;
    }
    dgx_di_esp_lcd_touch_init(&touch_panel, handle, 5, true);
    dgx_di_pointer_t *pointer = board_glue_pointer(); /* the one pointer of the core */
    dgx_di_pointer_init(pointer, &touch_panel.device, 0, (const dgx_screen_t *)display->screen);
    if (!dgx_di_pointer_calibrate(pointer, &touch_calibration))
        ESP_LOGW("board", "the calibration is not this board's: the touch works, only not as straight");
    if (device_out) *device_out = &touch_panel.device;
    if (pointer_out) *pointer_out = pointer;
    return true;
}

/* What the board has not: the rest of boards.h, answering false, so that the same program
 * links and runs on every board. */
#if !CONFIG_BOARD_MODULE_CHARACTER_DISPLAY /* a module on the board's bus gives this one instead */
bool board_character_display_init(struct board_character_display *out)
{
    (void)out;
    return false;
}
#endif

bool board_sound_start(board_sound_source_t source, uint32_t *rate_out)
{
    (void)source, (void)rate_out;
    return false;
}

void board_sound_source(board_sound_source_t source)
{
    (void)source;
}

bool board_button(bool *pressed)
{
    (void)pressed;
    return false;
}

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "jc4827w543", .title = "Guition JC4827W543", .target = "esp32s3"};
