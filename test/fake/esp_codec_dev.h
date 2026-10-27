#pragma once
/* esp_codec_dev: the device made of a data interface and a codec interface, opened in a format,
 * written to. As the real header, this one knows nothing of the ES8311 or the I2S/I2C interfaces:
 * those are esp_codec_dev_defaults.h. */
#include "esp_idf_stubs.h"
typedef void *esp_codec_dev_handle_t;
typedef struct audio_codec_data_if audio_codec_data_if_t;
typedef struct audio_codec_if audio_codec_if_t;
typedef struct { int dev_type; const audio_codec_if_t *codec_if; const audio_codec_data_if_t *data_if; } esp_codec_dev_cfg_t;
typedef struct { int sample_rate, channel, bits_per_sample; } esp_codec_dev_sample_info_t;
#define ESP_CODEC_DEV_TYPE_OUT 1
#define ESP_CODEC_DEV_OK 0
esp_codec_dev_handle_t esp_codec_dev_new(const esp_codec_dev_cfg_t *cfg);
int esp_codec_dev_open(esp_codec_dev_handle_t dev, const esp_codec_dev_sample_info_t *fmt);
int esp_codec_dev_set_out_vol(esp_codec_dev_handle_t dev, int vol);
int esp_codec_dev_write(esp_codec_dev_handle_t dev, const void *data, size_t len);
