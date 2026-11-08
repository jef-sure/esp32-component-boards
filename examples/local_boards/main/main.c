/* A board of the program: the program asks for its parts by kind, as on a board of the catalog. */
#include <stdio.h>
#include <string.h>

#include "boards.h"
#include "boards_dgx.h"
#include "dgx_bits.h"
#include "dgx_colors.h"
#include "dgx_draw.h"
#include "sdkconfig.h"
#if CONFIG_BOARD_DISPLAY_HD44780
#include "boards_hd44780.h"
#endif

void app_main(void)
{
    const board_info_t *board = board_info();
    printf("the board: %s (%s), %s\n", board->title, board->name, board->target);

    board_character_display_t lcd;
    if (board_character_display_init(&lcd)) {
        printf("the character display: %d x %d\n", lcd.cols, lcd.rows);
#if CONFIG_BOARD_DISPLAY_HD44780
        /* the name of the board on its first row */
        lcd_set_cursor(board_hd44780(&lcd), 0, 0);
        lcd_write_strn(board_hd44780(&lcd), board->name, strnlen(board->name, (size_t)lcd.cols));
#endif
    }

    board_display_t display = {0};
    if (!board_display_init(&display)) {
        printf("the display: none, or it could not be set up\n");
        return;
    }
    printf("the display: %d x %d pixels\n", display.width, display.height);
    dgx_screen_t *screen = board_dgx_screen(&display);
    dgx_fill_rectangle(screen, 0, 0, display.width, display.height, DGX_WHITE(dgx_rgb_to_16));
    dgx_fill_rectangle(screen, 0, 0, display.width, display.height / 8, DGX_BLUE(dgx_rgb_to_16));
}
