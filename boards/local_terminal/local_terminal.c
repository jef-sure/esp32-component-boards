/*
 * The glue of local_terminal, made by tools/boards_gen.py from catalog/boards/local_terminal/board.json: do not
 * edit by hand: edit the data and generate again (tools/check_boards.py checks the two agree).
 * Every function of boards.h is here: by the data for the parts the board has, returning
 * false for the parts it has not, so the contract of boards.h holds at link.
 */
#include "boards.h"
#include "board_glue.h"

#include "sdkconfig.h"

#include "board_character.h"
#include "driver/spi_common.h"
#include "esp_log.h"
#include <stdlib.h>
#include <string.h>

/* Local terminal: ESP32, 2004 LCD, two PN532: An attendance terminal: an ESP32 dev board, two PN532 on SPI2 and SPI3 and a 2004 LCD on I2C. */

/* The buses of the board. */
static const struct board_spi_bus board_spi_spi2 = {.host = SPI2_HOST, .mosi = GPIO_NUM_13, .miso = GPIO_NUM_12, .sclk = GPIO_NUM_14};
static const struct board_spi_bus board_spi_spi3 = {.host = SPI3_HOST, .mosi = GPIO_NUM_23, .miso = GPIO_NUM_19, .sclk = GPIO_NUM_18};
static const struct board_i2c_pins board_i2c_pins_of = {.port = I2C_NUM_0, .sda = GPIO_NUM_21, .scl = GPIO_NUM_22}; /* i2c.i2c0 */

/* Every bus of the board, its numbers by name: the kinds the component sets up and the
 * kinds it only keeps for the program, for a program that sets its own hardware up on the
 * board's wiring instead of copying pins. */
static const struct board_bus_field board_bus_table[] = {{"i2c.i2c0", "scl", 22}, {"i2c.i2c0", "sda", 21}, {"spi.spi3", "miso", 19}, {"spi.spi3", "mosi", 23}, {"spi.spi3", "sclk", 18}, {"spi.spi2", "miso", 12}, {"spi.spi2", "mosi", 13}, {"spi.spi2", "sclk", 14}, {"led", "out", 2}, {"nfc_in_nfc", "cs", 5}, {"nfc_out_nfc", "cs", 27}};

bool board_bus_get(const char *bus, const char *field, long *out)
{
    for (size_t i = 0; i < sizeof(board_bus_table) / sizeof(board_bus_table[0]); ++i) {
        if (board_bus_table[i].bus && strcmp(board_bus_table[i].bus, bus) == 0 && strcmp(board_bus_table[i].field, field) == 0) {
            if (out) *out = board_bus_table[i].value;
            return true;
        }
    }
    return false;
}

/* The SPI buses open to the program's devices. A host with only a display on it is not one of them. */
static const struct board_spi_bus *const board_spi_buses[] = {&board_spi_spi2, &board_spi_spi3};

const struct board_spi_bus *board_spi_bus(int host)
{
    for (size_t i = 0; i < sizeof(board_spi_buses) / sizeof(board_spi_buses[0]); ++i)
        if (board_spi_buses[i]->host == host) return board_spi_buses[i];
    return NULL;
}

/* The hosts the board's buses claim, SPI and QSPI alike: spi2, spi3. */
bool board_spi_taken(int host)
{
    static const int taken[] = {SPI2_HOST, SPI3_HOST};
    for (size_t i = 0; i < sizeof(taken) / sizeof(taken[0]); ++i)
        if (taken[i] == host) return true;
    return false;
}

/* The board's I2C: one master, made by whoever asks first (board_glue_i2c). */
const struct board_i2c_pins *board_i2c_pins(void)
{
    return &board_i2c_pins_of;
}

/* The character display: a 20x4 hd44780 on i2c.i2c0. */
static lcd_bus_hd44780_t *character_bus(void)
{
    i2c_master_bus_handle_t bus = board_glue_i2c();
    return bus ? lcd_bus_pcf8574_i2c_create_on_bus(bus, 0x27, 0) : NULL;
}

static const struct board_character_panel character_panel = {.geometry = HD44780_GEOMETRY_20X4, .cols = 20, .rows = 4, .bus = character_bus};

bool board_character_display_init(struct board_character_display *out)
{
    return board_glue_character_init(&character_panel, out);
}

const struct board_touch_table board_touch_table = {.count = 0};

const struct board_sound_table board_sound_table = {.count = 0};

static const struct board_button_entry button_entries[] = {{.name = "boot", .pin = 0, .active_low = true}};
const struct board_button_table board_button_table = {.entries = button_entries, .count = 1};

/* What the board has not: the rest of boards.h, returning false, so that the same program
 * links and runs on every board. */
int board_display_count(void)
{
    return 0;
}

bool board_display_init(struct board_display *out)
{
    (void)out;
    return false;
}

bool board_display_init_at(int index, struct board_display *out)
{
    (void)index, (void)out;
    return false;
}

bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy)
{
    (void)display, (void)dir_x, (void)dir_y, (void)swap_xy;
    return false;
}

/* What the board is, for board_info(). */
const struct board_data board_data = {.name = "local_terminal", .title = "Local terminal: ESP32, 2004 LCD, two PN532", .target = "esp32"};
