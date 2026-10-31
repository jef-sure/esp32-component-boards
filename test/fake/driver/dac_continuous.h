#pragma once
#include "../esp_idf_stubs.h"
typedef struct dac_continuous_s *dac_continuous_handle_t;
#define DAC_CHANNEL_MASK_CH0 1
#define DAC_CHANNEL_MASK_CH1 2
typedef enum { DAC_DIGI_CLK_SRC_DEFAULT } dac_continuous_digi_clk_src_t;
typedef enum { DAC_CHANNEL_MODE_SIMUL, DAC_CHANNEL_MODE_ALTER } dac_continuous_channel_mode_t;
typedef struct { int chan_mask; uint32_t desc_num; size_t buf_size; uint32_t freq_hz; int8_t offset; dac_continuous_digi_clk_src_t clk_src; dac_continuous_channel_mode_t chan_mode; } dac_continuous_config_t;
int dac_continuous_new_channels(const dac_continuous_config_t *c, dac_continuous_handle_t *h);
int dac_continuous_enable(dac_continuous_handle_t h);
int dac_continuous_write(dac_continuous_handle_t h, uint8_t *buf, size_t size, size_t *loaded, int timeout_ms);
int dac_continuous_disable(dac_continuous_handle_t h);
int dac_continuous_del_channels(dac_continuous_handle_t h);
