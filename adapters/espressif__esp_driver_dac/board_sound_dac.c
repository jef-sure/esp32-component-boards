/* Sound through the ESP32's own DAC: 8 bits on a pin, fed by DMA. */
#include "board_sound_dac.h"
#include "boards_esp_driver_dac.h"
#include "driver/dac_continuous.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "board";

enum { DAC_CH0_GPIO = 25, DAC_DESCRIPTORS = 4, DAC_MIDDLE = 128, WRITE_FOREVER = -1 };

static dac_continuous_handle_t dac;
static int                     dac_index = -1;

static esp_err_t dac_write(int16_t *samples, size_t count)
{
    static uint8_t bytes[BOARD_SOUND_FRAMES];
    for (size_t i = 0; i < count; ++i) bytes[i] = (uint8_t)((samples[i] >> 8) + DAC_MIDDLE);
    size_t loaded = 0;
    return dac_continuous_write(dac, bytes, count, &loaded, WRITE_FOREVER);
}

static const struct board_sound_output output = {"dac_continuous_write", dac_write};

bool board_glue_sound_dac_init(int index, int out, int pa, uint32_t rate)
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
        err = gpio_set_direction((gpio_num_t)pa, GPIO_MODE_OUTPUT);
        if (err == ESP_OK) err = gpio_set_level((gpio_num_t)pa, 1);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "gpio_set_level: %s (the amplifier on GPIO %d)", esp_err_to_name(err), pa);
            dac_continuous_disable(handle);
            dac_continuous_del_channels(handle);
            return false;
        }
    }
    dac       = handle;
    dac_index = index;
    board_glue_sound_ready(index, &output);
    ESP_LOGI(TAG, "the DAC at %lu Hz", (unsigned long)rate);
    return true;
}

dac_continuous_handle_t board_dac_continuous(const board_sound_t *sound)
{
    return sound && dac && sound->index == dac_index ? dac : NULL;
}
