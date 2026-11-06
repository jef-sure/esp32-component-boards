/*
 * The board host: the program on the computer, built for the linux target of ESP-IDF, boards.h over SDL2. The display
 * is a window of DGX (dgx_host_screen_init, DGX 0.10.8 and later) as large as the display of the board it shows
 * (CONFIG_BOARD_HOST_*, written by tools/board_select.py host --as <board>), and the sound goes to the speakers of the
 * computer. The task that starts the display shows the window in its waits and needs 48 KB of stack left, as
 * CONFIG_ESP_MAIN_TASK_STACK_SIZE=16384 gives app_main. The touch panel is the mouse over the window, a finger of DGX-DI
 * (dgx_di_host.h, DGX-DI 0.1.5 and later); every part the computer has not returns false as on a board.
 */
#include "sdkconfig.h"

#if !CONFIG_BOARD_SELECT_HOST
#error "the linux target is the board host, a window of the computer: choose it with board_select.py host --as <board> ."
#endif

#include "boards.h"
#include "boards_dgx.h"
#include "boards_dgx_di.h"

#include <SDL.h>
#include <string.h>

#include "dgx_di_host.h"
#include "dgx_host_screen.h"
#include "drivers/dgx_panel.h"
#include "esp_log.h"

static const char *TAG = "board";

enum { COLOR_BITS = 16, SOUND_RATE = 22050, SOUND_FRAMES = 256 };

_Static_assert((int)DgxScreenLeftRight == BOARD_DIR_FORWARD && (int)DgxScreenTopBottom == BOARD_DIR_FORWARD && (int)DgxScreenRightLeft == BOARD_DIR_BACKWARD &&
                   (int)DgxScreenBottomTop == BOARD_DIR_BACKWARD,
               "dir_x and dir_y of boards.h are passed to DGX as they are");

const board_info_t *board_info(void)
{
    static const board_info_t info = {.name = "host", .title = "The computer, as " CONFIG_BOARD_HOST_SHOWS, .target = "linux"};
    return &info;
}

/* ---- the display: a window of DGX, its glass the display of the board as shown ---- */

static board_display_t shown;
static dgx_screen_t   *screen;

int board_display_count(void)
{
    return 1;
}

bool board_display_init_at(int index, board_display_t *out)
{
    if (index != 0) return false;
    if (!screen) {
        const dgx_host_screen_options_t options = {.title = board_info()->title};
        screen = dgx_host_screen_init(CONFIG_BOARD_HOST_WIDTH, CONFIG_BOARD_HOST_HEIGHT, COLOR_BITS, &options);
        if (!screen) {
            ESP_LOGE(TAG, "dgx_host_screen_init: %dx%d", CONFIG_BOARD_HOST_WIDTH, CONFIG_BOARD_HOST_HEIGHT);
            return false;
        }
        shown = (board_display_t){.width = CONFIG_BOARD_HOST_WIDTH, .height = CONFIG_BOARD_HOST_HEIGHT, .mm_w = CONFIG_BOARD_HOST_MM_W, .mm_h = CONFIG_BOARD_HOST_MM_H,
                                  .dir_x = BOARD_DIR_FORWARD, .dir_y = BOARD_DIR_FORWARD, .swap_xy = false, .name = "window", .index = 0};
    }
    if (out) *out = shown;
    return true;
}

bool board_display_init(board_display_t *out)
{
    return board_display_init_at(0, out);
}

bool board_display_orientation(board_display_t *display, int dir_x, int dir_y, bool swap_xy)
{
    if (!display || !screen) return false;
    dgx_panel_orientation(screen, (dgx_orientation_t)dir_x, (dgx_orientation_t)dir_y, swap_xy);
    display->dir_x   = dir_x;
    display->dir_y   = dir_y;
    display->swap_xy = swap_xy;
    display->width   = swap_xy ? CONFIG_BOARD_HOST_HEIGHT : CONFIG_BOARD_HOST_WIDTH;
    display->height  = swap_xy ? CONFIG_BOARD_HOST_WIDTH : CONFIG_BOARD_HOST_HEIGHT;
    display->mm_w    = swap_xy ? CONFIG_BOARD_HOST_MM_H : CONFIG_BOARD_HOST_MM_W;
    display->mm_h    = swap_xy ? CONFIG_BOARD_HOST_MM_W : CONFIG_BOARD_HOST_MM_H;
    shown            = *display;
    return true;
}

dgx_screen_t *board_dgx_screen(const board_display_t *display)
{
    return display && display->index == 0 ? screen : NULL;
}

dgx_bus_protocols_t *board_dgx_bus(const board_display_t *display)
{
    (void)display;
    return NULL; /* the bus of the window has nothing to tune */
}

bool board_character_display_init(board_character_display_t *out)
{
    (void)out;
    return false;
}

/* ---- the touch panel: the mouse over the window, a finger on its glass as DGX-DI reads it ---- */

