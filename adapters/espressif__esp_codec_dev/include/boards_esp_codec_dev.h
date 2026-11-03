#pragma once

/*
 * The ES8311 of the board's sound as esp_codec_dev has it, for a board that has one
 * (CONFIG_BOARD_SOUND_ES8311). For a program that drives it itself: the device esp_codec_dev
 * made and opened by board_sound_init, at the rate it returned, 16 bits, mono. The program writes
 * with esp_codec_dev_write and sets the volume with esp_codec_dev_set_out_vol; it does not call
 * board_sound_start then, whose task writes to the same device.
 */
#include "boards.h"
#include "esp_codec_dev.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_codec_dev_handle_t board_esp_codec_dev(const board_sound_t *sound); /* NULL when this sound is not an ES8311 set up */

#ifdef __cplusplus
}
#endif
