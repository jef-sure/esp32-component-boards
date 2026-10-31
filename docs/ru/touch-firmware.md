# Прошивка тача GSL3680

Контроллер тача GSL3680 10,1-дюймовой Guition JC8012P4A1C не хранит
собственной прошивки: хост записывает её в чип по I2C при каждом старте.
Производитель поставляет её как C-массив в заголовке из пакета платы, без
лицензии, разрешающей распространение, поэтому в этом компоненте её нет.
Программа, которая собирается для этой платы, встраивает её сама. Без неё
плата собирается и работает с выключенным тачем: `board_touch_start`
возвращает `false`, и лог говорит почему.

## Создание файла

`tools/gsl_firmware.py` из DGX-DI превращает массив производителя в компактный
файл:

```sh
python3 managed_components/jef-sure__dgx-di/tools/gsl_firmware.py \
    path/to/esp_lcd_touch_gsl3680.h main/jc8012p4a1c_touch.fw --range 1664x896
```

`--range` — диапазон сырых координат, которые сообщает прошивка и о котором
массив ничего не говорит; 1664x896 — диапазон JC8012P4A1C, и он совпадает с
`x_max` и `y_max` в данных платы.

## Встраивание

В `main/CMakeLists.txt` программы:

```cmake
idf_component_register(SRCS "main.c"
                       PRIV_REQUIRES jef-sure__boards
                       EMBED_FILES "jc8012p4a1c_touch.fw")
```

ESP-IDF помещает файл во флеш с символами
`_binary_jc8012p4a1c_touch_fw_start` и `_end`. В программе определите хук,
который компонент объявляет в `boards.h`:

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

Собственная `board_touch_firmware` компонента слабая и возвращает `false`;
сильное определение программы занимает её место при компоновке. Клей платы
вызывает её в `board_touch_start`, передаёт байты драйверу GSL3680 из DGX-DI,
который записывает их в чип.

Программа, собираемая для нескольких плат, держит файл и функцию под условием,
чтобы сборка для CYD S028R не искала файл, которого у неё нет:

```cmake
if(CONFIG_BOARD_JC8012P4A1C AND EXISTS ${CMAKE_CURRENT_LIST_DIR}/jc8012p4a1c_touch.fw)
    set(TOUCH_FW "jc8012p4a1c_touch.fw")
endif()
idf_component_register(... EMBED_FILES ${TOUCH_FW})
if(TOUCH_FW)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE HAVE_TOUCH_FW=1)
endif()
```

и `#ifdef HAVE_TOUCH_FW` вокруг функции в C.