static board_touch_t       touched;
static dgx_di_host_touch_t mouse;
static dgx_di_pointer_t    pointer;

int board_touch_count(void)
{
    return 1;
}

bool board_touch_start_at(int index, const board_display_t *display, board_touch_t *out)
{
    if (index != 0) return false;
    if (display && display->name && strcmp(display->name, shown.name) != 0) return false; /* the display it covers */
    if (!touched.name) {
        if (!screen) return false; /* a finger on the glass of the window: the display first */
        dgx_di_host_touch_init(&mouse, screen);
        dgx_di_pointer_init(&pointer, &mouse.device, 0, screen); /* the mouse lies by flags 0 and needs no calibration */
        touched = (board_touch_t){.fingers = mouse.device.fingers, .x_max = mouse.device.x_max, .y_max = mouse.device.y_max, .name = "mouse", .index = 0};
    }
    if (out) *out = touched;
    return true;
}

bool board_touch_start(const board_display_t *display, board_touch_t *out)
{
    return board_touch_start_at(0, display, out);
}

dgx_di_device_t *board_dgx_di_device(const board_touch_t *touch)
{
    return touch && touch->index == 0 && touched.name ? &mouse.device : NULL;
}

dgx_di_pointer_t *board_dgx_di_pointer(const board_touch_t *touch)
{
    return touch && touch->index == 0 && touched.name ? &pointer : NULL;
}

void board_touch_firmware_set(const uint8_t *start, size_t size)
{
    (void)start;
    (void)size;
}

/* ---- the sound: the audio thread of SDL asks the source, as the task of a board does ---- */

static SDL_AudioDeviceID    speaker;
static board_sound_source_t sound_source;
static void                *sound_ctx;

static void sound_fill(void *userdata, Uint8 *stream, int bytes)
{
    (void)userdata;
    int16_t *samples = (int16_t *)stream;
    size_t   count   = (size_t)bytes / sizeof(*samples);
    if (sound_source) sound_source(sound_ctx, samples, count);
    else SDL_memset(stream, 0, (size_t)bytes);
}

int board_sound_count(void)
{
    return 1;
}

bool board_sound_init_at(int index, board_sound_t *out)
{
    if (index != 0) return false;
    if (!speaker) {
        if (SDL_InitSubSystem(SDL_INIT_AUDIO) != 0) {
            ESP_LOGE(TAG, "SDL_InitSubSystem: %s", SDL_GetError());
            return false;
        }
        const SDL_AudioSpec want = {.freq = SOUND_RATE, .format = AUDIO_S16SYS, .channels = 1, .samples = SOUND_FRAMES, .callback = sound_fill};
        speaker                  = SDL_OpenAudioDevice(NULL, 0, &want, NULL, 0);
        if (!speaker) {
            ESP_LOGE(TAG, "SDL_OpenAudioDevice: %s", SDL_GetError());
            return false;
        }
    }
    if (out) *out = (board_sound_t){.rate = SOUND_RATE, .name = "speakers", .index = 0};
    return true;
}

bool board_sound_init(board_sound_t *out)
{
    return board_sound_init_at(0, out);
}

void board_sound_source_at(int index, board_sound_source_t source, void *ctx)
{
    if (index != 0 || !speaker) return;
    SDL_LockAudioDevice(speaker); /* the audio thread never takes a source with the context of another */
    sound_source = source;
    sound_ctx    = ctx;
    SDL_UnlockAudioDevice(speaker);
}

void board_sound_source(board_sound_source_t source, void *ctx)
{
    board_sound_source_at(0, source, ctx);
}

bool board_sound_start_at(int index, board_sound_source_t source, void *ctx, uint32_t *rate_out)
{
    board_sound_t sound;
    if (!board_sound_init_at(index, &sound)) return false;
    board_sound_source_at(index, source, ctx);
    SDL_PauseAudioDevice(speaker, 0);
    if (rate_out) *rate_out = sound.rate;
    return true;
}

bool board_sound_start(board_sound_source_t source, void *ctx, uint32_t *rate_out)
{
    return board_sound_start_at(0, source, ctx, rate_out);
}

/* ---- what the computer has not: buses of a chip, buttons ---- */

const board_spi_bus_t *board_spi_bus(int host)
{
    (void)host;
    return NULL;
}

bool board_spi_taken(int host)
{
    (void)host;
    return false;
}

struct i2c_master_bus_t *board_i2c(int port)
{
    (void)port;
    return NULL;
}

bool board_i2c_taken(int port)
{
    (void)port;
    return false;
}

bool board_bus_get(const char *bus, const char *field, long *out)
{
    (void)bus;
    (void)field;
    (void)out;
    return false;
}

int board_button_count(void)
{
    return 0;
}

const char *board_button_name(int index)
{
    (void)index;
    return NULL;
}

bool board_button(bool *pressed)
{
    (void)pressed;
    return false;
}

bool board_button_at(int index, bool *pressed)
{
    (void)index;
    (void)pressed;
    return false;
}
