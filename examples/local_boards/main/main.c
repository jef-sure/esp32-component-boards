/* A board of the program: the program asks for its parts by kind, as on a board of the catalog. */
#include <stdio.h>

#include "boards.h"
#include "boards_dgx.h"
#include "dgx_draw.h"

void app_main(void)
{
    const struct board_info *board = board_info();
    printf("the board: %s (%s), %s\n", board->title, board->name, board->target);

    struct board_display display = {0};
    if (!board_display_init(&display)) {
        printf("the display: none, or it could not be set up\n");
        return;
    }
    printf("the display: %d x %d pixels\n", display.width, display.height);
    dgx_screen_t *screen = board_dgx_screen(&display);
    dgx_fill_rectangle(screen, 0, 0, display.width, display.height, 0xffff);
    dgx_fill_rectangle(screen, 0, 0, display.width, display.height / 8, 0x001f);
}
