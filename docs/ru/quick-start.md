# Быстрый старт

Программа на плате за несколько минут: компонент настраивает плату, а программа запрашивает её части по типу, а не по
имени платы.

Нужны ESP-IDF 5.5 или 6.x в оболочке (`idf.py --version` отвечает), Python 3.9 или новее и плата из
[таблицы README](../../README.ru.md#платы) на USB. Здесь пример — CYD S028R (ESP32-2432S028R, 2,8 дюйма); для другой платы
вместо `cyd_s028r` подставьте её имя из таблицы.

## 1. Проект с компонентом

```sh
idf.py create-project hello && cd hello
idf.py add-dependency "jef-sure/boards>=0.0.5"
```

## 2. CMake, который читает плату

В `CMakeLists.txt` строка `include($ENV{IDF_PATH}/tools/cmake/project.cmake)` заменяется этими строками, include
остаётся среди них. Они читают умолчания платы перед собственными умолчаниями проекта и дают каждой плате свой lock
компонентов:

```cmake
# BOARD=<board>, which the preset of a board sets, builds with sdkconfig.defaults.<board> that board_select.py writes,
# then with the program's own sdkconfig.defaults when it has one. A -D SDKCONFIG_DEFAULTS=... on the command line wins.
set(BOARD "" CACHE STRING "a board of this project: its file sdkconfig.defaults.<board>")
if(NOT SDKCONFIG_DEFAULTS AND BOARD)
    if(NOT EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.${BOARD})
        message(FATAL_ERROR "no sdkconfig.defaults.${BOARD} here: run board_select.py ${BOARD} . of jef-sure/boards")
    endif()
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.${BOARD}")
    if(EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults)
        list(APPEND SDKCONFIG_DEFAULTS "sdkconfig.defaults")
    endif()
endif()
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
if(BOARD)
    idf_build_set_property(DEPENDENCIES_LOCK ${CMAKE_CURRENT_LIST_DIR}/dependencies.lock.${BOARD})
endif()
```

## 3. Плата, один раз

```sh
idf.py reconfigure
python3 managed_components/jef-sure__boards/tools/board_select.py cyd_s028r .
```

Первая команда скачивает компонент в `managed_components/`. Вторая пишет `sdkconfig.defaults.cyd_s028r` (чип, флеш,
память и строку выбора платы), `CMakePresets.json` (пресет, который собирает плату в `build/cyd_s028r`) и lock
компонентов этой платы. Без `set-target` и без `menuconfig`.

## 4. Программа

`main/hello.c`:

```c
#include <stdio.h>

#include "boards.h"
#include "sdkconfig.h"
#if CONFIG_BOARD_DISPLAY_GRAPHICS
#include "boards_dgx.h"
#include "dgx_draw.h"
#endif

void app_main(void)
{
    const board_info_t *board = board_info();
    printf("the board: %s (%s), %s\n", board->title, board->name, board->target);

    board_display_t display = {0};
    if (board_display_init(&display)) {
        printf("the display: %d x %d pixels, %d x %d mm\n", display.width, display.height, display.mm_w, display.mm_h);
#if CONFIG_BOARD_DISPLAY_GRAPHICS
        dgx_screen_t *screen = board_dgx_screen(&display);
        dgx_fill_rectangle(screen, 0, 0, display.width, display.height, 0xffff);     /* white */
        dgx_fill_rectangle(screen, 0, 0, display.width, display.height / 8, 0x001f); /* a blue band at the top */
#endif
    }

    board_touch_t touch;
    if (board_touch_start(&display, &touch)) printf("the touch: %d fingers\n", touch.fingers);

    bool pressed;
    if (board_button(&pressed)) printf("the button: %s\n", pressed ? "held" : "free");
}
```

Каждая функция `boards.h` есть на каждой плате; для части, которой у платы нет, она возвращает `false`. Заголовок DGX —
для платы с графическим дисплеем, поэтому он включён под `CONFIG_BOARD_DISPLAY_GRAPHICS`.
[examples/hello_board](../../examples/hello_board) — то же самое со звуком и символьным дисплеем.

## 5. Собрать, прошить, посмотреть

```sh
idf.py build flash monitor
```

ESP-IDF 6 собирает пресет платы в `build/cyd_s028r`. ESP-IDF 5 пресеты не читает:
`idf.py -B build/cyd_s028r -D SDKCONFIG=build/cyd_s028r/sdkconfig -D BOARD=cyd_s028r build flash monitor`.

Лог CYD S028R:

```
the board: CYD (ESP32-2432S028R) (cyd_s028r), esp32
the display: 320 x 240 pixels, 58 x 43 mm
the touch: 1 fingers
the button: free
```

На экране белый фон и синяя полоса сверху. Если держать BOOT при сбросе, последняя строка скажет `held`.

## Другая плата или несколько

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py jc4827w543c .
idf.py build flash monitor
```

Та же программа на прошитой так JC4827W543C:

```
the board: Guition JC4827W543C (jc4827w543c), esp32s3
the display: 480 x 272 pixels, 95 x 54 mm
the touch: 5 fingers
the button: free
```

Плата, названная последней, становится текущей; `idf.py --preset cyd_s028r build` собирает другую, каждую в своём
`build/<плата>`. См. [choosing-a-board.md](choosing-a-board.md).

## Без правки файлов: одна команда или страница

С клоном репозитория проект создаётся целиком, CMake и программа — среди его файлов:

```sh
git clone --depth 1 https://github.com/jef-sure/esp32-component-boards.git
python3 esp32-component-boards/tools/board_project.py hello --board cyd_s028r
cd hello && idf.py reconfigure && python3 managed_components/jef-sure__boards/tools/board_select.py --again . && idf.py build flash monitor
```

Страница подбирает плату и детали под устройство и пишет проект:

```sh
mkdir hello2 && python3 esp32-component-boards/tools/boards_mcp.py --serve --project hello2
```

Откройте ссылку, которую она печатает. См. [tools.md](tools.md#страница).

## Программа, которая уже есть

[moving-a-program.md](moving-a-program.md): компонент рядом с остальными зависимостями, строки CMake, платы названы один
раз, свой код плат заменён вызовами по типу.
