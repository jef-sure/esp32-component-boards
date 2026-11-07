#include <stdio.h>

#include "boards.h"
#include "sdkconfig.h"
#if CONFIG_BOARD_DISPLAY_GRAPHICS
#include "boards_dgx.h"
#include "dgx_draw.h"
#endif

void app_main(void)
{
    const board_info_t *board = board_info();
    printf("the board: %s (%s), %s\n", board->title, board->name, board->target);

    /* Start every part before drawing. On an ESP32 both SPI hosts share one DMA, and board_touch_start sets up the
     * touch's host, which resets that DMA: a picture still being sent to the display would end in wrong pixels. */
    board_display_t display = {0};
    bool            shown   = board_display_init(&display);
    if (shown) printf("the display: %d x %d pixels, %d x %d mm\n", display.width, display.height, display.mm_w, display.mm_h);

    board_touch_t touch;
    if (board_touch_start(&display, &touch)) printf("the touch: %d fingers\n", touch.fingers);

    bool pressed;
    if (board_button(&pressed)) printf("the button: %s\n", pressed ? "held" : "free");

#if CONFIG_BOARD_DISPLAY_GRAPHICS
    if (shown) {
        dgx_screen_t *screen = board_dgx_screen(&display);
        dgx_fill_rectangle(screen, 0, 0, display.width, display.height, 0xffff);     /* white */
        dgx_fill_rectangle(screen, 0, 0, display.width, display.height / 8, 0x001f); /* a blue band at the top */
    }
#endif
}
