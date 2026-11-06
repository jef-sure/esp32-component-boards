/*
 * The board host: the program on the computer, built for the linux target of ESP-IDF, boards.h over SDL2. The display
 * is a window of DGX (dgx_host_screen_init, DGX 0.10.10 and later): the glass of the display of the board it shows, turned
 * as the board is held, its screen at the orientation it starts with there, the time on the bus of that board in the
 * title (CONFIG_BOARD_HOST_*, written by tools/board_select.py host --as <board>); the sound goes to the speakers of the
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
#include "board_volume.h"

#include <SDL.h>
#include <ctype.h>
#include <stdlib.h>
#include <string.h>

#include "dgx_di_host.h"
#ifdef BOARDS_HOST_FLASH
#include <errno.h>
#include <stdio.h>
#include <unistd.h>

#include "esp_private/partition_linux.h"
#endif
#include "dgx_host_screen.h"
#include "drivers/dgx_panel.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

static const char *TAG = "board";

enum { SOUND_RATE = 22050, SOUND_FRAMES = 256, SOUND_AHEAD = 4, SOUND_TASK_PRIORITY = 6 };

_Static_assert((int)DgxScreenLeftRight == BOARD_DIR_FORWARD && (int)DgxScreenTopBottom == BOARD_DIR_FORWARD && (int)DgxScreenRightLeft == BOARD_DIR_BACKWARD &&
                   (int)DgxScreenBottomTop == BOARD_DIR_BACKWARD,
               "dir_x and dir_y of boards.h are passed to DGX as they are");

const board_info_t *board_info(void)
{
    static const board_info_t info = {.name = "host", .title = "The computer, as " CONFIG_BOARD_HOST_SHOWS, .target = "linux"};
    return &info;
}

/* ---- the display: a window of DGX, the glass of the board turned as the board is held, its screen as it starts there ---- */

/* the glass upright, before the orientation of the screen on it (CONFIG_BOARD_HOST_SWAP exchanges the sides) */
#define GLASS_W    (CONFIG_BOARD_HOST_SWAP ? CONFIG_BOARD_HOST_HEIGHT : CONFIG_BOARD_HOST_WIDTH)
#define GLASS_H    (CONFIG_BOARD_HOST_SWAP ? CONFIG_BOARD_HOST_WIDTH : CONFIG_BOARD_HOST_HEIGHT)
#define GLASS_MM_W (CONFIG_BOARD_HOST_SWAP ? CONFIG_BOARD_HOST_MM_H : CONFIG_BOARD_HOST_MM_W)
#define GLASS_MM_H (CONFIG_BOARD_HOST_SWAP ? CONFIG_BOARD_HOST_MM_W : CONFIG_BOARD_HOST_MM_H)

static board_display_t shown;
static dgx_screen_t   *screen;

/* what a display reports of its orientation, as keep_orientation of the adapter of DGX does on a board */
static void keep_orientation(board_display_t *display, int dir_x, int dir_y, bool swap_xy)
{
    display->dir_x   = dir_x;
    display->dir_y   = dir_y;
    display->swap_xy = swap_xy;
    display->width   = swap_xy ? GLASS_H : GLASS_W;
    display->height  = swap_xy ? GLASS_W : GLASS_H;
    display->mm_w    = swap_xy ? GLASS_MM_H : GLASS_MM_W;
    display->mm_h    = swap_xy ? GLASS_MM_W : GLASS_MM_H;
}

static void sound_end_set(void);

int board_display_count(void)
{
    return 1;
}

