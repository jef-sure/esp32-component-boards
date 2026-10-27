/*
 * The board the program runs on, as it is: what the choice of the board gave the program, told
 * in the log and shown on what the board has. The program asks by kind (boards.h), never by
 * the board's name: build it for the CYD or for the 10-inch Guition, the same main.c runs.
 * Every function of boards.h exists on every board; one the board has not answers false.
 *
 * The headers of DGX, DGX-DI and hd44780 are included only when the board brings them (the
 * symbols of the Kconfig of the boards): a program that draws on every board it is built for
 * includes them unconditionally and lists the components in its own manifest.
 */
#include <math.h>
#include <stdio.h>

#include "boards.h"
#include "sdkconfig.h"

#if CONFIG_BOARD_DISPLAY_FRAMEBUFFER
#include "dgx_draw.h"
#endif
#if CONFIG_BOARD_TOUCH
#include "dgx_di.h"
#endif
#if CONFIG_BOARD_DISPLAY_HD44780
#include "hd44780.h"
#endif

/* A second of a tone, then silence: the speaker of the board heard once. */
static void tone(int16_t *samples, size_t count)
{
    static uint32_t phase, made;
    for (size_t i = 0; i < count; ++i) {
        samples[i] = made < 22050 ? (int16_t)(sinf((float)phase * 6.2831853f / 50.0f) * 8000.0f) : 0; /* 441 Hz at 22050 */
        phase = (phase + 1) % 50;
        ++made;
    }
}

void app_main(void)
{
    const struct board_info *board = board_info();
    printf("the board: %s (%s), %s\n", board->title, board->name, board->target);

    struct board_display display = {0};
    if (board_display_init(&display)) {
        printf("the display: %d x %d pixels, %d x %d mm\n", display.width, display.height, display.mm_w, display.mm_h);
#if CONFIG_BOARD_DISPLAY_FRAMEBUFFER
        /* a frame: white, a dark bar at the top, so that the orientation is seen */
        dgx_fill_rectangle((dgx_screen_t *)display.screen, 0, 0, display.width, display.height, 0xffff);
        dgx_fill_rectangle((dgx_screen_t *)display.screen, 0, 0, display.width, display.height / 8, 0x001f);
#endif
    } else {
        printf("the display: none, or it could not be set up\n");
    }

    struct board_character_display lcd;
    if (board_character_display_init(&lcd)) {
        printf("the character display: %d x %d\n", lcd.cols, lcd.rows);
#if CONFIG_BOARD_DISPLAY_HD44780
        lcd_set_cursor((hd44780_t *)lcd.lcd, 0, 0);
        lcd_write_str((hd44780_t *)lcd.lcd, board->title);
#endif
    } else {
        printf("the character display: none\n");
    }

    struct dgx_di_device *device = NULL;
    void                 *pointer = NULL; /* a dgx_di_pointer_t *, for dgx_di_pointer_read in a task of the program's */
    if (board_touch_start(&display, &device, &pointer)) {
#if CONFIG_BOARD_TOUCH
        printf("the touch: a device of DGX-DI, %d fingers\n", (int)device->fingers);
#else
        printf("the touch: started\n");
#endif
    } else {
        printf("the touch: none, or it could not be set up\n");
    }

    bool pressed;
    if (board_button(&pressed)) printf("the button: %s\n", pressed ? "held" : "free");
    else printf("the button: none\n");

    uint32_t rate;
    if (board_sound_start(tone, &rate)) printf("the sound: %lu Hz, a second of a tone\n", (unsigned long)rate);
    else printf("the sound: none, or it could not be set up\n");

    long hz;
    if (board_bus_get("spi.spi2", "hz", &hz)) printf("the display's SPI runs at %ld Hz\n", hz);
}
