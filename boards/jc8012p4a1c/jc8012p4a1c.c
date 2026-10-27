/*
 * The glue of jc8012p4a1c, made by tools/boards_gen.py from boards-data/jc8012p4a1c/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * Every function of boards.h is here: by the data for the parts the board has, answering
 * false for the parts it has not, so the contract of boards.h holds at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "bus/dgx_dsi_esp32.h"
#include "dgx_di.h"
#include "dgx_di_gsl3680.h"
#include "driver/gpio.h"
#include "driver/i2s_std.h"
#include "drivers/jd9365.h"
#include "esp_codec_dev.h"
#include "esp_codec_dev_defaults.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdlib.h>
#include <string.h>

/* Guition JC8012P4A1C: 10.1-inch 800x1280 JD9365 on MIPI-DSI (lying 1280x800), GSL3680 touch (firmware written into it at start), ES8311 sound. */

/* The pins of the board, each named by the part it serves: a bus's own, a device's
 * strobes (cs, dc, rst, backlight, an amplifier's pa). */
static const struct board_i2c_pins board_i2c_pins_of = {.port = I2C_NUM_0, .sda = GPIO_NUM_7, .scl = GPIO_NUM_8}; /* i2c.i2c0 */
static const struct board_i2s_bus board_i2s_i2s0 = {.port = I2S_NUM_0, .mclk = GPIO_NUM_13, .bclk = GPIO_NUM_12, .ws = GPIO_NUM_10, .dout = GPIO_NUM_9, .din = GPIO_NUM_11};
#define PIN_LCD_RST GPIO_NUM_27
#define PIN_LCD_BACKLIGHT GPIO_NUM_23
#define PIN_TOUCH_RST GPIO_NUM_22
#define PIN_TOUCH_INT GPIO_NUM_21
#define PIN_SOUND_PA GPIO_NUM_20

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_table[] = {{"dsi.dsi0", "lane_mbps", 1000}, {"dsi.dsi0", "lanes", 2}, {"dsi.dsi0", "phy_ldo_chan", 3}, {"dsi.dsi0", "phy_ldo_mv", 2500}, {"i2c.i2c0", "scl", 8}, {"i2c.i2c0", "sda", 7}, {"i2s.i2s0", "bclk", 12}, {"i2s.i2s0", "din", 11}, {"i2s.i2s0", "dout", 9}, {"i2s.i2s0", "mclk", 13}, {"i2s.i2s0", "ws", 10}, {"sdio.sdio0", "clk", 18}, {"sdio.sdio0", "cmd", 19}, {"sdio.sdio0", "d0", 14}, {"sdio.sdio0", "d1", 15}, {"sdio.sdio0", "d2", 16}, {"sdio.sdio0", "d3", 17}, {"sdio.sdio0", "reset", 54}};

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

/* The display: a 800x1280 jd9365 on dsi.dsi0, the glass 136x217 mm as the controller
 * scans it; lying as the board shows it, 1280x800, 217x136 mm. */
enum { DSI_LANES = 2, DSI_LANE_MBPS = 1000, DSI_PHY_LDO_CHAN = 3, DSI_PHY_LDO_MV = 2500 };
enum { GLASS_W = 800, GLASS_H = 1280, GLASS_MM_W = 136, GLASS_MM_H = 217 };

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
    dgx_bus_protocols_t *bus = dgx_dsi_init(0, DSI_LANES, DSI_LANE_MBPS, DSI_PHY_LDO_CHAN, DSI_PHY_LDO_MV);
    if (!bus) return false;
    dgx_screen_t *screen = dgx_jd9365_init(bus, PIN_LCD_RST, 16, DgxScreenRGB, DgxDsiTwoFrames);
    if (!screen) {
        bus->dispose(bus);
        return false;
    }
    dgx_jd9365_orientation(screen, DgxScreenRightLeft, DgxScreenTopBottom, true); /* as the board shows it; a program turns it its own way after */
    /* the light goes on over a black frame buffer, not over what the panel had before */
    gpio_set_direction(PIN_LCD_BACKLIGHT, GPIO_MODE_OUTPUT);
    gpio_set_level(PIN_LCD_BACKLIGHT, 1);
    out->screen = screen;
    out->bus = bus;
    display_lies(out, DgxScreenRightLeft, DgxScreenTopBottom, true);
    return true;
}

bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy)
{
    if (!display || !display->screen) return false;
    dgx_jd9365_orientation((dgx_screen_t *)display->screen, (dgx_orientation_t)dir_x, (dgx_orientation_t)dir_y, swap_xy);
    display_lies(display, dir_x, dir_y, swap_xy);
    return true;
}

/* The touch: a GSL3680 on the board's I2C bus, 5 fingers, the calibration of its measured board. */
static const dgx_di_calibration_t touch_calibration = {.version = 1, .size = sizeof(dgx_di_calibration_t), .x_min = 0, .x_max = 1663, .y_min = 0, .y_max = 895, .width = 800, .height = 1280, .flags = 6, .knots_x = 3, .knots_y = 3, .rounds = 3, .affine = {65301, 579, 774524, -221, 66564, -691501}, .x = {{44, 48}, {407, 399}, {747, 751}}, .y = {{47, 48}, {642, 640}, {1230, 1231}}, .down_ms = 50, .up_ms = 60, .blink_ms = 22, .gap_ms = 0, .off_tenths = 181, .worst_tenths = 220, .left_tenths = 50, .left_worst_tenths = 110};
static dgx_di_gsl3680_t touch_panel;

