/*
 * The core of the boards: what the chosen board is (its name, its target). The glue of the
 * board (boards/<board>/<board>.c, made by tools/boards_gen.py from its data) gives the data
 * and the parts; the program asks by kind (a display, a touch, a sound), never by the board's
 * name.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

const struct board_info *board_info(void)
{
    extern const struct board_data board_data; /* the glue of the chosen board */
    static struct board_info info;
    if (!info.name) info = (struct board_info){.name = board_data.name, .title = board_data.title, .target = board_data.target};
    return &info;
}
