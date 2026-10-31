/* The touch panels of the board: each started once, on demand, from the table of the glue. */
#include "board_glue.h"

#include <string.h>

int board_touch_count(void)
{
    return board_touch_table.count;
}

bool board_touch_start_at(int index, const struct board_display *display, struct board_touch *out)
{
    if (index < 0 || index >= board_touch_table.count) return false;
    const struct board_touch_entry *entry   = &board_touch_table.entries[index];
    struct board_touch             *started = &board_touch_table.started[index];
    if (display && display->name && strcmp(display->name, entry->over) != 0) return false; /* the display it lies over */
    if (!started->name) {
        if (!entry->start(index, display, started)) return false;
        started->name  = entry->name;
        started->index = index;
    }
    if (out) *out = *started;
    return true;
}

bool board_touch_start(const struct board_display *display, struct board_touch *out)
{
    for (int i = 0; i < board_touch_table.count; ++i)
        if (board_touch_start_at(i, display, out)) return true;
    return false;
}
