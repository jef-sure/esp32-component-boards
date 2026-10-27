# boards

*[In English: README.md](README.md)*

Компонент ESP-IDF, который описывает платы, на которых работает программа,
**один раз, как данные**, и настраивает их аппаратуру для программы. Каталог
на каждую плату в `boards-data/` хранит её пины, шины и периферию в одном
`board.json`; компонент превращает его в клей на C, а программа спрашивает
то, что ей нужно, **по роду**, а не по имени платы:

```c
#include "boards.h"

struct board_display display;
if (board_display_init(&display)) {
    /* display.screen is a dgx_screen_t *, 1024x600 or 320x240, whatever the chosen
       board has; display.mm_w / mm_h is its size in millimetres */
}

struct dgx_di_device *device;
void                 *pointer; /* a dgx_di_pointer_t * */
if (board_touch_start(&display, &device, &pointer)) {
    /* the touch panel under that display, calibrated by the board's data */
}
```

Каждая функция `boards.h` существует на каждой плате. Функция для того, чего
у платы нет, отвечает `false`, и программа идёт дальше без него. Один и тот
же `main.c` собирается и работает на 2,8-дюймовой CYD и на 10,1-дюймовой
Guition.

Сам по себе компонент не знает никакого дисплея: у платы его может не быть, а
дисплей — одна периферия среди прочих. Что сегодня может быть у платы:

