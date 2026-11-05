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
                       EMBED_FILES "jc8012p4a1c_touch.fw")
```

ESP-IDF помещает файл во флеш с символами
`_binary_jc8012p4a1c_touch_fw_start` и `_end`. В программе определите хук,
который компонент объявляет в `boards.h`:

```c
#include "boards.h"

extern const uint8_t touch_fw_start[] asm("_binary_jc8012p4a1c_touch_fw_start");
extern const uint8_t touch_fw_end[] asm("_binary_jc8012p4a1c_touch_fw_end");

void app_main(void)
{
    board_touch_firmware_set(touch_fw_start, (size_t)(touch_fw_end - touch_fw_start));
    /* затем board_display_init, board_touch_start, как для любой платы */
}
```

Клей платы берёт их в `board_touch_start` и передаёт драйверу GSL3680 из DGX-DI,
который записывает их в чип. Без этого вызова плата работает, тач выключен, и
`board_touch_start` пишет об этом в лог. Это вызов, а не функция, которую программа
определяет вместо функции компонента: сильное определение в файле, на который
программа больше ничем не ссылается, проигрывает слабому, и тач остался бы
выключенным без единого слова.

Программа, собираемая для нескольких плат, держит файл и вызов под условием,
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

и `#ifdef HAVE_TOUCH_FW` вокруг вызова в C.
