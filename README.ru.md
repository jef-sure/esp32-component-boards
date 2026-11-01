# boards

*[In English: README.md](README.md)*

Компонент ESP-IDF, который описывает платы, на которых работает программа,
**один раз, как данные**, и настраивает их аппаратуру для программы. Каталог
на каждую плату в `catalog/boards/` хранит её пины, шины и периферию в одном
`board.json`; компонент превращает его в клей на C, а программа спрашивает
то, что ей нужно, **по роду**, а не по имени платы:

```c
#include "boards.h"
#include "boards_dgx.h"
#include "boards_dgx_di.h"

struct board_display display = {0};
if (board_display_init(&display)) {
    /* display.width, display.height: 1024x600 or 320x240, whatever the chosen board has;
       display.mm_w, display.mm_h: its size in millimetres */
    dgx_screen_t *screen = board_dgx_screen(&display);
}

struct board_touch touch;
if (board_touch_start(&display, &touch)) {
    /* the touch panel under that display, calibrated by the board's data */
    dgx_di_pointer_t *pointer = board_dgx_di_pointer(&touch);
}
```

Каждая функция `boards.h` существует на каждой плате. Функция для того, чего
у платы нет, возвращает `false`, и программа идёт дальше без него. `boards.h` не
называет ни одной библиотеки: дескрипторы DGX, DGX-DI или hd44780 дают заголовки их
адаптеров. Один и тот
же `main.c` собирается и работает на 2,8-дюймовой CYD S028R и на 10,1-дюймовой
Guition.

Сам по себе компонент не знает никакого дисплея: у платы его может не быть, а
дисплей — одна периферия среди прочих. Что сегодня может быть у платы:

