/*
 * The pointer of DGX-DI the touch of the board is read through: one, of the core, the touch
 * panel of the chosen board is set up on it. Compiled only when the chosen board has a touch
 * (BOARD_TOUCH, the symbol the rules of idf_component.yml bring dgx-di in on): a board
 * without one does not pull dgx-di for nothing.
 */
#include "board_glue.h"

#include "sdkconfig.h"

#if CONFIG_BOARD_TOUCH

#include "dgx_di.h"

void *board_glue_pointer(void)
{
    static dgx_di_pointer_t pointer;
    return &pointer;
}

#endif
