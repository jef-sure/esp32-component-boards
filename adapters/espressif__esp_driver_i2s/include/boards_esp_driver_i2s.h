#pragma once

/*
 * The I2S channel of the board's sound, for an amplifier on I2S with no codec to set up
 * (CONFIG_BOARD_SOUND_I2S). For a program that writes its samples itself: the channel
 * board_sound_init made and enabled, at the rate it returned, 16 bits, mono, written with
 * i2s_channel_write. The program does not call board_sound_start then, whose task writes to
 * the same channel.
 */
#include "boards.h"
#include "driver/i2s_common.h"

#ifdef __cplusplus
extern "C" {
#endif

i2s_chan_handle_t board_i2s_channel(const board_sound_t *sound); /* NULL when this sound is not an I2S amplifier set up */

#ifdef __cplusplus
}
#endif
