# The glue of jc1060p470c, made by tools/boards_gen.py from its data: the components it needs,
# derived from what the board has (the components of ESP-IDF 5.5 and later; extra_requires
# in catalog/boards/jc1060p470c/board.json adds what the structure cannot say). Do not edit by hand.
# Added after idf_component_register, when the configuration is known: a requirement that
# depends on the board chosen cannot stand in REQUIRES. Optional: a component the rules of the
# manifest did not bring is simply not there, and the glue that needs it is not compiled either.
# PUBLIC: a program draws with DGX and reads DGX-DI through the headers this brings.
idf_component_optional_requires(PUBLIC esp_driver_gpio esp_driver_i2c esp_driver_i2s espressif__esp_codec_dev espressif__esp_hosted espressif__esp_lcd_touch espressif__esp_lcd_touch_gt911 jef-sure__dgx jef-sure__dgx-di)
# The radio beside the chip, for the flash step of the component: the target of its chip, the kind of its bus, who
# sets its firmware (program: the component keeps it at the version of the build) and the board of the catalog
# this hardware is, the root of what the board extends.
set(BOARD_RADIO_TARGET esp32c6)
set(BOARD_RADIO_TRANSPORT sdio)
set(BOARD_RADIO_FIRMWARE program)
set(BOARD_RADIO_HARDWARE jc1060p470c)
