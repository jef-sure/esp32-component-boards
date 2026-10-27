/*
 * The glue of cyd, made by tools/boards_gen.py from boards-data/cyd/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * Every function of boards.h is here: by the data for the parts the board has, answering
 * false for the parts it has not, so the contract of boards.h holds at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "bus/dgx_spi_esp32.h"
#include "dgx_di.h"
#include "dgx_di_esp_lcd_touch.h"
#include "driver/dac_continuous.h"
#include "driver/gpio.h"
#include "driver/spi_common.h"
#include "drivers/ili9341.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_touch_xpt2046.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdlib.h>
#include <string.h>

/* CYD (ESP32-2432S028R): 2.8-inch 320x240 ILI9341 on SPI2, lying landscape; a resistive XPT2046 touch on SPI3 (one finger); sound the chip's own 8-bit DAC on GPIO26 through the board's amplifier; the BOOT button; the microSD slot wired to pins no host is left for (spi3 is the touch's): kept as data for the program. */

/* The pins of the board, each named by the part it serves: a bus's own, a device's
 * strobes (cs, dc, rst, backlight, an amplifier's pa). */
static const struct board_spi_bus board_spi_spi2 = {.host = SPI2_HOST, .mosi = GPIO_NUM_13, .miso = GPIO_NUM_12, .sclk = GPIO_NUM_14, .hz = 40000000};
static const struct board_spi_bus board_spi_spi3 = {.host = SPI3_HOST, .mosi = GPIO_NUM_32, .miso = GPIO_NUM_39, .sclk = GPIO_NUM_25, .hz = 1000000};
#define PIN_CS GPIO_NUM_15
#define PIN_DC GPIO_NUM_2
#define PIN_LCD_BACKLIGHT GPIO_NUM_21
#define PIN_TOUCH_RST GPIO_NUM_NC
#define PIN_TOUCH_INT GPIO_NUM_36
#define PIN_TOUCH_CS GPIO_NUM_33
#define PIN_SOUND_OUT GPIO_NUM_26
#define PIN_BUTTON GPIO_NUM_0

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_table[] = {{"spi.spi2", "hz", 40000000}, {"spi.spi2", "miso", 12}, {"spi.spi2", "mosi", 13}, {"spi.spi2", "sclk", 14}, {"spi.spi3", "hz", 1000000}, {"spi.spi3", "miso", 39}, {"spi.spi3", "mosi", 32}, {"spi.spi3", "sclk", 25}, {"sdspi.sd", "cs", 5}, {"sdspi.sd", "miso", 19}, {"sdspi.sd", "mosi", 23}, {"sdspi.sd", "sclk", 18}};

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

/* The board's SPI buses by host: a device the program adds takes one of them or a free host. */
static const struct board_spi_bus *const board_spi_buses[] = {&board_spi_spi2, &board_spi_spi3};

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

/* The display: a 240x320 ili9341 on spi.spi2, the glass 43x58 mm as the controller
 * scans it; lying as the board shows it, 320x240, 58x43 mm. */
enum { GLASS_W = 240, GLASS_H = 320, GLASS_MM_W = 43, GLASS_MM_H = 58 };

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
    dgx_bus_protocols_t *bus = dgx_spi_init(SPI2_HOST, SPI_DMA_CH_AUTO, GPIO_NUM_13, GPIO_NUM_12, GPIO_NUM_14, PIN_CS, PIN_DC, 40000000, 0); /* spi.spi2 */
    if (!bus) return false;
    dgx_screen_t *screen = dgx_ili9341_init(bus, GPIO_NUM_NC, PIN_LCD_BACKLIGHT, 16, DgxScreenRGB);
    if (!screen) {
        bus->dispose(bus);
        return false;
    }
    dgx_ili9341_orientation(screen, DgxScreenRightLeft, DgxScreenTopBottom, true); /* as the board shows it; a program turns it its own way after */
    out->screen = screen;
    out->bus = bus;
    display_lies(out, DgxScreenRightLeft, DgxScreenTopBottom, true);
    return true;
}

bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy)
{
    if (!display || !display->screen) return false;
    dgx_ili9341_orientation((dgx_screen_t *)display->screen, (dgx_orientation_t)dir_x, (dgx_orientation_t)dir_y, swap_xy);
    display_lies(display, dir_x, dir_y, swap_xy);
    return true;
}

/* The touch: a XPT2046 of atanisoft/esp_lcd_touch_xpt2046 on spi.spi3, its own cs and irq,
 * one finger of a resistive panel, the calibration of its measured board. */
/* The calibration below is a placeholder, not measured on a board: the touch works, only not
 * straight; board_touch_start says so. Measure the board (dgx_di_calibrate_measure) and put the
 * numbers in the data. */
static const dgx_di_calibration_t touch_calibration = {.version = 1, .size = sizeof(dgx_di_calibration_t), .x_min = 0, .x_max = 4095, .y_min = 0, .y_max = 4095, .width = 320, .height = 240, .flags = 0, .knots_x = 3, .knots_y = 3, .rounds = 3, .affine = {40960, 0, 0, 0, 40960, 0}, .x = {{300, 300}, {2048, 2048}, {3800, 3800}}, .y = {{300, 300}, {2048, 2048}, {3800, 3800}}, .down_ms = 20, .up_ms = 40, .blink_ms = 0, .gap_ms = 0, .off_tenths = 0, .worst_tenths = 0, .left_tenths = 0, .left_worst_tenths = 0};
static dgx_di_esp_lcd_touch_t touch_panel;

