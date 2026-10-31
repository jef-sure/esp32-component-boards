# The boards and the modules the component has glue for, made by tools/boards_gen.py --all
# from catalog/: CMakeLists.txt compiles the chosen board's glue (CONFIG_BOARD_<BOARD>)
# and every module turned on (CONFIG_BOARD_MODULE_<MODULE>). Do not edit by hand.
set(BOARDS_LIST cyd_s028r jc1060p470c jc4827w543c jc8012p4a1c local_terminal)
set(BOARDS_MODULES lcd2004_pcf8574)
set(BOARDS_ADAPTER_DIRS adapters/espressif__esp_codec_dev adapters/espressif__esp_driver_dac adapters/espressif__esp_driver_i2s adapters/espressif__esp_lcd_touch adapters/espressif__esp_lcd_touch_gt911 adapters/jef-sure__dgx adapters/jef-sure__dgx-di adapters/jef-sure__hd44780)
set(BOARDS_ADAPTER_INCLUDES adapters/jef-sure__dgx/include adapters/jef-sure__dgx-di/include adapters/jef-sure__hd44780/include)
set(BOARDS_ADAPTER_SOURCES BOARD_SOUND_ES8311=adapters/espressif__esp_codec_dev/board_sound_es8311.c BOARD_SOUND_DAC=adapters/espressif__esp_driver_dac/board_sound_dac.c BOARD_SOUND_I2S=adapters/espressif__esp_driver_i2s/board_sound_i2s.c BOARD_TOUCH_SPI=adapters/espressif__esp_lcd_touch/board_touch_spi.c BOARD_TOUCH_GT911=adapters/espressif__esp_lcd_touch_gt911/board_touch_gt911.c BOARD_DISPLAY_GRAPHICS=adapters/jef-sure__dgx/board_display.c BOARD_TOUCH=adapters/jef-sure__dgx-di/board_pointer.c BOARD_TOUCH_GSL3680=adapters/jef-sure__dgx-di/board_touch_gsl3680.c BOARD_TOUCH_ESP_LCD=adapters/jef-sure__dgx-di/board_touch_lcd.c BOARD_DISPLAY_HD44780=adapters/jef-sure__hd44780/board_character.c)
