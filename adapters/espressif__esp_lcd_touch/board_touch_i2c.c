/* A touch panel of esp_lcd_touch on the board's I2C bus, such as a CST816S. */
#include "board_touch_i2c.h"
#include "esp_log.h"

static const char *TAG = "board";

esp_lcd_touch_handle_t board_glue_touch_i2c_new(const struct board_touch_i2c *i2c)
{
    const struct board_touch_panel *touch = i2c->panel;
    i2c_master_bus_handle_t         bus   = board_glue_i2c(touch->i2c_port);
    if (!bus) return NULL;
    esp_lcd_panel_io_i2c_config_t io_config = i2c->io;
    io_config.dev_addr                      = i2c->address;
    if (!io_config.scl_speed_hz) io_config.scl_speed_hz = i2c->hz;
    esp_lcd_panel_io_handle_t     io;
    esp_err_t                     err = esp_lcd_new_panel_io_i2c(bus, &io_config, &io);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_lcd_new_panel_io_i2c: %s", esp_err_to_name(err));
        return NULL;
    }
    const esp_lcd_touch_config_t config = {.x_max = touch->x_max, .y_max = touch->y_max, .rst_gpio_num = (gpio_num_t)touch->rst, .int_gpio_num = (gpio_num_t)touch->irq};
    esp_lcd_touch_handle_t       handle = NULL;
    err                                 = i2c->create(io, &config, &handle);
    if (err != ESP_OK || !handle) {
        ESP_LOGE(TAG, "esp_lcd_touch_new_i2c: %s: no touch panel at 0x%02x on the board's I2C bus", esp_err_to_name(err), (unsigned)i2c->address);
        esp_lcd_panel_io_del(io);
        return NULL;
    }
    return handle;
}

bool board_glue_touch_i2c_start(int index, const struct board_touch_entry *entry, const struct board_display *display, struct board_touch *out)
{
    const struct board_touch_i2c *i2c = entry->esp_lcd_touch_i2c;
    if (!board_dgx_screen(display)) return false;
    esp_lcd_touch_handle_t handle = board_glue_touch_i2c_new(i2c);
    return handle && board_glue_touch_lcd_attach(i2c->device, index, handle, true, i2c->panel, i2c->calibrated, display, out);
}
