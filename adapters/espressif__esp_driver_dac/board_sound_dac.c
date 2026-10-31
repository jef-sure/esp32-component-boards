/* Sound through the ESP32's own DAC: 8 bits on a pin, fed by DMA. */
#include "board_sound_dac.h"
#include "driver/dac_continuous.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "board";

enum { DAC_CH0_GPIO = 25, DAC_DESCRIPTORS = 4, DAC_MIDDLE = 128, WRITE_FOREVER = -1 };

static dac_continuous_handle_t dac;

static esp_err_t dac_write(int16_t *samples, size_t count)
{
    static uint8_t bytes[BOARD_SOUND_FRAMES];
    for (size_t i = 0; i < count; ++i) bytes[i] = (uint8_t)((samples[i] >> 8) + DAC_MIDDLE);
    size_t loaded = 0;
    return dac_continuous_write(dac, bytes, count, &loaded, WRITE_FOREVER);
}

static const struct board_sound_output output = {"dac_continuous_write", dac_write};

bool board_glue_sound_dac_start(int index, int out, int pa, uint32_t rate, board_sound_source_t source)
{
    if (dac) return true;
    const dac_continuous_config_t config = {.chan_mask = out == DAC_CH0_GPIO ? DAC_CHANNEL_MASK_CH0 : DAC_CHANNEL_MASK_CH1,
                                            .desc_num  = DAC_DESCRIPTORS,
                                            .buf_size  = BOARD_SOUND_FRAMES,
                                            .freq_hz   = rate,
                                            .offset    = 0,
                                            .clk_src   = DAC_DIGI_CLK_SRC_DEFAULT,
                                            .chan_mode = DAC_CHANNEL_MODE_SIMUL};
    dac_continuous_handle_t       handle = NULL;
    esp_err_t                     err    = dac_continuous_new_channels(&config, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "dac_continuous_new_channels: %s", esp_err_to_name(err));
        return false;
    }
    err = dac_continuous_enable(handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "dac_continuous_enable: %s", esp_err_to_name(err));
        dac_continuous_del_channels(handle);
        return false;
    }
    if (pa != GPIO_NUM_NC) {
        gpio_set_direction((gpio_num_t)pa, GPIO_MODE_OUTPUT);
        gpio_set_level((gpio_num_t)pa, 1);
    }
    dac = handle;
    if (!board_glue_sound_run(index, &output, rate, source)) {
        dac_continuous_disable(handle);
        dac_continuous_del_channels(handle);
        dac = NULL;
        return false;
    }
    ESP_LOGI(TAG, "the DAC at %lu Hz", (unsigned long)rate);
    return true;
}
