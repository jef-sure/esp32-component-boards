#pragma once

/* An amplifier on I2S with no codec to set up. */
#include "board_glue.h"

/* The init of a board_sound_entry of the kind i2s. */
bool board_glue_sound_i2s_init(int index, const struct board_sound_entry *entry);
