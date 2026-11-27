/*
 * The glue of esp32_s3_touch_amoled_1_32, made by tools/boards_gen.py from catalog/boards/esp32_s3_touch_amoled_1_32/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * The data of the board as tables, and the functions of the parts it starts: src/ reads the
 * tables, and what the board has not returns false there, so the contract of boards.h holds
 * at link.
 */
#include "boards.h"
#include "board_glue.h"
/* jef-sure/dgx before 0.12.4: co5300: no library this component can start it with: none in the catalog */
#if BOARDS_VERSION_JEF_SURE__DGX < BOARDS_VERSION(0, 12, 4)
#error "esp32_s3_touch_amoled_1_32 needs jef-sure/dgx 0.12.4 or later"
#endif

#include "sdkconfig.h"

#include "board_display.h"
#include "board_sound_es8311.h"
#include "board_touch.h"
#include "board_touch_i2c.h"
#include "board_touch_lcd.h"
#include "board_touch_spi.h"
#include "bus/dgx_qspi_esp32.h"
#include "driver/i2s_std.h"
#include "drivers/co5300.h"
#include "esp_lcd_touch_cst816s.h"

/* Waveshare ESP32-S3-Touch-AMOLED-1.32: A round 1.32-inch 466x466 AMOLED, CO5300 on QSPI, CST820 touch, ES8311 with a speaker header and a microphone; an ESP32-S3-PICO-1 with 8 MB flash and 8 MB octal PSRAM, a battery charger, PWR and BOOT buttons. */

/* The buses of the board. */
static const struct board_i2c_pins board_i2c_buses[] = {
    {.port = I2C_NUM_0, .sda = GPIO_NUM_47, .scl = GPIO_NUM_48}, /* i2c.i2c0 */
};
static const struct board_i2s_bus board_i2s_i2s0 = {.port = I2S_NUM_0, .mclk = GPIO_NUM_38, .bclk = GPIO_NUM_39, .ws = GPIO_NUM_41, .dout = GPIO_NUM_42, .din = GPIO_NUM_40};

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_fields[] = {{"qspi.spi2", "d0", 12}, {"qspi.spi2", "d1", 13}, {"qspi.spi2", "d2", 14}, {"qspi.spi2", "d3", 15}, {"qspi.spi2", "hz", 40000000}, {"qspi.spi2", "sclk", 11}, {"i2c.i2c0", "scl", 48}, {"i2c.i2c0", "sda", 47}, {"i2s.i2s0", "bclk", 39}, {"i2s.i2s0", "din", 40}, {"i2s.i2s0", "dout", 42}, {"i2s.i2s0", "mclk", 38}, {"i2s.i2s0", "ws", 41}, {"battery", "in", 4}, {"usb", "d_minus", 19}, {"usb", "d_plus", 20}};
const struct board_bus_table board_bus_table = {.fields = board_bus_fields, .count = sizeof(board_bus_fields) / sizeof(board_bus_fields[0])};

/* The hosts the board's buses claim, SPI and QSPI alike: spi2. */
static const int board_spi_hosts[] = {SPI2_HOST};
const struct board_spi_table board_spi_table = {.taken = board_spi_hosts, .taken_count = sizeof(board_spi_hosts) / sizeof(board_spi_hosts[0])};

/* The board's I2C buses by port: board_glue_i2c makes the master of one at the first ask. */
const struct board_i2c_table board_i2c_table = {.buses = board_i2c_buses, .count = sizeof(board_i2c_buses) / sizeof(board_i2c_buses[0])};

/* lcd: a 466x466 co5300 on qspi.spi2. */
static dgx_bus_protocols_t *display0_bus(void)
{
    return dgx_qspi_init(SPI2_HOST, SPI_DMA_CH_AUTO, GPIO_NUM_12, GPIO_NUM_13, GPIO_NUM_14, GPIO_NUM_15, GPIO_NUM_11, GPIO_NUM_10, 40000000, 0);
}

static dgx_screen_t *display0_screen(dgx_bus_protocols_t *bus)
{
    return dgx_co5300_init(bus, GPIO_NUM_8, 16, DgxScreenRGB, DGX_CO5300_466X466);
}

