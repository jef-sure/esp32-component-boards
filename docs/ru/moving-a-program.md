# Переезд программы со своими платами

У программы, которая уже работает на нескольких платах, есть свой слой для них: выбор платы в её Kconfig, файл
умолчаний на каждую плату и код под `#if`, который настраивает дисплей, сенсорную панель и кнопку каждой. Здесь
описано, как такая программа переезжает на компонент, на примере рукописных часов. Копия часов, перенесённая так,
собрана и работает на Guition JC1060P470C и JC8012P4A1C, с тачем.

## Что было у часов

- `main/Kconfig.projbuild`: `choice CLOCK_BOARD` с `CLOCK_BOARD_JC1060P470` и `CLOCK_BOARD_JC8012P4A1C`, каждый
  включает драйверы DGX своей панели.
- Файлы умолчаний: `sdkconfig.defaults`, `sdkconfig.defaults.esp32`, `sdkconfig.defaults.esp32p4`,
  `sdkconfig.defaults.esp32p4.jc1060p470`, `sdkconfig.defaults.esp32p4.jc8012p4a1c` и `sdkconfig.defaults.idf5`.
  Файлы двух плат на P4 держат выбор платы и строки ревизии чипа.
- `main/display.c` и `main/touch.c`: для каждой платы под `#if CONFIG_CLOCK_BOARD_...` пины, шина, драйвер,
  ориентация, подсветка и калибровка сенсорной панели. `main/main.c` читал пин BOOT по его номеру для каждого чипа.
- `main/idf_component.yml`: `jef-sure/dgx`, `jef-sure/dgx-di` и драйвер тача 7-дюймовой платы по правилу на
  `CLOCK_BOARD_JC1060P470`.

## Шаги

1. Компонент добавляется в `main/idf_component.yml` рядом с тем, чем программа пользуется сама:

   ```sh
   idf.py add-dependency "jef-sure/boards>=0.0.7"
   ```

   Правило, которое приносило драйвер тача одной платы, уходит: компонент приносит части выбранной платы. То, что
   программа зовёт сама, остаётся, как `jef-sure/dgx-di` для жестов часов.

2. Верхний `CMakeLists.txt` получает строки из [choosing-a-board.md](choosing-a-board.md#новый-проект) до
   `project.cmake` и lock каждой платы после него. Свои строки идут после них, как список умолчаний часов для ESP-IDF 5:

   ```cmake
   include($ENV{IDF_PATH}/tools/cmake/version.cmake)
   if(IDF_VERSION_MAJOR LESS 6)
       list(APPEND SDKCONFIG_DEFAULTS "sdkconfig.defaults.idf5")
   endif()
   ```

   `main/CMakeLists.txt` ничего для него не называет: менеджер компонентов сам делает компонент зависимостью `main`.

3. Платы называются один раз:

   ```sh
   idf.py reconfigure
   python3 managed_components/jef-sure__boards/tools/board_select.py jc1060p470c jc8012p4a1c .
   ```

   Это пишет `sdkconfig.defaults.jc1060p470c` и `sdkconfig.defaults.jc8012p4a1c` со строками ревизии чипа из данных,
   `CMakePresets.json` и lock на каждую плату. Файлы программы для одной платы, `sdkconfig.defaults.esp32p4.jc1060p470`
   и `sdkconfig.defaults.esp32p4.jc8012p4a1c`, уходят. Плата с чипом другой ревизии называется отдельной командой, с
   `--revision`.

4. Выбор платы программы уходит из `main/Kconfig.projbuild`: платы теперь в меню *Boards → Board the program runs on*.
   Опция программы, зависевшая от платы, зависит от того, что у платы есть. Прогноз часов листается касанием, поэтому
   вместо `default y if IDF_TARGET_ESP32P4` у него теперь:

   ```
   depends on BOARD_TOUCH != 0
   ```

   `BOARD_TOUCH` — символ типа `int`: голое `depends on BOARD_TOUCH` ложно при любом значении.

5. Код плат становится вызовами по типу. Дисплей в `main/display.c`, две ветки пинов, шин и драйверов, теперь такой:

   ```c
   board_display_t board;
   if (!board_display_init(&board)) {
       ESP_LOGE(TAG, "board_display_init failed");
       return NULL;
   }
   display = board_dgx_screen(&board);
   display_bus = board_dgx_bus(&board);
   ```

   Сенсорная панель берётся через `board_touch_start` и `board_dgx_di_pointer`, с калибровкой из данных платы; кнопка —
   через `board_button`. Прошивку GSL3680 10-дюймовой платы по-прежнему встраивает программа, а
   `board_touch_firmware_set` отдаёт её компоненту до `board_touch_start`, см. [touch-firmware.md](touch-firmware.md).

## Что остаётся программе

- Её собственный `sdkconfig.defaults`, который читается после файла платы: тик FreeRTOS, таблица разделов, то, что
  нужно её библиотекам. Строка, которую задают оба, берёт значение программы как более позднее. Цель берётся из файла
  платы, первого файла, который её называет.
- Файл ESP-IDF для цели, как `sdkconfig.defaults.esp32p4` у часов, по-прежнему читается после `sdkconfig.defaults` для
  этого чипа. `board_select.py` не считает его файлом платы: его первая строка — не команда.
- Её библиотеки, шрифты и встроенные файлы.

## Страница в программе

`python3 managed_components/jef-sure__boards/tools/boards_mcp.py --serve --project .` открывает страницу для программы.
Папка с `CMakeLists.txt` получает только то, что делает страница: плату программы в `components/local-boards/` для
комплекта с модулями, `sdkconfig.defaults.<плата>`, `selection.json`, а через `board_select.py --again` — пресеты и
клей. Строки CMake и манифеста, которых у программы нет, показываются, чтобы вписать их руками. Имя проекта страница
делает из `project()`: `handwritten-clock` становится `handwritten_clock`, а плата программы —
`handwritten_clock_<плата>`.
