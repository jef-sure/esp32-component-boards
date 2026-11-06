/* The buttons of the computer: those of the board shown and of a gamepad, pressed by a script of DGX. */
#include <stdio.h>
#include <stdlib.h>

#include "boards.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

enum { WAIT_MS = 3000, WATCHED = 3 };

void app_main(void)
{
    board_display_t display;
    board_display_init(&display);
    printf("buttons: %d:", board_button_count());
    for (int i = 0; i < board_button_count(); ++i) printf(" %s", board_button_name(i));
    printf("\nfind boot %d, up %d, nope %d, name 99 %s\n", board_button_find("boot"), board_button_find("up"), board_button_find("nope"),
           board_button_name(99) ? "?" : "NULL");
    const char *watched[WATCHED] = {"boot", "up", "a"};
    bool        seen[WATCHED]    = {false};
    for (int t = 0; t < WAIT_MS / 10; ++t) {
        for (int w = 0; w < WATCHED; ++w) {
            bool pressed = false;
            if (board_button_at(board_button_find(watched[w]), &pressed) && pressed && !seen[w]) {
                seen[w] = true;
                printf("%s pressed at about %d ms\n", watched[w], t * 10);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    const bool all = seen[0] && seen[1] && seen[2];
    printf("%s\n", all ? "all pass" : "FAILED");
    exit(all ? EXIT_SUCCESS : EXIT_FAILURE);
}
