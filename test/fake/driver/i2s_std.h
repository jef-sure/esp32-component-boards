#pragma once
#include "../esp_idf_stubs.h"
typedef struct i2s_chan_handle_s *i2s_chan_handle_t;
typedef enum { I2S_NUM_0 = 0 } i2s_port_t;
typedef enum { I2S_ROLE_MASTER } i2s_role_t;
typedef enum { I2S_DATA_BIT_WIDTH_16BIT } i2s_data_bit_width_t;
typedef enum { I2S_SLOT_MODE_MONO } i2s_slot_mode_t;
typedef struct { i2s_port_t id; i2s_role_t role; int dma_frame_num; } i2s_chan_config_t;
typedef struct { gpio_num_t mclk, bclk, ws, dout, din; } i2s_std_gpio_config_t;
typedef struct { int clk_cfg; int slot_cfg; i2s_std_gpio_config_t gpio_cfg; } i2s_std_config_t;
#define I2S_GPIO_UNUSED ((gpio_num_t)-1)
#define I2S_CHANNEL_DEFAULT_CONFIG(id, role) ((i2s_chan_config_t){id, role, 0})
#define I2S_STD_CLK_DEFAULT_CONFIG(rate) (rate)
#define I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(bits, mode) (0)
int i2s_new_channel(const i2s_chan_config_t *cfg, i2s_chan_handle_t *tx, i2s_chan_handle_t *rx);
int i2s_channel_init_std_mode(i2s_chan_handle_t chan, const i2s_std_config_t *cfg);
int i2s_channel_enable(i2s_chan_handle_t chan);
int i2s_channel_disable(i2s_chan_handle_t chan);
int i2s_del_channel(i2s_chan_handle_t chan);
int i2s_channel_write(i2s_chan_handle_t chan, const void *data, size_t size, size_t *written, int timeout);
