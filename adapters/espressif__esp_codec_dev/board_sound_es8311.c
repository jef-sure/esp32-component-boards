/* Sound through an ES8311: the codec is set up over I2C by esp_codec_dev and takes its samples over I2S. */
#include "board_sound_es8311.h"
#include "driver/i2s_std.h"
#include "esp_codec_dev.h"
#include "esp_codec_dev_defaults.h"
#include "esp_log.h"

static const char *TAG = "board";

enum { SOUND_CHANNELS = 1, SOUND_BITS = 16 };

static i2s_chan_handle_t             sound_tx;
static bool                          sound_tx_enabled;
static const audio_codec_data_if_t  *sound_data;
static const audio_codec_ctrl_if_t  *sound_ctrl;
static const audio_codec_gpio_if_t  *sound_gpio;
static const audio_codec_if_t       *sound_codec;
static esp_codec_dev_handle_t        speaker;

static esp_err_t codec_write(int16_t *samples, size_t count)
{
    return esp_codec_dev_write(speaker, samples, (int)(count * sizeof(*samples))) == ESP_CODEC_DEV_OK ? ESP_OK : ESP_FAIL;
}

static const struct board_sound_output output = {"esp_codec_dev_write", codec_write};

/* Frees what start made before it failed; esp_codec_dev_delete closes the device. */
static void sound_release(void)
{
    if (speaker) esp_codec_dev_delete(speaker);
    if (sound_codec) audio_codec_delete_codec_if(sound_codec);
    if (sound_ctrl) audio_codec_delete_ctrl_if(sound_ctrl);
    if (sound_gpio) audio_codec_delete_gpio_if(sound_gpio);
    if (sound_data) audio_codec_delete_data_if(sound_data);
    if (sound_tx_enabled) i2s_channel_disable(sound_tx);
    if (sound_tx) i2s_del_channel(sound_tx);
    speaker          = NULL;
    sound_codec      = NULL;
    sound_ctrl       = NULL;
    sound_gpio       = NULL;
    sound_data       = NULL;
    sound_tx_enabled = false;
    sound_tx         = NULL;
}

bool board_glue_sound_es8311_start(int index, const struct board_sound_es8311 *codec, board_sound_source_t source)
{
    if (speaker) return true;
    i2c_master_bus_handle_t i2c = board_glue_i2c();
    if (!i2c) {
        ESP_LOGE(TAG, "board_glue_i2c: no I2C bus for the codec");
        return false;
    }
    const struct board_i2s_bus *bus  = codec->i2s;
    i2s_chan_config_t           chan = I2S_CHANNEL_DEFAULT_CONFIG(bus->port, I2S_ROLE_MASTER);
    chan.dma_frame_num               = BOARD_SOUND_FRAMES;
    const i2s_std_config_t std       = {
              .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(codec->rate),
              .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
              .gpio_cfg = {.mclk = (gpio_num_t)bus->mclk, .bclk = (gpio_num_t)bus->bclk, .ws = (gpio_num_t)bus->ws, .dout = (gpio_num_t)bus->dout, .din = (gpio_num_t)bus->din},
    };
    esp_err_t err = i2s_new_channel(&chan, &sound_tx, NULL);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2s_new_channel: %s", esp_err_to_name(err));
        sound_tx = NULL;
        return false;
    }
    /* enabled before esp_codec_dev_open: it disables the channel to set the format and logs an error if it was never enabled */
    err = i2s_channel_init_std_mode(sound_tx, &std);
    if (err == ESP_OK) err = i2s_channel_enable(sound_tx);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2s_channel_enable: %s", esp_err_to_name(err));
        sound_release();
        return false;
    }
    sound_tx_enabled = true;
    sound_data       = audio_codec_new_i2s_data(&(audio_codec_i2s_cfg_t){.port = bus->port, .tx_handle = sound_tx});
    /* esp_codec_dev takes the 8-bit address */
    sound_ctrl = audio_codec_new_i2c_ctrl(&(audio_codec_i2c_cfg_t){.port = codec->i2c_port, .addr = codec->address << 1, .bus_handle = i2c});
    sound_gpio = audio_codec_new_gpio();
    es8311_codec_cfg_t es = {.ctrl_if = sound_ctrl, .gpio_if = sound_gpio, .codec_mode = ESP_CODEC_DEV_WORK_MODE_DAC, .pa_pin = codec->pa, .use_mclk = true};
    es.hw_gain.pa_voltage        = codec->pa_voltage;
    es.hw_gain.codec_dac_voltage = codec->codec_dac_voltage;
    sound_codec = sound_data && sound_ctrl && sound_gpio ? es8311_codec_new(&es) : NULL;
    speaker     = sound_codec ? esp_codec_dev_new(&(esp_codec_dev_cfg_t){.dev_type = ESP_CODEC_DEV_TYPE_OUT, .codec_if = sound_codec, .data_if = sound_data}) : NULL;
    esp_codec_dev_sample_info_t format = {.sample_rate = codec->rate, .channel = SOUND_CHANNELS, .bits_per_sample = SOUND_BITS};
    if (!speaker || esp_codec_dev_open(speaker, &format) != ESP_CODEC_DEV_OK) {
        ESP_LOGE(TAG, "esp_codec_dev_open: no ES8311");
        sound_release();
        return false;
    }
    esp_codec_dev_set_out_vol(speaker, codec->volume);
    if (!board_glue_sound_run(index, &output, codec->rate, source)) {
        sound_release();
        return false;
    }
    ESP_LOGI(TAG, "ES8311 at %lu Hz", (unsigned long)codec->rate);
    return true;
}
