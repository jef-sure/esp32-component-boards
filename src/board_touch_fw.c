/*
 * The firmware of the touch panel of the board (a GSL3680 keeps none of its own): the program that
 * builds for a board with such a panel embeds it (DGX-DI's tools/gsl_firmware.py makes the file from
 * the board's package; the vendor's array carries no licence to give away) and gives it here before
 * board_touch_start. A program that does not leaves the touch of that board off: board_touch_start
 * says so, the rest of the board works.
 *
 * A call, not a weak function the program redefines: a strong definition in a file the program
 * links by nothing else loses to the weak one of the component, and the touch would stay off with
 * no word.
 */
#include "board_glue.h"

static const uint8_t *firmware_start;
static size_t         firmware_size;

void board_touch_firmware_set(const uint8_t *start, size_t size)
{
    firmware_start = size ? start : NULL;
    firmware_size  = start ? size : 0;
}

bool board_glue_touch_firmware(const uint8_t **start, size_t *size)
{
    if (!firmware_start) return false;
    *start = firmware_start;
    *size  = firmware_size;
    return true;
}
