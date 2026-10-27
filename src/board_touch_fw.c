/*
 * The firmware of the touch panel of the board (a GSL3680 keeps none of its own): the program
 * that builds for a board with such a panel embeds it (DGX-DI's tools/gsl_firmware.py makes
 * the file from the board's package; the vendor's array carries no licence to give away) and
 * defines board_touch_firmware itself, giving the embedded bytes. A build that does not leaves
 * this weak one, and the touch of that board is off: board_touch_start tells so, the rest of
 * the board works.
 *
 * Weak here and strong in the program is safe across the two archives: whichever the linker
 * meets first, the strong one wins. Inside this component nothing is weak: the glue of a board
 * defines every function of boards.h itself.
 */
#include "boards.h"

__attribute__((weak)) bool board_touch_firmware(const uint8_t **start, size_t *size)
{
    (void)start;
    (void)size;
    return false;
}
