#pragma once

/*
 * The inside of the boards: the contract between the core (src/boards.c, src/board_i2c.c,
 * src/board_pointer.c, src/board_touch_fw.c) and the glue of the chosen board
 * (boards/<board>/<board>.c, made by tools/boards_gen.py from boards-data/<board>/board.json).
 * Not for a program: boards.h is; this is how a board is brought in. The glue gives the data
 * and every function boards.h declares; a part the board has not is a function answering false,
 * generated into the same glue, so that the contract of boards.h holds at link on every board.
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
    const char *target; /* the chip of the board: esp32, esp32s3, esp32p4 */
};
extern const struct board_data board_data;

/* The pins of the board's I2C, from the data of the board: NULL when it has none. */
struct board_i2c_pins {
    int port, sda, scl;
};
const struct board_i2c_pins *board_i2c_pins(void);

/*
 * The I2C master of the board, made once and kept, shared by whoever needs it: the touch
 * panel, the codec, a character display module. NULL when the board has no I2C in its data.
 */
i2c_master_bus_handle_t board_glue_i2c(void);

/* The pointer of DGX-DI the touch of the board is read through: one, of the core, kept here
 * (a dgx_di_pointer_t *, as void *: this header includes nothing of DGX-DI). */
void *board_glue_pointer(void);

/*
 * One I2S bus of the board, as its data names it ("i2s0" is the chip's I2S0): its port and
 * its lines; a codec streams over it (the din line may be unused: nothing listens).
 */
struct board_i2s_bus {
    int port; /* the port of the chip the name claims */
    int mclk, bclk, ws, dout;
    int din; /* GPIO_NUM_NC when nothing listens */
};

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

#ifdef __cplusplus
}
#endif
