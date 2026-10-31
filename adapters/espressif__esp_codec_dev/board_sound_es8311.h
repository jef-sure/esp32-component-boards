#pragma once

/* An ES8311 on the board's I2C bus, streaming over an I2S bus, through esp_codec_dev. */
#include "board_glue.h"

struct board_sound_es8311 {
    const struct board_i2s_bus *i2s;
    int                         i2c_port;
    int                         address;  /* 7 bits */
    int                         pa;       /* its amplifier's enable; GPIO_NUM_NC when none */
    float                       pa_voltage, codec_dac_voltage;
    int                         volume;   /* 0..100 */
    uint32_t                    rate;
};

bool board_glue_sound_es8311_start(int index, const struct board_sound_es8311 *codec, board_sound_source_t source);