- **дисплей с кадровым буфером** под управлением [DGX](https://github.com/jef-sure/esp32-component-dgx):
  панели MIPI-DSI, QSPI или SPI, с их размером в пикселях и в миллиметрах и
  тем, как они лежат на плате;
- **символьный дисплей** (HD44780, 2004 на переходнике PCF8574) через
  [hd44780](https://github.com/jef-sure/esp32-component-hd44780), на плате
  или как модуль на её шине I2C;
- **тач-панель** как устройство [DGX-DI](https://github.com/jef-sure/esp32-component-dgx-di),
  с калибровкой, измеренной на плате и хранящейся в данных;
- **звук**: кодек ES8311 на I2S или собственный ЦАП ESP32;
- **кнопка**; и любая **шина**, которую плата разводит, даже та, которую
  компонент сам не настраивает (SDIO радиомодуля, пины слота SD), хранящаяся
  как данные, которые программа может прочитать.

## Выбор платы

Плата называется один раз, в одной командной строке. `tools/board_select.py`
компонента записывает в проект `sdkconfig.defaults.board`: настройки чипа,
памяти и флеша платы и строку, которая выбирает её в меню конфигурации.

```sh
idf.py add-dependency "jef-sure/boards^0.0.1"
python3 managed_components/jef-sure__boards/tools/board_select.py cyd .
idf.py build flash monitor
```

`CMakeLists.txt` проекта читает этот файл перед своими собственными
умолчаниями:

```cmake
if(NOT SDKCONFIG_DEFAULTS AND EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.board)
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.board;sdkconfig.defaults")
endif()
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
```

Ни `set-target`, ни `menuconfig`. Меню (*Boards → Board the program runs
on*) следует за файлом; оно есть, чтобы посмотреть и чтобы переопределить. Что
нужно плате, приходит вместе с выбором: драйверы DGX её панели — как
`select`-ы, остальные части (драйвер тача, кодек, hd44780) — по правилам в
`idf_component.yml` компонента, так что сборка для CYD не скачивает ни драйвер
GT911, ни библиотеку кодека. См. [docs/ru/choosing-a-board.md](docs/ru/choosing-a-board.md).

## Платы

<!-- boards:table -->
| плата | чип | дисплей | тач | звук | кнопка |
|---|---|---|---|---|---|
| CYD (ESP32-2432S028R) | ESP32 | 320x240 ILI9341, SPI, 58x43 mm | XPT2046 (резистивный); калибровка-заглушка | DAC, GPIO26 | да |
| Guition JC1060P470 | ESP32-P4 | 1024x600 JD9165, MIPI-DSI, 154x86 mm | GT911 | ES8311 | да |
| Guition JC4827W543 | ESP32-S3 | 480x272 NV3041A, QSPI, 95x54 mm | GT911 | нет | нет |
| Guition JC8012P4A1C | ESP32-P4 | 1280x800 JD9365, MIPI-DSI, 217x136 mm | GSL3680 (прошивку встраивает программа) | ES8311 | нет |
<!-- boards:end -->

Модуль едет на любой выбранной плате: `board_select.py cyd --module
lcd2004_pcf8574 .` добавляет символьный LCD 20x4 на шину I2C платы.

Калибровка тача CYD — заглушка, пока её не измерят на плате; тач работает,
только неточно, и лог об этом говорит. GSL3680 10,1-дюймовой платы не хранит
собственной прошивки, а массив производителя не несёт лицензии на
распространение: программа встраивает его сама, см.
[docs/ru/touch-firmware.md](docs/ru/touch-firmware.md); без него плата
собирается и работает с выключенным тачем.

## Что в репозитории

```
boards-data/<board>/board.json         плата: единственный источник правды
boards-data/<board>/sdkconfig.defaults что нужно её чипу, памяти и флешу; строки, которые её выбирают
boards/<board>/<board>.c, board.cmake  клей, сгенерированный из данных и закоммиченный
boards/boards.cmake, Kconfig           тоже сгенерированы, как и зависимости в idf_component.yml
include/boards.h                       что программа спрашивает, по роду
src/                                   ядро: board_info, общий мастер I2C, указатель, хук прошивки тача
tools/boards_gen.py                    данные -> клей, Kconfig, списки, правила манифеста, таблицы README
tools/check_boards.py                  сгенерированное совпадает с данными; пины не пересекаются; API полон
tools/board_pins.py                    карта пинов платы и её дерево
tools/board_select.py                  выбор платы для проекта
editor/                                редактор данных: Vue + Pinia с CDN, без сборки
examples/hello_board/                  самая маленькая программа, собирается в CI для каждой платы
docs/en/, docs/ru/                     документация
```

Сгенерированные файлы закоммичены, так что программа, берущая компонент из
реестра компонентов, собирается без запуска каких-либо инструментов этого
репозитория. `tools/check_boards.py` падает в CI, когда они расходятся с
данными.

Документация, по-русски: [как это работает](docs/ru/how-it-works.md),
[формат данных](docs/ru/data-format.md), [API](docs/ru/api.md),
[выбор платы](docs/ru/choosing-a-board.md),
[добавление платы](docs/ru/adding-a-board.md), [инструменты](docs/ru/tools.md),
[калибровка](docs/ru/calibration.md), [прошивка тача](docs/ru/touch-firmware.md),
[модули](docs/ru/modules.md). По-английски: [docs/en/](docs/en/).

## Добавление платы

Скопируйте ближайшую `boards-data/<board>/`, отредактируйте `board.json`
(редактор в `editor/index.html` проверяет схему по мере ввода), напишите её
`sdkconfig.defaults` с причинами в комментариях, запустите
`python3 tools/boards_gen.py --all`, затем `python3 tools/check_boards.py
--host-syntax`. Плата оказывается в меню, в манифесте и в таблице README, и
ни одного из них не нужно трогать. Измерьте тач на плате
(`dgx_di_calibrate_measure` из DGX-DI) и вставьте результат в редактор.
См. [docs/ru/adding-a-board.md](docs/ru/adding-a-board.md).

## Чем это отличается от esp-bsp и esp_board_manager

[espressif/esp-bsp](https://github.com/espressif/esp-bsp) описывает собственные
платы Espressif вокруг LVGL: каждый манифест тянет `lvgl` и `esp_lvgl_port`, а
дисплей приходит как объект LVGL.
[espressif/esp_board_manager](https://github.com/espressif/esp_board_manager)
описывает платы в YAML и генерирует код инициализации в проект, а плата
выбирается через `idf.py bmgr`. Этот компонент — для собственных плат (в
первую очередь линейка Guition и CYD), не знает никакой библиотеки виджетов,
держит дисплей одной периферией среди прочих и держит данные достаточно
малыми, чтобы их мог прочитать и проверить скрипт: пины, шины, устройства,
измеренная калибровка. Что он берёт у esp-bsp — это механизм
`components/bsp_selector`: один Kconfig choice, скрытые символы рядом с ним,
правила манифеста на них.

## Состояние

0.0.1. Собирается для каждой платы, и с модулем, под ESP-IDF 5.5 и 6.1: это
матрица `.github/workflows/build.yml`. Клей повторяет код настройки
рукописных часов и DGX-GE, которые работают на этих платах; сам этот релиз
ещё не прошивался, и тач CYD ждёт своего измерения.

Лицензия: MIT.