bool board_display_init_at(int index, board_display_t *out)
{
    if (index != 0) return false;
    if (!screen) {
        /* a display not on SPI or QSPI has no bus the window counts */
        const dgx_host_screen_options_t options = {.title     = board_info()->title,
                                                   .bus_hz    = CONFIG_BOARD_HOST_BUS_HZ,
                                                   .bus_lines = CONFIG_BOARD_HOST_BUS_LINES,
                                                   .turn      = CONFIG_BOARD_HOST_TURN,
                                                   .no_bus    = CONFIG_BOARD_HOST_BUS_HZ == 0};
        screen = dgx_host_screen_init(GLASS_W, GLASS_H, CONFIG_BOARD_HOST_COLOR_BITS, &options);
        if (!screen) {
            ESP_LOGE(TAG, "dgx_host_screen_init: %dx%d", GLASS_W, GLASS_H);
            return false;
        }
        sound_end_set();
        dgx_panel_orientation(screen, (dgx_orientation_t)CONFIG_BOARD_HOST_DIR_X, (dgx_orientation_t)CONFIG_BOARD_HOST_DIR_Y, CONFIG_BOARD_HOST_SWAP);
        shown = (board_display_t){.name = "window", .index = 0};
        keep_orientation(&shown, CONFIG_BOARD_HOST_DIR_X, CONFIG_BOARD_HOST_DIR_Y, CONFIG_BOARD_HOST_SWAP);
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
    keep_orientation(display, dir_x, dir_y, swap_xy);
    shown = *display;
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
    if (index != 0 || !screen) return false; /* a finger on the glass of the window: the display first */
    if (display && display->name && strcmp(display->name, shown.name) != 0) return false; /* the display it covers */
    if (!touched.name) {
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

/* ---- the sound: a task asks the source, as on a board, and queues what it gives for the speakers of the computer ---- */

static SDL_AudioDeviceID    speaker;
static SemaphoreHandle_t    sound_busy; /* held across the source and the queue: a change of source waits for the task */
static board_sound_source_t sound_source;
static void                *sound_ctx;
static bool                 sound_running;
static bool                 sound_ends_first; /* sound_end runs before the end of the window of DGX */

static void sound_task(void *arg)
{
    (void)arg;
    static int16_t samples[SOUND_FRAMES];
    for (;;) {
        xSemaphoreTakeRecursive(sound_busy, portMAX_DELAY);
        /* what SDL has not played yet stays near SOUND_AHEAD blocks */
        const bool full = SDL_GetQueuedAudioSize(speaker) > SOUND_AHEAD * sizeof(samples);
        if (!full) {
            if (sound_source) sound_source(sound_ctx, samples, SOUND_FRAMES);
            else memset(samples, 0, sizeof(samples));
            if (SDL_QueueAudio(speaker, samples, sizeof(samples)) != 0) ESP_LOGE(TAG, "SDL_QueueAudio: %s", SDL_GetError());
        }
        xSemaphoreGiveRecursive(sound_busy);
        if (full) vTaskDelay(1);
    }
}

/* At the end of the program the device is closed with the task kept out of SDL for good: before the end of the window,
 * whose SDL_Quit would close it under the task. The handlers of atexit run last first, so it is set again once there
 * is a window; a second run does nothing. */
static void sound_end(void)
{
    xSemaphoreTakeRecursive(sound_busy, portMAX_DELAY);
    if (speaker) SDL_CloseAudioDevice(speaker);
    speaker = 0;
}

static void sound_end_set(void)
{
    if (!sound_running || sound_ends_first) return;
    atexit(sound_end);
    sound_ends_first = screen != NULL;
}

int board_sound_count(void)
{
    return 1;
}

bool board_sound_init_at(int index, board_sound_t *out)
{
    if (index != 0) return false;
    if (!sound_busy && !(sound_busy = xSemaphoreCreateRecursiveMutex())) {
        ESP_LOGE(TAG, "xSemaphoreCreateRecursiveMutex: sound");
        return false;
    }
    xSemaphoreTakeRecursive(sound_busy, portMAX_DELAY);
    if (!speaker) {
        const SDL_AudioSpec want = {.freq = SOUND_RATE, .format = AUDIO_S16SYS, .channels = 1, .samples = SOUND_FRAMES};
        if (SDL_InitSubSystem(SDL_INIT_AUDIO) != 0) ESP_LOGE(TAG, "SDL_InitSubSystem: %s", SDL_GetError());
        else if (!(speaker = SDL_OpenAudioDevice(NULL, 0, &want, NULL, 0))) ESP_LOGE(TAG, "SDL_OpenAudioDevice: %s", SDL_GetError());
    }
    const bool ready = speaker != 0;
    xSemaphoreGiveRecursive(sound_busy);
    /* the data has no level for the speakers of the computer: only one kept */
    if (ready && out) *out = (board_sound_t){.rate = SOUND_RATE, .mixer_volume = board_volume_kept(0, 0), .name = "speakers", .index = 0};
    return ready;
}

bool board_sound_init(board_sound_t *out)
{
    return board_sound_init_at(0, out);
}

/* the source of the task and its context, as one; a source may change itself, the lock being recursive */
void board_sound_source_at(int index, board_sound_source_t source, void *ctx)
{
    if (index != 0 || !sound_busy) return;
    xSemaphoreTakeRecursive(sound_busy, portMAX_DELAY);
    sound_source = source;
    sound_ctx    = ctx;
    xSemaphoreGiveRecursive(sound_busy);
}

void board_sound_source(board_sound_source_t source, void *ctx)
{
    board_sound_source_at(0, source, ctx);
}

bool board_sound_start_at(int index, board_sound_source_t source, void *ctx, uint32_t *rate_out)
{
    if (!board_sound_init_at(index, NULL)) return false;
    xSemaphoreTakeRecursive(sound_busy, portMAX_DELAY);
    board_sound_source_at(index, source, ctx);
    if (!sound_running) {
        sound_running = xTaskCreate(sound_task, "sound", CONFIG_BOARD_SOUND_TASK_STACK, NULL, SOUND_TASK_PRIORITY, NULL) == pdPASS;
        if (!sound_running) ESP_LOGE(TAG, "xTaskCreate: sound");
        else SDL_PauseAudioDevice(speaker, 0);
        sound_end_set();
    }
    const bool running = sound_running;
    xSemaphoreGiveRecursive(sound_busy);
    if (running && rate_out) *rate_out = SOUND_RATE;
    return running;
}

bool board_sound_start(board_sound_source_t source, void *ctx, uint32_t *rate_out)
{
    return board_sound_start_at(0, source, ctx, rate_out);
}

/* ---- the flash: kept in the build directory between runs, as a board keeps its own ---- */

#ifdef BOARDS_HOST_FLASH
/* The linux target maps the flash to a new file in /tmp at each run and leaves it there: NVS forgets what it kept. Here the
 * flash is BOARDS_HOST_FLASH of the build directory while its partition table is that of the build; the first run starts
 * from a new file and keeps it at its end. Removing the file erases the flash. */
enum { FLASH_TABLE_MAX = 0x1000, FLASH_COPY_BYTES = 65536 };

/* the partition table in the flash kept is the build's */
static bool flash_table_same(void)
{
    static uint8_t table[FLASH_TABLE_MAX], kept[FLASH_TABLE_MAX];
    FILE          *built = fopen(BOARDS_HOST_TABLE, "rb");
    FILE          *flash = fopen(BOARDS_HOST_FLASH, "rb");
    size_t         size  = built ? fread(table, 1, sizeof(table), built) : 0;
    const bool     same  = size && flash && fseek(flash, CONFIG_PARTITION_TABLE_OFFSET, SEEK_SET) == 0 && fread(kept, 1, size, flash) == size &&
                      memcmp(table, kept, size) == 0;
    if (built) fclose(built);
    if (flash) fclose(flash);
    return same;
}

/* the flash a first run made in /tmp, copied into the build directory and removed */
static void flash_keep(void)
{
    const char *made = esp_partition_get_file_mmap_ctrl_act()->flash_file_name;
    if (!made[0] || strcmp(made, BOARDS_HOST_FLASH) == 0) return; /* no flash used, or the kept one */
    static uint8_t piece[FLASH_COPY_BYTES];
    FILE          *from = fopen(made, "rb");
    FILE          *to   = fopen(BOARDS_HOST_FLASH ".new", "wb");
    bool           done = from && to;
    for (size_t n; done && (n = fread(piece, 1, sizeof(piece), from)) > 0;) done = fwrite(piece, 1, n, to) == n;
    if (from) fclose(from);
    if (to && fclose(to) != 0) done = false;
    if (done && rename(BOARDS_HOST_FLASH ".new", BOARDS_HOST_FLASH) == 0) unlink(made);
    else ESP_LOGE(TAG, "the flash %s not kept as %s: %s", made, BOARDS_HOST_FLASH, strerror(errno));
}

__attribute__((constructor)) static void flash_kept(void)
{
    atexit(flash_keep);
    if (access(BOARDS_HOST_FLASH, F_OK) != 0) return;
    if (!flash_table_same()) {
        ESP_LOGW(TAG, "%s has another partition table than the build: the flash starts empty, the old one is kept with .old", BOARDS_HOST_FLASH);
        rename(BOARDS_HOST_FLASH, BOARDS_HOST_FLASH ".old");
        return;
    }
    snprintf(esp_partition_get_file_mmap_ctrl_input()->flash_file_name, PATH_MAX, "%s", BOARDS_HOST_FLASH);
}
#endif

/* ---- what the computer has not: buses of a chip ---- */

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

/* ---- the buttons: those of the board shown and those of a gamepad, keys of the computer ---- */

/* The keys come from the window of DGX (dgx_host_keys, DGX 0.10.11), a stand-in until input has a place of its own: asked
 * here alone. A button of the board shown named as one of a gamepad is on its keys, another on the key of its first
 * letter (boot on B); then come the buttons of the gamepad the board has not. */
enum { BUTTONS_MAX = 16, BUTTON_KEYS = 2, KEYS_HELD_MAX = 16 };
struct host_button {
    const char *name;
    uint16_t    keys[BUTTON_KEYS]; /* SDL_Scancode, the numbers of USB HID; 0 for none */
};
static const struct host_button gamepad[] = {
    {"up", {SDL_SCANCODE_W, SDL_SCANCODE_UP}},     {"left", {SDL_SCANCODE_A, SDL_SCANCODE_LEFT}},     {"down", {SDL_SCANCODE_S, SDL_SCANCODE_DOWN}},
    {"right", {SDL_SCANCODE_D, SDL_SCANCODE_RIGHT}}, {"a", {SDL_SCANCODE_SPACE, SDL_SCANCODE_J}},     {"b", {SDL_SCANCODE_K, SDL_SCANCODE_BACKSPACE}},
    {"start", {SDL_SCANCODE_RETURN}},             {"select", {SDL_SCANCODE_TAB}},
};
enum { GAMEPAD_BUTTONS = sizeof(gamepad) / sizeof(gamepad[0]) };
static struct host_button buttons[BUTTONS_MAX];
static char               button_names[] = CONFIG_BOARD_HOST_BUTTONS; /* cut into names by commas, once */
static int                button_count;

static const struct host_button *gamepad_button(const char *name)
{
    for (int i = 0; i < GAMEPAD_BUTTONS; ++i)
        if (strcmp(gamepad[i].name, name) == 0) return &gamepad[i];
    return NULL;
}

/* made before the program starts: any task may ask */
__attribute__((constructor)) static void buttons_made(void)
{
    for (char *name = strtok(button_names, ","); name && button_count < BUTTONS_MAX; name = strtok(NULL, ",")) {
        const struct host_button *pad   = gamepad_button(name);
        const int                 first = tolower((unsigned char)name[0]);
        buttons[button_count++] = pad ? *pad : (struct host_button){.name = name, .keys = {first >= 'a' && first <= 'z' ? SDL_SCANCODE_A + (first - 'a') : 0}};
    }
    for (int i = 0; i < GAMEPAD_BUTTONS && button_count < BUTTONS_MAX; ++i)
        if (board_button_find(gamepad[i].name) < 0) buttons[button_count++] = gamepad[i];
}

int board_button_count(void)
{
    return button_count;
}

const char *board_button_name(int index)
{
    return index >= 0 && index < button_count ? buttons[index].name : NULL;
}

bool board_button_at(int index, bool *pressed)
{
    if (!pressed || index < 0 || index >= button_count) return false;
    uint16_t  held[KEYS_HELD_MAX];
    const int count = dgx_host_keys(held, KEYS_HELD_MAX);
    *pressed        = false;
    for (int k = 0; k < count && !*pressed; ++k)
        for (int j = 0; j < BUTTON_KEYS; ++j) *pressed |= buttons[index].keys[j] && held[k] == buttons[index].keys[j];
    return true;
}

bool board_button(bool *pressed)
{
    return board_button_at(0, pressed);
}
