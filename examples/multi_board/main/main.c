/*
 * One program for several boards: it asks for its board by kind and draws on whatever display the board has, and
 * CMake knows the size of that display before the build (BOARD_PIXELS, BOARD_MM). The same file builds for the CYD
 * S028R, an ESP32 with a 320x240 panel on SPI, and the JC8012P4A1C, an ESP32-P4 with a 1280x800 panel on MIPI-DSI.
 */
#include <stdio.h>

#include "boards.h"
#include "sdkconfig.h"

#if CONFIG_BOARD_DISPLAY_GRAPHICS
#include "boards_dgx.h"
#include "dgx_bits.h"
#include "dgx_colors.h"
#include "dgx_draw.h"
#endif

void app_main(void)
{
    const board_info_t *board = board_info();
    printf("the board: %s (%s), %s\n", board->title, board->name, board->target);
    board_display_t display;
    if (!board_display_init(&display)) {
        printf("the display: none\n");
        return;
    }
    printf("the display: %d x %d pixels, %d x %d mm\n", display.width, display.height, display.mm_w, display.mm_h);
#if CONFIG_BOARD_DISPLAY_GRAPHICS
    dgx_screen_t *screen = board_dgx_screen(&display);
    dgx_fill_rectangle(screen, 0, 0, display.width, display.height, DGX_WHITE(dgx_rgb_to_16));
    dgx_fill_rectangle(screen, 0, 0, display.width, display.height / 8, DGX_BLUE(dgx_rgb_to_16));
#endif
}
