/*
 * The numbers of the board's buses by name, from the table of the glue: a program that sets its
 * own hardware up takes the board's wiring from here.
 */
#include "board_glue.h"

#include <string.h>

bool board_bus_get(const char *bus, const char *field, long *out)
{
    for (size_t i = 0; i < board_bus_table.count; ++i) {
        const struct board_bus_field *entry = &board_bus_table.fields[i];
        if (strcmp(entry->bus, bus) == 0 && strcmp(entry->field, field) == 0) {
            if (out) *out = entry->value;
            return true;
        }
    }
    return false;
}
