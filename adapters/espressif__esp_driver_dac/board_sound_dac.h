#pragma once

/* The ESP32's own DAC. */
#include "board_glue.h"

bool board_glue_sound_dac_init(int index, int out, int pa, uint32_t rate);
