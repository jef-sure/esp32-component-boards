/* Graphics displays: each started once, on demand, from the table of the glue. */
#include "board_display.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "sdkconfig.h"

#if CONFIG_BOARD_DISPLAY_GROUP
#include "drivers/vscreen_2h.h"
#endif

static const char *TAG = "board";

_Static_assert((int)DgxScreenLeftRight == BOARD_DIR_FORWARD && (int)DgxScreenTopBottom == BOARD_DIR_FORWARD && (int)DgxScreenRightLeft == BOARD_DIR_BACKWARD &&
                   (int)DgxScreenBottomTop == BOARD_DIR_BACKWARD,
               "dir_x and dir_y of boards.h are passed to DGX as they are");

static void keep_orientation(const struct board_display_panel *panel, struct board_display *d, int dir_x, int dir_y, bool swap_xy)
{
    d->dir_x   = dir_x;
    d->dir_y   = dir_y;
    d->swap_xy = swap_xy;
    d->width   = swap_xy ? panel->glass_h : panel->glass_w;
    d->height  = swap_xy ? panel->glass_w : panel->glass_h;
    d->mm_w    = swap_xy ? panel->mm_h : panel->mm_w;
    d->mm_h    = swap_xy ? panel->mm_w : panel->mm_h;
}

static bool start_panel(const struct board_display_panel *panel, struct board_display_started *d)
{
    dgx_bus_protocols_t *bus = panel->bus();
    if (!bus) return false;
    dgx_screen_t *screen = panel->screen(bus);
    if (!screen) {
        bus->dispose(bus);
        return false;
    }
    panel->orientation(screen, (dgx_orientation_t)panel->dir_x, (dgx_orientation_t)panel->dir_y, panel->swap_xy);
    if (panel->backlight != GPIO_NUM_NC) {
        /* the light goes on over a black frame buffer, not over what the panel had before */
        gpio_set_direction((gpio_num_t)panel->backlight, GPIO_MODE_OUTPUT);
        gpio_set_level((gpio_num_t)panel->backlight, panel->backlight_on);
    }
    d->screen = screen;
    d->bus    = bus;
    keep_orientation(panel, &d->shown, panel->dir_x, panel->dir_y, panel->swap_xy);
    return true;
}

static bool start_group(const struct board_display_panel *panel, struct board_display_started *d)
{
#if CONFIG_BOARD_DISPLAY_GROUP
    struct board_display left, right;
    if (!board_display_init_at(panel->left, &left) || !board_display_init_at(panel->right, &right)) return false;
    dgx_screen_t *screen = dgx_vscreen_2h_init(board_dgx_screen(&left), board_dgx_screen(&right));
    if (!screen) {
        ESP_LOGE(TAG, "dgx_vscreen_2h_init: %s", panel->name);
        return false;
    }
    d->screen        = screen;
    d->shown.width   = left.width + right.width;
    d->shown.height  = left.height > right.height ? left.height : right.height;
    d->shown.mm_w    = left.mm_w + right.mm_w;
    d->shown.mm_h    = left.mm_h > right.mm_h ? left.mm_h : right.mm_h;
    d->shown.dir_x   = BOARD_DIR_FORWARD;
    d->shown.dir_y   = BOARD_DIR_FORWARD;
    d->shown.swap_xy = false;
    return true;
#else
    ESP_LOGE(TAG, "%s: a group of displays in a build without it", panel->name);
    return false;
#endif
}

int board_display_count(void)
{
    return board_display_table.count;
}

bool board_display_init_at(int index, struct board_display *out)
{
    if (!out || index < 0 || index >= board_display_table.count) return false;
    const struct board_display_panel *panel = &board_display_table.panels[index];
    struct board_display_started     *d     = &board_display_table.started[index];
    if (!d->screen) {
        if (!(panel->group ? start_group(panel, d) : start_panel(panel, d))) return false;
        d->shown.name  = panel->name;
        d->shown.index = index;
    }
    *out = d->shown;
    return true;
}

bool board_display_init(struct board_display *out)
{
    return board_display_init_at(0, out);
}

bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy)
{
    dgx_screen_t *screen = board_dgx_screen(display);
    if (!screen) return false;
    const struct board_display_panel *panel = &board_display_table.panels[display->index];
    if (panel->group) return false; /* the members keep theirs */
    panel->orientation(screen, (dgx_orientation_t)dir_x, (dgx_orientation_t)dir_y, swap_xy);
    keep_orientation(panel, display, dir_x, dir_y, swap_xy);
    board_display_table.started[display->index].shown = *display;
    return true;
}

static const struct board_display_started *started_of(const struct board_display *display)
{
    return display && display->index >= 0 && display->index < board_display_table.count ? &board_display_table.started[display->index] : NULL;
}

dgx_screen_t *board_dgx_screen(const struct board_display *display)
{
    const struct board_display_started *d = started_of(display);
    return d ? d->screen : NULL;
}

dgx_bus_protocols_t *board_dgx_bus(const struct board_display *display)
{
    const struct board_display_started *d = started_of(display);
    return d ? d->bus : NULL;
}
