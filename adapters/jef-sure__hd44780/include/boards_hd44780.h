#pragma once

/* A character display of boards.h as hd44780 has it. Compiled in when a character display is there (CONFIG_BOARD_DISPLAY_HD44780). */
#include "boards.h"
#include "hd44780.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The display, for lcd_set_cursor, lcd_write_str and the rest of hd44780.h. NULL before board_character_display_init. */
hd44780_t *board_hd44780(const struct board_character_display *display);

#ifdef __cplusplus
}
#endif
