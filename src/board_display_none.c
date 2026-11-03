/*
 * The functions of a display the board has not, returning false, so that the same program links
 * and runs on every board. A pixel display has them from the adapter of its library
 * (CONFIG_BOARD_DISPLAY_GRAPHICS), a character display from the glue of its board or module
 * (CONFIG_BOARD_DISPLAY_HD44780).
 */
#include "boards.h"

#include "sdkconfig.h"

#if !CONFIG_BOARD_DISPLAY_GRAPHICS
int board_display_count(void)
{
    return 0;
}

bool board_display_init(struct board_display *out)
{
    (void)out;
    return false;
}

bool board_display_init_at(int index, struct board_display *out)
{
    (void)index;
    (void)out;
    return false;
}

bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy)
{
    (void)display;
    (void)dir_x;
    (void)dir_y;
    (void)swap_xy;
    return false;
}
#endif

#if !CONFIG_BOARD_DISPLAY_HD44780
bool board_character_display_init(struct board_character_display *out)
{
    (void)out;
    return false;
}
#endif
