#pragma once

/* An amplifier on I2S with no codec to set up. */
#include "board_glue.h"

bool board_glue_sound_i2s_start(int index, const struct board_i2s_bus *bus, uint32_t rate, board_sound_source_t source);
