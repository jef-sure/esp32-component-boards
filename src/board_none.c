/*
 * No board chosen (CONFIG_BOARD_SELECT_NONE): the program sets its hardware up itself. The tables
 * a glue gives, all empty, so that every function of boards.h links and returns false or none.
 */
#include "board_glue.h"

#include "sdkconfig.h"

const struct board_bus_table    board_bus_table = {.count = 0};
const struct board_spi_table    board_spi_table = {.count = 0};
const struct board_i2c_table    board_i2c_table = {.count = 0};
const struct board_touch_table  board_touch_table = {.count = 0};
const struct board_sound_table  board_sound_table = {.count = 0};
const struct board_button_table board_button_table = {.count = 0};
const struct board_data         board_data = {.name = "none", .title = "None: the program sets its hardware up itself", .target = CONFIG_IDF_TARGET};