bool board_touch_start(const struct board_display *display, struct dgx_di_device **device_out, void **pointer_out)
{
    if (!display || !display->screen) return false;
    const struct board_spi_bus *bus = board_spi_bus(SPI3_HOST);
    if (!bus) return false;
    /* the host is the touch's own, no display on it: taken here, once */
    static bool host_up;
    if (!host_up) {
        const spi_bus_config_t host = {.mosi_io_num = bus->mosi, .miso_io_num = bus->miso, .sclk_io_num = bus->sclk, .quadwp_io_num = GPIO_NUM_NC, .quadhd_io_num = GPIO_NUM_NC, .max_transfer_sz = 0};
        if (spi_bus_initialize((spi_host_device_t)bus->host, &host, SPI_DMA_CH_AUTO) != ESP_OK) {
            ESP_LOGE("board", "the SPI host of the touch could not be taken");
            return false;
        }
        host_up = true;
    }
    const esp_lcd_panel_io_spi_config_t config = {
        .cs_gpio_num = PIN_TOUCH_CS, .dc_gpio_num = GPIO_NUM_NC, .spi_mode = 0, .pclk_hz = 1000000,
        .trans_queue_depth = 3, .lcd_cmd_bits = 8, .lcd_param_bits = 8,
    };
    esp_lcd_panel_io_handle_t io;
    if (esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)(intptr_t)bus->host, &config, &io) != ESP_OK) return false;
    const esp_lcd_touch_config_t tconfig = {.x_max = 4095, .y_max = 4095, .rst_gpio_num = PIN_TOUCH_RST, .int_gpio_num = PIN_TOUCH_INT};
    esp_lcd_touch_handle_t handle = NULL;
    if (esp_lcd_touch_new_spi_xpt2046(io, &tconfig, &handle) != ESP_OK || !handle) {
        ESP_LOGE("board", "no touch panel answers on the board's SPI bus");
        esp_lcd_panel_io_del(io);
        return false;
    }
    dgx_di_esp_lcd_touch_init(&touch_panel, handle, 1, false);
    dgx_di_pointer_t *pointer = board_glue_pointer(); /* the one pointer of the core */
    dgx_di_pointer_init(pointer, &touch_panel.device, 0, (const dgx_screen_t *)display->screen);
    if (!dgx_di_pointer_calibrate(pointer, &touch_calibration))
        ESP_LOGW("board", "the calibration is not this board's: the touch works, only not as straight");
    ESP_LOGW("board", "the touch calibration of this board is a placeholder, not measured: measure the board and put the numbers in the data");
    if (device_out) *device_out = &touch_panel.device;
    if (pointer_out) *pointer_out = pointer;
    return true;
}

enum { SOUND_FRAMES = 256 }; /* samples a write: 11 ms at 22050 */

static board_sound_source_t sound_source;

void board_sound_source(board_sound_source_t source)
{
    sound_source = source;
}

/* The sound: the chip's own DAC, 8 bits on a pin, fed by DMA (dac_continuous); the writes wait
 * for the DMA, which sets the pace. A task of its own takes the program's next samples and
 * writes them. */
static dac_continuous_handle_t dac;

static void sound_task(void *arg)
{
    (void)arg;
    static int16_t samples[SOUND_FRAMES];
    static uint8_t bytes[SOUND_FRAMES];
    bool           told = false;
    for (;;) {
        if (sound_source) sound_source(samples, SOUND_FRAMES);
        else memset(samples, 0, sizeof(samples));
        for (int i = 0; i < SOUND_FRAMES; ++i) bytes[i] = (uint8_t)((samples[i] >> 8) + 128);
        size_t loaded = 0;
        if (dac_continuous_write(dac, bytes, sizeof(bytes), &loaded, -1) == ESP_OK) continue;
        if (!told) {
            ESP_LOGE("board", "the DAC takes no samples");
            told = true;
        }
        vTaskDelay(pdMS_TO_TICKS(SOUND_FRAMES * 1000 / 22050) + 1);
    }
}

bool board_sound_start(board_sound_source_t source, uint32_t *rate_out)
{
    if (!dac) {
        const dac_continuous_config_t config = {.chan_mask = DAC_CHANNEL_MASK_CH1, .desc_num = 4, .buf_size = SOUND_FRAMES, .freq_hz = 22050, .offset = 0, .clk_src = DAC_DIGI_CLK_SRC_DEFAULT, .chan_mode = DAC_CHANNEL_MODE_SIMUL};
        if (dac_continuous_new_channels(&config, &dac) != ESP_OK || dac_continuous_enable(dac) != ESP_OK) {
            ESP_LOGE("board", "no DAC");
            dac = NULL;
            return false;
        }
        sound_source = source;
        if (xTaskCreate(sound_task, "sound", 3072, NULL, 6, NULL) != pdPASS) {
            ESP_LOGE("board", "no task for the sound");
            return false;
        }
        ESP_LOGI("board", "the DAC at 22050 Hz");
    }
    if (rate_out) *rate_out = 22050;
    return true;
}

/* The button of the board, low when pressed. */
bool board_button(bool *pressed)
{
    if (!pressed) return false;
    static bool set_up;
    if (!set_up) {
        const gpio_config_t config = {.pin_bit_mask = 1ULL << PIN_BUTTON, .mode = GPIO_MODE_INPUT, .pull_up_en = GPIO_PULLUP_ENABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE};
        gpio_config(&config);
        set_up = true;
    }
    *pressed = gpio_get_level((gpio_num_t)PIN_BUTTON) == 0;
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

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "cyd", .title = "CYD (ESP32-2432S028R)", .target = "esp32"};