bool board_touch_start(const struct board_display *display, struct dgx_di_device **device_out, void **pointer_out)
{
    if (!display || !display->screen) return false;
    i2c_master_bus_handle_t bus = board_glue_i2c();
    if (!bus) return false;
    const uint8_t *fw_start;
    size_t         fw_size;
    if (!board_touch_firmware(&fw_start, &fw_size)) {
        ESP_LOGE("board", "no firmware embedded for the touch panel: the program defines board_touch_firmware, see the docs");
        return false;
    }
    if (!dgx_di_gsl3680_init(&touch_panel, bus, PIN_TOUCH_RST, PIN_TOUCH_INT, 0, fw_start, fw_size)) {
        ESP_LOGE("board", "no GSL3680 answers");
        return false;
    }
    dgx_di_pointer_t *pointer = board_glue_pointer(); /* the one pointer of the core */
    dgx_di_pointer_init(pointer, &touch_panel.device, 0, (const dgx_screen_t *)display->screen);
    if (!dgx_di_pointer_calibrate(pointer, &touch_calibration))
        ESP_LOGW("board", "the calibration is not this board's: the touch works, only not as straight");
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

/* The sound: an ES8311 on i2s.i2s0, set up over the board's I2C bus, its amplifier on PIN_SOUND_PA;
 * a task of its own takes the program's next samples and writes them; the writes wait for the I2S, which sets the pace. */
enum { SOUND_VOLUME = 25 }; /* of the codec, 0..100 */

static esp_codec_dev_handle_t speaker;

static void sound_task(void *arg)
{
    (void)arg;
    static int16_t samples[SOUND_FRAMES];
    bool           told = false;
    for (;;) {
        if (sound_source) sound_source(samples, SOUND_FRAMES);
        else memset(samples, 0, sizeof(samples));
        if (esp_codec_dev_write(speaker, samples, sizeof(samples)) == ESP_CODEC_DEV_OK) continue;
        if (!told) {
            ESP_LOGE("board", "the codec takes no samples");
            told = true;
        }
        vTaskDelay(pdMS_TO_TICKS(SOUND_FRAMES * 1000 / 22050) + 1);
    }
}

bool board_sound_start(board_sound_source_t source, uint32_t *rate_out)
{
    if (!speaker) {
        i2c_master_bus_handle_t i2c = board_glue_i2c();
        if (!i2c) {
            ESP_LOGE("board", "no I2C bus for the codec");
            return false;
        }
        i2s_chan_handle_t tx;
        i2s_chan_config_t chan = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
        chan.dma_frame_num = SOUND_FRAMES;
        const i2s_std_config_t std = {
            .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(22050),
            .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
            .gpio_cfg = {.mclk = board_i2s_i2s0.mclk, .bclk = board_i2s_i2s0.bclk, .ws = board_i2s_i2s0.ws, .dout = board_i2s_i2s0.dout, .din = board_i2s_i2s0.din}, /* i2s.i2s0 */
        };
        /* on from the start: esp_codec_dev turns it off to set the format, and off before ever on is an error in the log */
        if (i2s_new_channel(&chan, &tx, NULL) != ESP_OK || i2s_channel_init_std_mode(tx, &std) != ESP_OK || i2s_channel_enable(tx) != ESP_OK) {
            ESP_LOGE("board", "no I2S");
            return false;
        }
        const audio_codec_data_if_t *data = audio_codec_new_i2s_data(&(audio_codec_i2s_cfg_t){.port = I2S_NUM_0, .tx_handle = tx});
        const audio_codec_ctrl_if_t *ctrl = audio_codec_new_i2c_ctrl(&(audio_codec_i2c_cfg_t){.port = I2C_NUM_0, .addr = 0x18, .bus_handle = i2c});
        const audio_codec_gpio_if_t *gpio = audio_codec_new_gpio();
        es8311_codec_cfg_t           es   = {.ctrl_if = ctrl, .gpio_if = gpio, .codec_mode = ESP_CODEC_DEV_WORK_MODE_DAC, .pa_pin = PIN_SOUND_PA, .use_mclk = true};
        es.hw_gain.pa_voltage = 5.0, es.hw_gain.codec_dac_voltage = 3.3;
        const audio_codec_if_t *codec = data && ctrl && gpio ? es8311_codec_new(&es) : NULL;
        speaker = codec ? esp_codec_dev_new(&(esp_codec_dev_cfg_t){.dev_type = ESP_CODEC_DEV_TYPE_OUT, .codec_if = codec, .data_if = data}) : NULL;
        esp_codec_dev_sample_info_t format = {.sample_rate = 22050, .channel = 1, .bits_per_sample = 16};
        if (!speaker || esp_codec_dev_open(speaker, &format) != ESP_CODEC_DEV_OK) {
            ESP_LOGE("board", "no ES8311");
            speaker = NULL;
            return false;
        }
        esp_codec_dev_set_out_vol(speaker, SOUND_VOLUME);
        sound_source = source;
        if (xTaskCreate(sound_task, "sound", 3072, NULL, 6, NULL) != pdPASS) {
            ESP_LOGE("board", "no task for the sound");
            return false;
        }
        ESP_LOGI("board", "ES8311 at 22050 Hz");
    }
    if (rate_out) *rate_out = 22050;
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

bool board_button(bool *pressed)
{
    (void)pressed;
    return false;
}

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "jc8012p4a1c", .title = "Guition JC8012P4A1C", .target = "esp32p4"};
