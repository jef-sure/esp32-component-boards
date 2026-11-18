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
    const struct board_spi_bus *host;         /* an SPI host it shares with other parts, set up here first; NULL when it has its own */
    dgx_bus_protocols_t *(*bus)(void);
    int i2c_port;                                                /* the port of its I2C bus, when on_i2c is set */
    dgx_bus_protocols_t *(*on_i2c)(i2c_master_bus_handle_t i2c); /* a display on the board's I2C bus, instead of bus */
    dgx_screen_t *(*screen)(dgx_bus_protocols_t *bus);
    void (*orientation)(dgx_screen_t *scr, dgx_orientation_t dir_x, dgx_orientation_t dir_y, bool swap_xy); /* NULL when the driver cannot turn it */
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

#if BOARDS_VERSION_JEF_SURE__DGX >= BOARDS_VERSION(0, 11, 1)
/* dgx_screen_orientation(), which turns every display since DGX 0.11.1, in the form orientation of a panel takes: a driver
 * with no call of its own to turn it, as the ST7701, is turned by this, and its error goes to the log. */
void board_glue_screen_orientation(dgx_screen_t *scr, dgx_orientation_t dir_x, dgx_orientation_t dir_y, bool swap_xy);
#endif
