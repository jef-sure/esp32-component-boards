/*
 * The board host: the program on the computer, built for the linux target of ESP-IDF, boards.h over SDL2. The window is
 * as large as the board it shows (CONFIG_BOARD_HOST_*, written by tools/board_select.py host --as <board>), and the
 * sound goes to the speakers of the computer. What needs a library on the computer too (a screen of DGX in the window,
 * the mouse as a finger of DGX-DI) waits for those libraries to build for the linux target; until then the window is
 * black, the board has no touch panel, and every part it has not returns false as on a board.
 */
#include "boards.h"

#include <SDL.h>
#include <stdlib.h>
#include <time.h>

#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

#if !CONFIG_BOARD_SELECT_HOST
#error "the linux target is the board host, a window of the computer: choose it with board_select.py host --as <board> ."
#endif

static const char *TAG = "board";

enum { WINDOW_TASK_STACK = 8192, WINDOW_TASK_PRIORITY = 5, EVENTS_MS = 16, SOUND_RATE = 22050, SOUND_FRAMES = 256 };

/* esp_timer of ESP-IDF is only a header on the linux target: the board gives its time */
int64_t esp_timer_get_time(void)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (int64_t)now.tv_sec * 1000000 + now.tv_nsec / 1000;
}

const board_info_t *board_info(void)
{
    static const board_info_t info = {.name = "host", .title = "The computer, as " CONFIG_BOARD_HOST_SHOWS, .target = "linux"};
    return &info;
}

/* ---- the window: made by a task of its own, which reads the events of SDL as long as it is there ---- */

static board_display_t   shown;
static volatile int      window_state; /* 0 none yet, 1 made, -1 failed */
static SDL_Window       *window;

static void window_task(void *arg)
{
    (void)arg;
    if (SDL_InitSubSystem(SDL_INIT_VIDEO) != 0) {
        ESP_LOGE(TAG, "SDL_InitSubSystem: %s", SDL_GetError());
        window_state = -1;
        vTaskDelete(NULL);
        return;
    }
    window = SDL_CreateWindow(board_info()->title, SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, CONFIG_BOARD_HOST_WIDTH, CONFIG_BOARD_HOST_HEIGHT, 0);
    if (!window) {
        ESP_LOGE(TAG, "SDL_CreateWindow: %s", SDL_GetError());
        window_state = -1;
        vTaskDelete(NULL);
        return;
    }
    window_state = 1;
    for (;;) {
        SDL_Event event;
        while (SDL_PollEvent(&event))
            if (event.type == SDL_QUIT) exit(0); /* the window closed: the program ends, as a board switched off */
        vTaskDelay(pdMS_TO_TICKS(EVENTS_MS));
    }
}

int board_display_count(void)
{
    return 1;
}

bool board_display_init_at(int index, board_display_t *out)
{
    if (index != 0) return false;
    if (!window_state && xTaskCreate(window_task, "window", WINDOW_TASK_STACK, NULL, WINDOW_TASK_PRIORITY, NULL) != pdPASS) {
        ESP_LOGE(TAG, "xTaskCreate: window");
        return false;
    }
    while (!window_state) vTaskDelay(1);
    if (window_state < 0) return false;
    shown = (board_display_t){.width = CONFIG_BOARD_HOST_WIDTH, .height = CONFIG_BOARD_HOST_HEIGHT, .mm_w = CONFIG_BOARD_HOST_MM_W, .mm_h = CONFIG_BOARD_HOST_MM_H,
                              .dir_x = BOARD_DIR_FORWARD, .dir_y = BOARD_DIR_FORWARD, .swap_xy = false, .name = "window", .index = 0};
    if (out) *out = shown;
    return true;
}

bool board_display_init(board_display_t *out)
{
    return board_display_init_at(0, out);
}

bool board_display_orientation(board_display_t *display, int dir_x, int dir_y, bool swap_xy)
{
    if (!display || window_state <= 0) return false;
    if (swap_xy != display->swap_xy) {
        int width   = display->width;
        int mm_w    = display->mm_w;
        display->width  = display->height;
        display->height = width;
        display->mm_w   = display->mm_h;
        display->mm_h   = mm_w;
    }
    display->dir_x   = dir_x;
    display->dir_y   = dir_y;
    display->swap_xy = swap_xy;
    return true;
}

bool board_character_display_init(board_character_display_t *out)
{
    (void)out;
    return false;
}

/* ---- the touch panel: the mouse as a finger once DGX-DI builds for the computer ---- */

int board_touch_count(void)
{
    return 0;
}

bool board_touch_start(const board_display_t *display, board_touch_t *out)
{
    (void)display;
    (void)out;
    return false;
}

bool board_touch_start_at(int index, const board_display_t *display, board_touch_t *out)
{
    (void)index;
    (void)display;
    (void)out;
    return false;
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
