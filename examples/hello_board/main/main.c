/*
 * The board the program runs on, as it is: what the choice of the board gave the program, told
 * in the log and shown on what the board has. The program asks by kind (boards.h), never by
 * the board's name: build it for the CYD S028R or for the 10-inch Guition, the same main.c runs.
 * Every function of boards.h exists on every board; one the board has not returns false.
 *
 * The headers of the libraries are included only when the board brings them (the symbols of the
 * Kconfig of the boards): a program that draws on every board it is built for includes them
 * unconditionally and lists the components in its own manifest.
 */
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "boards.h"
#include "sdkconfig.h"

#if CONFIG_BOARD_DISPLAY_GRAPHICS
#include "boards_dgx.h"
#include "dgx_draw.h"
#endif
#if CONFIG_BOARD_DISPLAY_HD44780
#include "boards_hd44780.h"
#endif

enum { TONE_PERIOD = 50 }; /* samples a wave: 441 Hz at 22050 */
#define TONE_AMPLITUDE 8000.0f
#define TWO_PI         6.2831853f

/* A second of a tone at the rate of the board, then silence: the speaker of the board heard once. */
struct tone {
    uint32_t rate, phase, made;
};

static void tone(void *ctx, int16_t *samples, size_t count)
{
    struct tone *wave = ctx;
    for (size_t i = 0; i < count; ++i) {
        samples[i]  = wave->made < wave->rate ? (int16_t)(sinf((float)wave->phase * TWO_PI / TONE_PERIOD) * TONE_AMPLITUDE) : 0;
        wave->phase = (wave->phase + 1) % TONE_PERIOD;
        ++wave->made;
    }
}

void app_main(void)
{
    const board_info_t *board = board_info();
    printf("the board: %s (%s), %s\n", board->title, board->name, board->target);

    board_display_t display = {0};
    if (board_display_init(&display)) {
        printf("the display: %d x %d pixels", display.width, display.height);
        if (display.mm_w) printf(", %d x %d mm", display.mm_w, display.mm_h);
        printf("\n");
#if CONFIG_BOARD_DISPLAY_GRAPHICS
        /* a frame: white, a blue bar at the top, so that the orientation and the order of the colors are seen */
        dgx_screen_t *screen = board_dgx_screen(&display);
        dgx_fill_rectangle(screen, 0, 0, display.width, display.height, 0xffff);
        dgx_fill_rectangle(screen, 0, 0, display.width, display.height / 8, 0x001f);
#endif
    } else {
        printf("the display: none, or it could not be set up\n");
    }

    board_character_display_t lcd;
    if (board_character_display_init(&lcd)) {
        printf("the character display: %d x %d\n", lcd.cols, lcd.rows);
#if CONFIG_BOARD_DISPLAY_HD44780
        /* row by row: past the end of a row the memory of an HD44780 goes on in another one, row 0 runs into row 2 */
        const char *rest = board->title;
        for (int row = 0; row < lcd.rows && *rest; ++row) {
            size_t count = strnlen(rest, (size_t)lcd.cols);
            lcd_set_cursor(board_hd44780(&lcd), 0, (uint8_t)row);
            lcd_write_strn(board_hd44780(&lcd), rest, count);
            rest += count;
        }
#endif
    } else {
        printf("the character display: none\n");
    }

    board_touch_t touch;
    if (board_touch_start(&display, &touch)) printf("the touch: %d fingers\n", touch.fingers);
    else printf("the touch: none, or it could not be set up\n");

    printf("the buttons: %d\n", board_button_count());
    for (int i = 0; i < board_button_count(); ++i) {
        bool pressed;
        if (board_button_at(i, &pressed)) printf("  %s: %s\n", board_button_name(i), pressed ? "held" : "free");
    }

    static struct tone wave;
    board_sound_t      sound;
    if (board_sound_init(&sound)) {
        wave.rate = sound.rate;
        board_sound_start(tone, &wave, NULL);
        printf("the sound: %lu Hz, a second of a tone\n", (unsigned long)sound.rate);
    } else {
        printf("the sound: none, or it could not be set up\n");
    }

    long hz;
    if (board_bus_get("spi.spi2", "hz", &hz)) printf("the display's SPI runs at %ld Hz\n", hz);
}
