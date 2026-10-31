/* The buttons of the board, from the table of the glue. */
#include "board_glue.h"

#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "board";

int board_button_count(void)
{
    return board_button_table.count;
}

const char *board_button_name(int index)
{
    return index >= 0 && index < board_button_table.count ? board_button_table.entries[index].name : NULL;
}

bool board_button_at(int index, bool *pressed)
{
    if (!pressed || index < 0 || index >= board_button_table.count) return false;
    const struct board_button_entry *button = &board_button_table.entries[index];
    static uint64_t set_up; /* a bit per pin */
    if (!(set_up & (1ULL << button->pin))) {
        const gpio_config_t config = {.pin_bit_mask = 1ULL << button->pin,
                                      .mode         = GPIO_MODE_INPUT,
                                      .pull_up_en   = button->active_low ? GPIO_PULLUP_ENABLE : GPIO_PULLUP_DISABLE,
                                      .pull_down_en = button->active_low ? GPIO_PULLDOWN_DISABLE : GPIO_PULLDOWN_ENABLE};
        esp_err_t           err    = gpio_config(&config);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "gpio_config: %s", esp_err_to_name(err));
            return false;
        }
        set_up |= 1ULL << button->pin;
    }
    *pressed = (gpio_get_level((gpio_num_t)button->pin) == 0) == button->active_low;
    return true;
}

bool board_button(bool *pressed)
{
    return board_button_at(0, pressed);
}
