/* Sound through an I2S amplifier with no codec to set up. It has no volume of its own: a program scales its samples. */
#include "board_sound_i2s.h"
#include "driver/i2s_std.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"

static const char *TAG = "board";

static i2s_chan_handle_t sound_tx;

static esp_err_t i2s_write(int16_t *samples, size_t count)
{
    size_t written = 0;
    return i2s_channel_write(sound_tx, samples, count * sizeof(*samples), &written, portMAX_DELAY);
}

static const struct board_sound_output output = {"i2s_channel_write", i2s_write};

bool board_glue_sound_i2s_start(int index, const struct board_i2s_bus *bus, uint32_t rate, board_sound_source_t source)
{
    if (sound_tx) return true;
    i2s_chan_config_t chan = I2S_CHANNEL_DEFAULT_CONFIG(bus->port, I2S_ROLE_MASTER);
    chan.dma_frame_num     = BOARD_SOUND_FRAMES;
    i2s_chan_handle_t tx   = NULL;
    esp_err_t         err  = i2s_new_channel(&chan, &tx, NULL);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2s_new_channel: %s", esp_err_to_name(err));
        return false;
    }
    const i2s_std_config_t std = {
        .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(rate),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {.mclk = (gpio_num_t)bus->mclk, .bclk = (gpio_num_t)bus->bclk, .ws = (gpio_num_t)bus->ws, .dout = (gpio_num_t)bus->dout, .din = (gpio_num_t)bus->din},
    };
    err = i2s_channel_init_std_mode(tx, &std);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2s_channel_init_std_mode: %s", esp_err_to_name(err));
        i2s_del_channel(tx);
        return false;
    }
    err = i2s_channel_enable(tx);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2s_channel_enable: %s", esp_err_to_name(err));
        i2s_del_channel(tx);
        return false;
    }
    sound_tx = tx;
    if (!board_glue_sound_run(index, &output, rate, source)) {
        i2s_channel_disable(tx);
        i2s_del_channel(tx);
        sound_tx = NULL;
        return false;
    }
    ESP_LOGI(TAG, "I2S at %lu Hz", (unsigned long)rate);
    return true;
}