static const struct board_display_panel display_panels[] = {
    {.name = "lcd", .glass_w = 466, .glass_h = 466, .mm_w = 34, .mm_h = 34, .dir_x = DgxScreenLeftRight, .dir_y = DgxScreenTopBottom, .swap_xy = false, .backlight = GPIO_NUM_NC, .backlight_on = 1, .bus = display0_bus, .screen = display0_screen, .orientation = board_glue_screen_orientation},
};
static struct board_display_started displays_started[1];
const struct board_display_table board_display_table = {.panels = display_panels, .started = displays_started, .count = 1};

/* touch: espressif/esp_lcd_touch_cst816s on i2c.i2c0, the calibration of its measured board. */
static const dgx_di_aim_t touch0_aims[] = {{.meant_x = 90, .meant_y = 90, .x = 376, .y = 374}, {.meant_x = 375, .meant_y = 90, .x = 72, .y = 376}, {.meant_x = 90, .meant_y = 375, .x = 376, .y = 83}, {.meant_x = 375, .meant_y = 375, .x = 68, .y = 73}, {.meant_x = 233, .meant_y = 30, .x = 221, .y = 438}, {.meant_x = 233, .meant_y = 435, .x = 219, .y = 12}, {.meant_x = 30, .meant_y = 233, .x = 427, .y = 224}, {.meant_x = 435, .meant_y = 233, .x = 9, .y = 211}, {.meant_x = 233, .meant_y = 233, .x = 217, .y = 214}};
static const struct board_touch_calibration touch0_calibrated = {.aims = touch0_aims, .count = 9, .width = 466, .height = 466, .blink_ms = 0, .gap_ms = 0, .placeholder = false};
static const struct board_touch_panel touch0_panel = {.x_max = 466, .y_max = 466, .rst = GPIO_NUM_7, .irq = GPIO_NUM_6, .i2c_port = I2C_NUM_0, .fingers = 1};
static dgx_di_esp_lcd_touch_t touch0_device;
static const struct board_touch_i2c touch0_driver = {.panel = &touch0_panel, .calibrated = &touch0_calibrated, .device = &touch0_device, .io = ESP_LCD_TOUCH_IO_I2C_CST816S_CONFIG(), .address = 0x15, .hz = 400000, .create = esp_lcd_touch_new_i2c_cst816s};

static const struct board_touch_entry touch_entries[] = {{.name = "touch", .over = "lcd", .start = board_glue_touch_i2c_start, .esp_lcd_touch_i2c = &touch0_driver}};
static struct board_touch touches_started[1];
static struct board_touch_slot touch_slots[1];
const struct board_touch_slots board_touch_slots = {.slots = touch_slots, .count = 1};
const struct board_touch_table board_touch_table = {.entries = touch_entries, .started = touches_started, .count = 1};

/* sound: es8311 at 22050 Hz. */
static const struct board_sound_es8311 sound0_es8311 = {.i2s = &board_i2s_i2s0, .i2c_port = I2C_NUM_0, .address = 0x18, .pa = GPIO_NUM_46,
                                                      .pa_voltage = 5.0f, .codec_dac_voltage = 3.3f, .volume = 25};

static const struct board_sound_entry sound_entries[] = {{.name = "sound", .rate = 22050, .init = board_glue_sound_es8311_init, .es8311 = &sound0_es8311}};
static struct board_sound_stream sound_streams[1];
const struct board_sound_table board_sound_table = {.entries = sound_entries, .streams = sound_streams, .count = 1};

static const struct board_button_entry button_entries[] = {{.name = "boot", .pin = 0, .active_low = true}, {.name = "pwr", .pin = 17, .active_low = true}};
const struct board_button_table board_button_table = {.entries = button_entries, .count = 2};

const struct board_radio_table board_radio_table = {.count = 0};

const struct board_ethernet_table board_ethernet_table = {.count = 0};

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "esp32_s3_touch_amoled_1_32", .title = "Waveshare ESP32-S3-Touch-AMOLED-1.32", .target = "esp32s3"};
