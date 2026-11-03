#pragma once

/*
 * The DAC of the board's sound, the ESP32's own (CONFIG_BOARD_SOUND_DAC). For a program that
 * writes its samples itself: the channel board_sound_init made and enabled, at the rate it
 * returned, 8 bits a sample, written with dac_continuous_write. The program does not call
 * board_sound_start then, whose task writes to the same channel.
 */
#include "boards.h"
#include "driver/dac_continuous.h"

#ifdef __cplusplus
extern "C" {
#endif

dac_continuous_handle_t board_dac_continuous(const board_sound_t *sound); /* NULL when this sound is not the DAC set up */

#ifdef __cplusplus
}
#endif
