/*
 * The glue of cyd_s028r, made by tools/boards_gen.py from catalog/boards/cyd_s028r/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * Every function of boards.h is here: by the data for the parts the board has, returning
 * false for the parts it has not, so the contract of boards.h holds at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "board_display.h"
#include "board_sound_dac.h"
#include "board_touch.h"
#include "board_touch_lcd.h"
#include "board_touch_spi.h"
#include "bus/dgx_spi_esp32.h"
#include "driver/spi_common.h"
#include "drivers/ili9341.h"
#include "esp_lcd_touch_xpt2046.h"
#include "esp_log.h"
#include <stdlib.h>
#include <string.h>

/* CYD (ESP32-2432S028R): 2.8-inch 320x240 ILI9341 on SPI2, lying landscape; a resistive XPT2046 touch on SPI3 (one finger); sound the chip's own 8-bit DAC on GPIO26 through the board's amplifier; the BOOT button; the microSD slot wired to pins no host is left for (spi3 is the touch's): kept as data for the program. */

/* The buses of the board. */
static const struct board_spi_bus board_spi_spi3 = {.host = SPI3_HOST, .mosi = GPIO_NUM_32, .miso = GPIO_NUM_39, .sclk = GPIO_NUM_25, .hz = 1000000};

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_table[] = {{"spi.spi2", "hz", 40000000}, {"spi.spi2", "miso", 12}, {"spi.spi2", "mosi", 13}, {"spi.spi2", "sclk", 14}, {"spi.spi3", "hz", 1000000}, {"spi.spi3", "miso", 39}, {"spi.spi3", "mosi", 32}, {"spi.spi3", "sclk", 25}, {"sdspi.sd", "miso", 19}, {"sdspi.sd", "mosi", 23}, {"sdspi.sd", "sclk", 18}, {"light", "in", 34}, {"rgb", "b", 17}, {"rgb", "g", 16}, {"rgb", "r", 4}, {"sd", "cs", 5}};

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

/* The SPI buses open to the program's devices. A host with only a display on it is not one of them. */
static const struct board_spi_bus *const board_spi_buses[] = {&board_spi_spi3};

const struct board_spi_bus *board_spi_bus(int host)
{
    for (size_t i = 0; i < sizeof(board_spi_buses) / sizeof(board_spi_buses[0]); ++i)
        if (board_spi_buses[i]->host == host) return board_spi_buses[i];
    return NULL;
}

/* The hosts the board's buses claim, SPI and QSPI alike: spi2, spi3. */
bool board_spi_taken(int host)
{
    static const int taken[] = {SPI2_HOST, SPI3_HOST};
    for (size_t i = 0; i < sizeof(taken) / sizeof(taken[0]); ++i)
        if (taken[i] == host) return true;
    return false;
}

/* The board wires no I2C bus: nothing for board_glue_i2c to make. */
const struct board_i2c_pins *board_i2c_pins(void)
{
    return NULL;
}

/* lcd: a 240x320 ili9341 on spi.spi2. */
static dgx_bus_protocols_t *display0_bus(void)
{
    return dgx_spi_init(SPI2_HOST, SPI_DMA_CH_AUTO, GPIO_NUM_13, GPIO_NUM_12, GPIO_NUM_14, GPIO_NUM_15, GPIO_NUM_2, 40000000, 0);
}

static dgx_screen_t *display0_screen(dgx_bus_protocols_t *bus)
{
    return dgx_ili9341_init(bus, GPIO_NUM_NC, GPIO_NUM_21, 16, DgxScreenRGB);
}

static const struct board_display_panel display_panels[] = {
    {.name = "lcd", .glass_w = 240, .glass_h = 320, .mm_w = 43, .mm_h = 58, .dir_x = DgxScreenRightLeft, .dir_y = DgxScreenTopBottom, .swap_xy = true, .backlight = GPIO_NUM_NC, .backlight_on = 1, .bus = display0_bus, .screen = display0_screen, .orientation = dgx_ili9341_orientation},
};
static struct board_display_started displays_started[1];
const struct board_display_table board_display_table = {.panels = display_panels, .started = displays_started, .count = 1};

/* touch: atanisoft/esp_lcd_touch_xpt2046 on spi.spi3, the calibration of its measured board. */
static const dgx_di_calibration_t touch0_calibration = {.version = 1, .size = sizeof(dgx_di_calibration_t), .x_min = 0, .x_max = 4095, .y_min = 0, .y_max = 4095, .width = 240, .height = 320, .flags = 1, .knots_x = 3, .knots_y = 3, .rounds = 3, .affine = {74051, -652, -886661, 173, 75199, -702795}, .x = {{30, 30}, {119, 119}, {209, 209}}, .y = {{30, 30}, {159, 160}, {289, 289}}, .down_ms = 130, .up_ms = 30, .blink_ms = 101, .gap_ms = 0, .off_tenths = 164, .worst_tenths = 290, .left_tenths = 18, .left_worst_tenths = 30};
static const struct board_touch_calibration touch0_calibrated = {.calibration = &touch0_calibration, .placeholder = false};
static const struct board_touch_panel touch0_panel = {.x_max = 4096, .y_max = 4096, .rst = GPIO_NUM_NC, .irq = GPIO_NUM_36, .fingers = 1};
static const struct board_touch_spi touch0_driver = {.panel = &touch0_panel, .host = SPI3_HOST, .cs = GPIO_NUM_33, .hz = 1000000, .create = esp_lcd_touch_new_spi_xpt2046};
static dgx_di_esp_lcd_touch_t touch0_device;

static bool touch0_start(int index, const struct board_display *display, struct board_touch *out)
{
    if (!board_dgx_screen(display)) return false;
    esp_lcd_touch_handle_t handle = board_glue_touch_spi_new(&touch0_driver);
    return handle && board_glue_touch_lcd_attach(&touch0_device, index, handle, false, &touch0_panel, &touch0_calibrated, display, out);
}

static const struct board_touch_entry touch_entries[] = {{.name = "touch", .over = "lcd", .start = touch0_start}};
static struct board_touch touches_started[1];
static struct board_touch_slot touch_slots[1];
const struct board_touch_slots board_touch_slots = {.slots = touch_slots, .count = 1};
const struct board_touch_table board_touch_table = {.entries = touch_entries, .started = touches_started, .count = 1};

/* sound: dac at 22050 Hz. */
static bool sound0_start(int index, board_sound_source_t source)
{
    return board_glue_sound_dac_start(index, GPIO_NUM_26, GPIO_NUM_NC, 22050, source);
}

static const struct board_sound_entry sound_entries[] = {{.name = "sound", .rate = 22050, .start = sound0_start}};
static struct board_sound_stream sound_streams[1];
const struct board_sound_table board_sound_table = {.entries = sound_entries, .streams = sound_streams, .count = 1};

static const struct board_button_entry button_entries[] = {{.name = "boot", .pin = 0, .active_low = true}};
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
const struct board_data board_data = {.name = "cyd_s028r", .title = "CYD (ESP32-2432S028R)", .target = "esp32"};
