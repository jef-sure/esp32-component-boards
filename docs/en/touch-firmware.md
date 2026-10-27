# The touch firmware of the GSL3680

The GSL3680 touch controller of the 10.1-inch Guition JC8012P4A1C keeps no
firmware of its own: the host writes it into the chip over I2C at every
start. The vendor ships it as a C array in a header of the board's package,
with no licence that allows redistribution, so it is not in this component.
The program that builds for that board embeds it. Without it the board builds
and runs, with its touch off: `board_touch_start` returns `false` and the log
says why.

## Making the file

DGX-DI's `tools/gsl_firmware.py` turns the vendor's array into a compact file:

```sh
python3 managed_components/jef-sure__dgx-di/tools/gsl_firmware.py \
    path/to/esp_lcd_touch_gsl3680.h main/jc8012p4a1c_touch.fw --range 1664x896
```

`--range` is the range of the raw coordinates the firmware reports, which
the array does not say; 1664x896 is the JC8012P4A1C's, and matches `x_max`
and `y_max` in the board's data.

## Embedding it

In the program's `main/CMakeLists.txt`:

```cmake
idf_component_register(SRCS "main.c"
                       PRIV_REQUIRES jef-sure__boards
                       EMBED_FILES "jc8012p4a1c_touch.fw")
```

ESP-IDF places the file in flash with the symbols
`_binary_jc8012p4a1c_touch_fw_start` and `_end`. In the program, define the
hook the component declares in `boards.h`:

```c
#include "boards.h"

extern const uint8_t touch_fw_start[] asm("_binary_jc8012p4a1c_touch_fw_start");
extern const uint8_t touch_fw_end[] asm("_binary_jc8012p4a1c_touch_fw_end");

bool board_touch_firmware(const uint8_t **start, size_t *size)
{
    *start = touch_fw_start;
    *size  = (size_t)(touch_fw_end - touch_fw_start);
    return true;
}
```

The component's own `board_touch_firmware` is weak and answers `false`; the
program's strong definition takes its place at link. The glue of the board
calls it at `board_touch_start`, hands the bytes to DGX-DI's GSL3680 driver,
which writes them into the chip.

A program built for several boards keeps the file and the function under a
condition, so the CYD build does not look for a file it has not:

```cmake
if(CONFIG_BOARD_JC8012P4A1C AND EXISTS ${CMAKE_CURRENT_LIST_DIR}/jc8012p4a1c_touch.fw)
    set(TOUCH_FW "jc8012p4a1c_touch.fw")
endif()
idf_component_register(... EMBED_FILES ${TOUCH_FW})
if(TOUCH_FW)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE HAVE_TOUCH_FW=1)
endif()
```

and `#ifdef HAVE_TOUCH_FW` around the function in C.
