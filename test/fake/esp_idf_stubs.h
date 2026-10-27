#pragma once
/* Stubs of the headers the generated glue includes, for the host syntax check of the glue
 * (tools/check_boards.py --host-syntax compiles each board's file with -fsyntax-only against
 * these): no ESP-IDF needed, only the shape of the calls the glue makes. When the real headers
 * change their shape, the generator changes, and this follows. The real check is the build of
 * examples/hello_board for every board in CI; this one is the fast filter before it. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* gpio */
typedef enum { GPIO_NUM_NC = -1, GPIO_NUM_0 = 0, GPIO_NUM_1 = 1, GPIO_NUM_2 = 2, GPIO_NUM_3 = 3, GPIO_NUM_4 = 4, GPIO_NUM_5 = 5, GPIO_NUM_6 = 6, GPIO_NUM_7 = 7, GPIO_NUM_8 = 8, GPIO_NUM_9 = 9, GPIO_NUM_10 = 10, GPIO_NUM_11 = 11, GPIO_NUM_12 = 12, GPIO_NUM_13 = 13, GPIO_NUM_14 = 14, GPIO_NUM_15 = 15, GPIO_NUM_16 = 16, GPIO_NUM_17 = 17, GPIO_NUM_18 = 18, GPIO_NUM_19 = 19, GPIO_NUM_20 = 20, GPIO_NUM_21 = 21, GPIO_NUM_22 = 22, GPIO_NUM_23 = 23, GPIO_NUM_24 = 24, GPIO_NUM_25 = 25, GPIO_NUM_26 = 26, GPIO_NUM_27 = 27, GPIO_NUM_28 = 28, GPIO_NUM_29 = 29, GPIO_NUM_30 = 30, GPIO_NUM_31 = 31, GPIO_NUM_32 = 32, GPIO_NUM_33 = 33, GPIO_NUM_34 = 34, GPIO_NUM_35 = 35, GPIO_NUM_36 = 36, GPIO_NUM_37 = 37, GPIO_NUM_38 = 38, GPIO_NUM_39 = 39, GPIO_NUM_40 = 40, GPIO_NUM_41 = 41, GPIO_NUM_42 = 42, GPIO_NUM_43 = 43, GPIO_NUM_44 = 44, GPIO_NUM_45 = 45, GPIO_NUM_46 = 46, GPIO_NUM_47 = 47, GPIO_NUM_48 = 48, GPIO_NUM_49 = 49, GPIO_NUM_50 = 50, GPIO_NUM_51 = 51, GPIO_NUM_52 = 52, GPIO_NUM_53 = 53, GPIO_NUM_54 = 54 } gpio_num_t;
typedef enum { GPIO_MODE_INPUT, GPIO_MODE_OUTPUT } gpio_mode_t;
typedef enum { GPIO_PULLUP_DISABLE, GPIO_PULLUP_ENABLE } gpio_pullup_t;
typedef enum { GPIO_PULLDOWN_DISABLE, GPIO_PULLDOWN_ENABLE } gpio_pulldown_t;
typedef struct { uint64_t pin_bit_mask; gpio_mode_t mode; gpio_pullup_t pull_up_en; gpio_pulldown_t pull_down_en; } gpio_config_t;
int gpio_config(const gpio_config_t *c);
int gpio_set_direction(gpio_num_t n, gpio_mode_t m);
int gpio_set_level(gpio_num_t n, int l);
int gpio_get_level(gpio_num_t n);

#define ESP_OK 0

/* spi */
typedef enum { SPI1_HOST = 0, SPI2_HOST = 1, SPI3_HOST = 2 } spi_host_device_t;
#define SPI_DMA_CH_AUTO 3
typedef struct { int mosi_io_num, miso_io_num, sclk_io_num, quadwp_io_num, quadhd_io_num, max_transfer_sz; } spi_bus_config_t;
int spi_bus_initialize(spi_host_device_t host, const spi_bus_config_t *c, int dma);

/* i2c master */
typedef struct i2c_master_bus_t i2c_master_bus_t;
typedef i2c_master_bus_t *i2c_master_bus_handle_t;
typedef enum { I2C_NUM_0 = 0, I2C_NUM_1 = 1, I2C_CLK_SRC_DEFAULT } i2c_clock_source_t;
typedef struct { int i2c_port; gpio_num_t sda_io_num, scl_io_num; i2c_clock_source_t clk_source; int glitch_ignore_cnt; struct { unsigned enable_internal_pullup : 1; } flags; } i2c_master_bus_config_t;
int i2c_new_master_bus(const i2c_master_bus_config_t *c, i2c_master_bus_handle_t *h);

/* esp_lcd: the panel io on I2C and on SPI, the touch interface */
typedef struct esp_lcd_panel_io_t *esp_lcd_panel_io_handle_t;
typedef void *esp_lcd_spi_bus_handle_t;
typedef struct { int dev_addr, scl_speed_hz; } esp_lcd_panel_io_i2c_config_t;
int esp_lcd_new_panel_io_i2c(i2c_master_bus_handle_t bus, const esp_lcd_panel_io_i2c_config_t *c, esp_lcd_panel_io_handle_t *io);
int esp_lcd_panel_io_del(esp_lcd_panel_io_handle_t io);
typedef struct { int cs_gpio_num, dc_gpio_num, spi_mode, pclk_hz, trans_queue_depth, lcd_cmd_bits, lcd_param_bits; } esp_lcd_panel_io_spi_config_t;
int esp_lcd_new_panel_io_spi(esp_lcd_spi_bus_handle_t bus, const esp_lcd_panel_io_spi_config_t *c, esp_lcd_panel_io_handle_t *io);
typedef struct { int x_max, y_max; gpio_num_t rst_gpio_num, int_gpio_num; void *driver_data; } esp_lcd_touch_config_t;
typedef struct esp_lcd_touch_t *esp_lcd_touch_handle_t;
#define ESP_LCD_TOUCH_IO_I2C_GT911_CONFIG() ((esp_lcd_panel_io_i2c_config_t){0})
#define ESP_LCD_TOUCH_IO_I2C_GT911_ADDRESS 0x5d
#define ESP_LCD_TOUCH_IO_I2C_GT911_ADDRESS_BACKUP 0x14
int esp_lcd_touch_new_i2c_gt911(esp_lcd_panel_io_handle_t io, const esp_lcd_touch_config_t *c, esp_lcd_touch_handle_t *h);

/* log */
#define ESP_LOGE(tag, ...) ((void)0)
#define ESP_LOGW(tag, ...) ((void)0)
#define ESP_LOGI(tag, ...) ((void)0)

/* hd44780: the bus of a character LCD */
typedef struct lcd_bus_hd44780_s lcd_bus_hd44780_t;
lcd_bus_hd44780_t *lcd_bus_pcf8574_i2c_create_on_bus(i2c_master_bus_handle_t bus, uint8_t addr, uint32_t hz);
