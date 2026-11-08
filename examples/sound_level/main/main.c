/*
 * The level of the sound a board is comfortable at, heard on the board: a tone at levels from 5 to 100 percent of full
 * scale, each for a few seconds, the level in the log and as a bar on the display. The level that sounds neither faint
 * nor loud goes into the data of the board as config.mixer_volume of its sound, with the trial in checked.
 */
#include <math.h>
#include <stdio.h>

#include "boards.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

#if CONFIG_BOARD_DISPLAY_GRAPHICS
#include "boards_dgx.h"
#include "dgx_bits.h"
#include "dgx_colors.h"
#include "dgx_draw.h"
#endif

enum { TONE_HZ = 441, LEVEL_STEP = 5, LEVEL_MAX = 100, STEP_MS = 3000 };
#define TWO_PI    6.2831853f
#define FULL_SCALE 32767.0f

struct tone {
    volatile int level;  /* percent of full scale */
    uint32_t     period; /* samples a wave at the rate of the board */
    uint32_t     phase;
};

static void tone(void *ctx, int16_t *samples, size_t count)
{
    struct tone *wave      = ctx;
    const float  amplitude = FULL_SCALE * (float)wave->level / LEVEL_MAX;
    for (size_t i = 0; i < count; ++i) {
        samples[i]  = (int16_t)(sinf((float)wave->phase * TWO_PI / (float)wave->period) * amplitude);
        wave->phase = (wave->phase + 1) % wave->period;
    }
}

void app_main(void)
{
    static struct tone wave;
    board_sound_t      sound;
    if (!board_sound_init(&sound)) {
        printf("the board has no sound, or it could not be set up\n");
        return;
    }
    wave.period = sound.rate / TONE_HZ;
    if (sound.mixer_volume) printf("the data of %s says %d%%\n", board_info()->name, sound.mixer_volume);
    else printf("the data of %s has no level of its sound yet\n", board_info()->name);
#if CONFIG_BOARD_DISPLAY_GRAPHICS
    board_display_t display = {0};
    dgx_screen_t   *screen = board_display_init(&display) ? board_dgx_screen(&display) : NULL;
    if (screen) dgx_fill_rectangle(screen, 0, 0, display.width, display.height, 0);
#endif
    board_sound_start(tone, &wave, NULL);
    for (int level = LEVEL_STEP; level <= LEVEL_MAX; level += LEVEL_STEP) {
        wave.level = level;
        printf("level %d%% of full scale\n", level);
#if CONFIG_BOARD_DISPLAY_GRAPHICS
        /* a bar as wide as the level, white on black */
        if (screen)
            dgx_fill_rectangle(screen, 0, display.height / 3, display.width * level / LEVEL_MAX, display.height / 3, DGX_WHITE(dgx_rgb_to_16));
#endif
        vTaskDelay(pdMS_TO_TICKS(STEP_MS));
    }
    wave.level = 0;
    printf("done: the level that sounded neither faint nor loud is config.mixer_volume of the sound of the board\n");
}