- **графический дисплей** под управлением [DGX](https://github.com/jef-sure/esp32-component-dgx):
  панели MIPI-DSI, QSPI или SPI, с их размером в пикселях и в миллиметрах и
  тем, как они лежат на плате;
- **символьный дисплей** (HD44780, 2004 на переходнике PCF8574) через
  [hd44780](https://github.com/jef-sure/esp32-component-hd44780), на плате
  или как модуль на её шине I2C;
- **тач-панель** как устройство [DGX-DI](https://github.com/jef-sure/esp32-component-dgx-di),
  с калибровкой, измеренной на плате и хранящейся в данных;
- **LVGL** через [DGX-LVGL](https://github.com/jef-sure/esp32-component-dgx-lvgl):
  дисплей и тач-панель, которые настраивает компонент, становятся дисплеем и
  устройством ввода LVGL, см. [examples/hello_lvgl](examples/hello_lvgl);
- **звук**: кодек ES8311 на I2S, усилитель на I2S или собственный ЦАП ESP32;
- **камера**, пока как данные: её шина, разъём и сенсор описаны, компонент её не запускает;
- **кнопка**; и любая **шина**, которую плата разводит, даже та, которую
  компонент сам не настраивает (SDIO радиомодуля, пины слота SD), хранящаяся
  как данные, которые программа может прочитать.

## Выбор платы

Плата называется один раз, в одной командной строке. `tools/board_select.py`
компонента записывает в проект `sdkconfig.defaults.board`: настройки чипа,
памяти и флеша платы и строку, которая выбирает её в меню конфигурации.

```sh
idf.py add-dependency "jef-sure/boards^0.0.1"
python3 managed_components/jef-sure__boards/tools/board_select.py cyd_s028r .
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
`idf_component.yml` компонента, так что сборка для CYD S028R не скачивает ни драйвер
GT911, ни библиотеку кодека. См. [docs/ru/choosing-a-board.md](docs/ru/choosing-a-board.md).

## Платы

<!-- boards:table -->
| плата | чип | дисплей | тач | звук | кнопка |
|---|---|---|---|---|---|
| CYD (ESP32-2432S028R) | ESP32 | 320x240 ILI9341, SPI, 58x43 mm | XPT2046 (резистивный) | DAC, GPIO26 | да |
| ESP32 DevKit, 4 MB | ESP32 | нет | нет | нет | да |
| Waveshare ESP32-P4-ETH | ESP32-P4 | нет | нет | ES8311 | да |
| Waveshare ESP32-P4-POE-ETH | ESP32-P4 | нет | нет | ES8311 | да |
| ESP32-S3 DevKit, 16 MB, 8 MB PSRAM | ESP32-S3 | нет | нет | нет | да |
| Guition JC1060P470C | ESP32-P4 | 1024x600 JD9165, MIPI-DSI, 154x86 mm | GT911 | ES8311 | да |
| Guition JC4827W543C | ESP32-S3 | 480x272 NV3041A, QSPI, 95x54 mm | GT911 | усилитель I2S | да |
| Guition JC8012P4A1C | ESP32-P4 | 1280x800 JD9365, MIPI-DSI, 217x136 mm | GSL3680 (прошивку встраивает программа) | ES8311 | да |
<!-- boards:end -->

Модуль едет на любой выбранной плате: `board_select.py cyd_s028r --module
lcd2004_pcf8574 .` добавляет символьный LCD 20x4 на шину I2C платы.

GSL3680 10,1-дюймовой платы не хранит
собственной прошивки, а массив производителя не несёт лицензии на
распространение: программа встраивает его сама, см.
[docs/ru/touch-firmware.md](docs/ru/touch-firmware.md); без него плата
собирается и работает с выключенным тачем.

## Что в репозитории

```
catalog/boards/<board>/board.json         плата: единственный источник правды
catalog/devices/, catalog/mcu/            что за чипы на ней, лежат под ней
catalog/libraries/                        что каждая библиотека делает с каждым чипом и что требуют её версии
catalog/boards/<board>/sdkconfig.defaults что нужно её чипу, памяти и флешу; строки, которые её выбирают
boards/<board>/<board>.c, board.cmake  клей, сгенерированный из данных и закоммиченный
boards/boards.cmake, Kconfig           тоже сгенерированы, как и зависимости в idf_component.yml
include/boards.h                       что программа спрашивает, по роду
src/                                   ядро: board_info, общие I2C и SPI, задача звука, хук прошивки тача
adapters/<владелец>__<имя>/            код под каждую библиотеку, её публичный заголовок в include/
tools/boards_gen.py                    данные -> клей, Kconfig, списки, правила манифеста, таблицы README
tools/check_format.py                  схема, правила и их случаи в test/format/
tools/check_boards.py                  сгенерированное совпадает с данными; пины не пересекаются; API полон
tools/board_pins.py                    карта пинов платы и её дерево
tools/board_select.py                  выбор платы для проекта
tools/board_bom.py                     что купить для изделия, с ценами диапазонами
editor/                                страница: что собрать, комплект, проект; и редактор. Любой статический сервер из корня, затем /editor/
examples/hello_board/                  самая маленькая программа, собирается в CI для каждой платы
examples/hello_lvgl/                   LVGL через DGX-LVGL, собирается в CI для каждой платы с графическим дисплеем
examples/local_boards/                 плата и модуль самой программы, в components/local-boards/
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

Скопируйте ближайшую `catalog/boards/<board>/`, отредактируйте `board.json`, напишите её
`sdkconfig.defaults` с причинами в комментариях, запустите
`python3 tools/boards_gen.py --all`, затем `python3 tools/check_boards.py
--host-syntax`. Плата оказывается в меню, в манифесте и в таблице README, и
ни одного из них не нужно трогать. Измерьте тач на плате
(`dgx_di_calibrate_measure` из DGX-DI) и отдайте лог `tools/board_calibration.py`.
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
матрица `.github/workflows/build.yml`. `examples/hello_board` и
`examples/hello_lvgl` прошиты на CYD S028R, JC4827W543C и JC1060P470C под ESP-IDF 6.1:
дисплей, тач и звук запускаются без ошибок в логе. Координаты касаний проверены
пальцем на всех трёх и верны. На JC1060P470C проверено и изображение: цвета и ориентация. Модуль 2004 показывает текст
на девките ESP32. На JC8012P4A1C, тоже прошитой, дисплей запускается, а звук `hello_board` услышан. Её
тач требует прошивку, которую встраивает программа: с ней лог чистый, пальцем никто не проверял.

Дисплей-модуль `tft153_st77916` запускался на `esp32s3_devkit` как плата программы, изображение видели.
На этих пинах ESP-IDF 6.1 требует DGX 0.10.3: драйвер SPI версии 6.1 принимает четырёхлинейную шину за
восьмилинейную. `esp32_devkit` запускался как основа платы программы.

Лицензия: MIT.
