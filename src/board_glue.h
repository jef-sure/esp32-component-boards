#pragma once

/*
 * The inside of the boards: the contract between the core (src/), the adapters of the libraries
 * (adapters/) and the glue of the chosen board (boards/<board>/<board>.c, made by
 * tools/boards_gen.py from catalog/boards/<board>/board.json). It names no library. Not for a
 * program: boards.h is; this is how a board is brought in. The glue gives the data as tables and
 * the functions of the parts it starts; src/ reads the tables, and a part the board has not is a
 * function of src/ returning false, so that the contract of boards.h holds at link on every board.
 * With no board chosen, src/board_none.c gives the tables, all empty.
 */
#include "boards.h"

#include "driver/i2c_master.h"

#ifdef __cplusplus
extern "C" {
#endif

/* What the board is: given by its glue (board_data), handed out by board_info(). */
struct board_data {
    const char *name;   /* the board's directory name, as the data names it */
    const char *title;  /* what the menu of the configuration shows */
    const char *target; /* the chip of the board: esp32, esp32s3, esp32p4, esp32c3, esp32c6 */
};
extern const struct board_data board_data;

/* The pins of an I2C bus of the board on a port, from the data of the board: NULL when it has none there. */
struct board_i2c_pins {
    int port, sda, scl;
};
struct board_i2c_table {
    const struct board_i2c_pins *buses;
    size_t                       count;
};
extern const struct board_i2c_table board_i2c_table; /* given by the glue of the board */
const struct board_i2c_pins *board_i2c_pins(int port);

/*
 * The I2C master of the board on a port, made once and kept, shared by whoever needs it: the touch
 * panel, the codec, a character display module, the program. NULL when the board has no I2C there.
 */
i2c_master_bus_handle_t board_glue_i2c(int port);

/* The firmware of the touch panel the program gave with board_touch_firmware_set; false when it gave none. */
bool board_glue_touch_firmware(const uint8_t **start, size_t *size);

/* Sets up an SPI host once, with DMA: a touch panel on it, a display sharing it. */
bool board_glue_spi_host(const struct board_spi_bus *bus);

/* A touch panel as its data says, for whatever drives it. x_max and y_max are counts: the data's largest coordinate plus one. */
struct board_touch_panel {
    int x_max, y_max;
    int rst, irq;  /* GPIO_NUM_NC when not wired */
    int i2c_port;  /* the port of its I2C bus; -1 for a panel on SPI */
    int fingers;
};

/* The touch panels of the board: the glue gives the table, src/board_touch.c starts them on demand. */
struct board_touch_entry {
    const char *name;
    const char *over; /* the display it covers */
    bool (*start)(int index, const struct board_display *display, struct board_touch *out);
};
struct board_touch_table {
    const struct board_touch_entry *entries;
    struct board_touch             *started; /* one for each */
    int                             count;
};
extern const struct board_touch_table board_touch_table;

/* The buttons of the board. */
struct board_button_entry {
    const char *name;
    int         pin;
    bool        active_low;
};
struct board_button_table {
    const struct board_button_entry *entries;
    int                              count;
};
extern const struct board_button_table board_button_table;

/*
 * One I2S bus of the board, as its data names it ("i2s0" is the chip's I2S0): its port and
 * its lines; a codec streams over it (the din line may be unused: nothing listens).
 */
struct board_i2s_bus {
    int port; /* the port of the chip the name claims */
    int mclk, bclk, ws, dout; /* mclk is GPIO_NUM_NC for an amplifier without one */
    int din; /* GPIO_NUM_NC when nothing listens */
};

enum { BOARD_SOUND_FRAMES = 256 }; /* samples a write */

/* What a kind of sound gives the task of src/board_sound.c. */
struct board_sound_output {
    const char *name; /* the call behind write, for the log */
    esp_err_t (*write)(int16_t *samples, size_t count); /* waits for the hardware, which sets the pace */
};
/* Called by an adapter when the hardware of a sound is set up: the task, if the program starts it, writes through output. */
void board_glue_sound_ready(int index, const struct board_sound_output *output);

/* The sound outputs of the board: the glue gives the table, src/board_sound.c sets each up and runs its task on demand. */
struct board_sound_entry {
    const char *name;
    uint32_t    rate;
    bool (*init)(int index); /* sets the hardware up and calls board_glue_sound_ready */
};
struct board_sound_stream {
    const struct board_sound_output *output; /* NULL until the hardware is set up */
    board_sound_source_t             source;
    void                            *ctx; /* given back to source */
    uint32_t                         rate;
    bool                             running; /* its task started */
    int16_t                          samples[BOARD_SOUND_FRAMES];
};
struct board_sound_table {
    const struct board_sound_entry *entries;
    struct board_sound_stream      *streams; /* one for each */
    int                             count;
};
extern const struct board_sound_table board_sound_table;

/*
 * A number of a bus of the board, by its name and the number's own name: every bus the
 * data wires, the kinds this component sets up itself and the kinds it only keeps (an
 * sdio of a radio beside the chip). A program that sets its own hardware up takes the
 * board's wiring from here instead of copying pins.
 */
struct board_bus_field {
    const char *bus;   /* "spi.spi2", "sdio.sdio0" */
    const char *field; /* "mosi", "clk", "hz": a number the bus carries */
    long        value;
};
struct board_bus_table {
    const struct board_bus_field *fields;
    size_t                        count;
};
extern const struct board_bus_table board_bus_table; /* given by the glue of the board */

/* The SPI buses open to the program's devices (a host with only a display on it is not one), and the hosts any bus of the board claims. */
struct board_spi_table {
    const struct board_spi_bus *const *buses;
    size_t                             count;
    const int                         *taken;
    size_t                             taken_count;
};
extern const struct board_spi_table board_spi_table; /* given by the glue of the board */

#ifdef __cplusplus
}
#endif
