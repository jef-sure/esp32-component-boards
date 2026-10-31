/* A GT911 on the board's I2C bus. */
#include "board_touch_gt911.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_touch_gt911.h"
#include "esp_log.h"

static const char *TAG = "board";

esp_lcd_touch_handle_t board_glue_touch_gt911_new(const struct board_touch_gt911 *gt911)
{
    i2c_master_bus_handle_t bus = board_glue_i2c();
    if (!bus) return NULL;
    const struct board_touch_panel *touch = gt911->panel;
    esp_lcd_touch_config_t    config = {.x_max = touch->x_max, .y_max = touch->y_max, .rst_gpio_num = (gpio_num_t)touch->rst, .int_gpio_num = (gpio_num_t)touch->irq};
    const bool                choose_address = touch->rst != GPIO_NUM_NC && touch->irq != GPIO_NUM_NC;
    esp_lcd_touch_handle_t    handle         = NULL;
    for (int i = 0; i < gt911->address_count && !handle; ++i) {
        esp_lcd_panel_io_handle_t     io;
        esp_lcd_panel_io_i2c_config_t io_config = ESP_LCD_TOUCH_IO_I2C_GT911_CONFIG();
        io_config.dev_addr                      = gt911->addresses[i];
        io_config.scl_speed_hz                  = gt911->i2c_hz;
        /* RST and INT are wired: the driver holds INT at the level of this address during reset */
        esp_lcd_touch_io_gt911_config_t address = {.dev_addr = gt911->addresses[i]};
        if (choose_address) config.driver_data = &address;
        if (esp_lcd_new_panel_io_i2c(bus, &io_config, &io) != ESP_OK) continue;
        if (esp_lcd_touch_new_i2c_gt911(io, &config, &handle) != ESP_OK) esp_lcd_panel_io_del(io); /* off the bus: the next address */
    }
    if (!handle) {
        ESP_LOGE(TAG, "esp_lcd_touch_new_i2c_gt911: no touch panel answers on the board's I2C bus");
    }
    return handle;
}
