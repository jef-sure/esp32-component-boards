/* A button of the board by its name, as its data names it: a button that controls a program has a name of a gamepad. */
#include <string.h>

#include "boards.h"

int board_button_find(const char *name)
{
    for (int i = 0; name && i < board_button_count(); ++i)
        if (strcmp(board_button_name(i), name) == 0) return i;
    return -1;
}
