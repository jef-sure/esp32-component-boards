/*
 * The table of the Ethernet when the glue gives none, as the glue of a board of the program made by a component from before
 * it started Ethernet: weak, so a glue that defines it wins. It lies apart from board_ethernet.c, where a weak value in the
 * same file could be taken as the one.
 */
#include "board_glue.h"

__attribute__((weak)) const struct board_ethernet_table board_ethernet_table = {.count = 0};
