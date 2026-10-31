#pragma once

/* Graphics displays: the glue gives a table of them, board_display.c starts them on demand. */
#include "board_glue.h"
#include "boards_dgx.h"

struct board_display_panel {
    const char *name;
    int         glass_w, glass_h, mm_w, mm_h; /* as the controller scans the glass */
    int         dir_x, dir_y;                 /* how the board shows it */
    bool        swap_xy;
    int         backlight, backlight_on;      /* lit here after the driver starts; GPIO_NUM_NC when the driver does it */
    dgx_bus_protocols_t *(*bus)(void);
    dgx_screen_t *(*screen)(dgx_bus_protocols_t *bus);
    void (*orientation)(dgx_screen_t *scr, dgx_orientation_t dir_x, dgx_orientation_t dir_y, bool swap_xy);
    bool group;       /* two entries of this table shown as one screen, dgx_vscreen_2h_init(left, right) */
    int  left, right;
};

/* A display that is up: what the program sees and the handles of DGX. */
struct board_display_started {
    struct board_display shown;
    dgx_screen_t        *screen;
    dgx_bus_protocols_t *bus;
};

struct board_display_table {
    const struct board_display_panel *panels;  /* the primary first */
    struct board_display_started     *started; /* one for each panel */
    int                               count;
};
extern const struct board_display_table board_display_table;
