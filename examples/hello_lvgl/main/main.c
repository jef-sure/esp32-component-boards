/*
 * LVGL on the chosen board: boards sets up the display and the touch panel, DGX-LVGL connects
 * them to LVGL. Nothing here names a board.
 *
 * The task of app_main owns the display: only it calls LVGL and draws on the screen.
 */
#include "boards.h"
#include "boards_dgx.h"
#include "dgx_lvgl.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

#if CONFIG_BOARD_TOUCH
#include "boards_dgx_di.h"
#endif

static const char *TAG = "hello_lvgl";

#define BANDS_PER_SCREEN 10 /* LVGL renders this part of the screen at a time */
#define MAX_WAIT_MS      30

static uint32_t ms_now(void)
{
    return (uint32_t)(esp_timer_get_time() / 1000);
}

static void pressed(lv_event_t *event)
{
    static int presses;
    lv_label_set_text_fmt((lv_obj_t *)lv_event_get_user_data(event), "Pressed %d", ++presses);
    ESP_LOGI(TAG, "pressed %d", presses);
}

void app_main(void)
{
    struct board_display board = {0};
    if (!board_display_init(&board)) {
        ESP_LOGE(TAG, "board_display_init failed");
        return;
    }

    lv_init();
    lv_tick_set_cb(ms_now);

    const uint32_t size    = (uint32_t)board.width * board.height * sizeof(uint16_t) / BANDS_PER_SCREEN;
    void          *buffer  = heap_caps_aligned_alloc(LV_DRAW_BUF_ALIGN, size, MALLOC_CAP_DMA);
    lv_display_t  *display = buffer ? dgx_lvgl_display_create(board_dgx_screen(&board), buffer, size) : NULL;
    if (!display) {
        ESP_LOGE(TAG, "dgx_lvgl_display_create failed");
        return;
    }

#if CONFIG_BOARD_TOUCH
    struct board_touch touch;
    dgx_di_pointer_t  *pointer = board_touch_start(&board, &touch) ? board_dgx_di_pointer(&touch) : NULL;
    if (pointer) dgx_lvgl_pointer_create(display, pointer);
    else ESP_LOGI(TAG, "board_touch_start: no touch panel");
#endif

    lv_obj_t *button = lv_button_create(lv_screen_active());
    lv_obj_center(button);
    lv_obj_t *text = lv_label_create(button);
    lv_label_set_text(text, "Press me");
    lv_obj_add_event_cb(button, pressed, LV_EVENT_CLICKED, text);
    ESP_LOGI(TAG, "%s: %dx%d, a buffer of %lu bytes", board_info()->name, board.width, board.height, (unsigned long)size);

    for (;;) {
#if CONFIG_BOARD_TOUCH
        if (pointer) dgx_di_pointer_read(pointer, lv_tick_get());
#endif
        const uint32_t wait = lv_timer_handler();
        vTaskDelay(pdMS_TO_TICKS(wait < 1u ? 1u : wait > MAX_WAIT_MS ? MAX_WAIT_MS : wait));
    }
}
