#pragma once
/* esp_codec_dev_defaults: the interfaces (I2S data, I2C control, GPIO) and the codecs' own
 * constructors. Not the device: that is esp_codec_dev.h, which a glue includes as well. */
#include "esp_idf_stubs.h"
typedef struct audio_codec_data_if audio_codec_data_if_t;
typedef struct audio_codec_ctrl_if audio_codec_ctrl_if_t;
typedef struct audio_codec_gpio_if audio_codec_gpio_if_t;
typedef struct audio_codec_if audio_codec_if_t;
#define ES8311_CODEC_DEFAULT_ADDR 0x18
#define ESP_CODEC_DEV_WORK_MODE_DAC 1
typedef struct { int port; void *tx_handle; } audio_codec_i2s_cfg_t;
typedef struct { int port; int addr; i2c_master_bus_handle_t bus_handle; } audio_codec_i2c_cfg_t;
typedef struct { const audio_codec_ctrl_if_t *ctrl_if; const audio_codec_gpio_if_t *gpio_if; int codec_mode; int pa_pin; bool use_mclk; struct { float pa_voltage, codec_dac_voltage; } hw_gain; } es8311_codec_cfg_t;
const audio_codec_data_if_t *audio_codec_new_i2s_data(const audio_codec_i2s_cfg_t *cfg);
const audio_codec_ctrl_if_t *audio_codec_new_i2c_ctrl(const audio_codec_i2c_cfg_t *cfg);
const audio_codec_gpio_if_t *audio_codec_new_gpio(void);
const audio_codec_if_t *es8311_codec_new(const es8311_codec_cfg_t *cfg);
