# The glue of local_terminal, made by tools/boards_gen.py from its data: the components it needs,
# derived from what the board has (the components of ESP-IDF 5.3 and later; extra_requires
# in catalog/boards/local_terminal/board.json adds what the structure cannot say). Do not edit by hand.
# Added after idf_component_register, when the configuration is known: a requirement that
# depends on the board chosen cannot stand in REQUIRES. Optional: a component the rules of the
# manifest did not bring is simply not there, and the glue that needs it is not compiled either.
# PUBLIC: a program draws with DGX and reads DGX-DI through the headers this brings.
idf_component_optional_requires(PUBLIC esp_driver_gpio esp_driver_i2c esp_driver_spi jef-sure__hd44780)
