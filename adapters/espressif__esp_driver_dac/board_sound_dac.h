#pragma once

/* The ESP32's own DAC. */
#include "board_glue.h"

struct board_sound_dac {
    int out; /* DAC_CH0_GPIO or DAC_CH1_GPIO */
    int pa;  /* its amplifier's enable; GPIO_NUM_NC when none */
};

/* The init of a board_sound_entry of the kind dac. */
bool board_glue_sound_dac_init(int index, const struct board_sound_entry *entry);
