# API: boards.h

`#include "boards.h"`. Каждая функция ниже существует на каждой плате. Функция
для части, которой у платы нет, отвечает `false` (или `NULL`) и не трогает свой
выход; программе не нужен `#if` на плату. Дескрипторы, которые дают функции, —
это дескрипторы библиотек, управляющих аппаратурой: дальше программа использует
DGX, DGX-DI и hd44780 напрямую.

## Что это за плата

```c
struct board_info { const char *name, *title, *target; };
const struct board_info *board_info(void);
```

`name` — каталог в `boards-data/` (`"cyd"`), `title` — то, что показывало
меню, `target` — чип (`"esp32"`, `"esp32s3"`, `"esp32p4"`). Для лога и для
страницы настроек, а не для того, чтобы решать, что делать: вместо этого
спрашивайте по роду.

## Дисплей с кадровым буфером

```c
struct board_display {
    void *screen;        /* dgx_screen_t * */
    void *bus;           /* dgx_bus_protocols_t *, NULL when none */
    int   width, height; /* as it lies, in pixels */
    int   mm_w, mm_h;    /* as it lies, in millimetres */
    int   dir_x, dir_y;  /* dgx_orientation_t values: 1 left-right / top-bottom, -1 the other way */
    bool  swap_xy;
};
bool board_display_init(struct board_display *out);
bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy);
```

`board_display_init` поднимает панель с включённой подсветкой, ориентированную
так, как показывает плата (`original_orientation` из данных), и заполняет
`*out`. `screen` — экран DGX: `#include "dgx_draw.h"` и рисуйте. `bus` — шина
DGX панели, для того, что знает только шина: на MIPI-DSI это
`dgx_dsi_frame_us()`, чтобы задавать темп рисования по кадрам панели, и
`dgx_dsi_bench()` / `dgx_dsi_tune()`, чтобы измерить плату один раз и
сохранить числа (см. [calibration.md](calibration.md)).

`board_display_orientation` поворачивает дисплей: вызывает собственную функцию
ориентации драйвера панели с этими значениями и обновляет `width`, `height`,
`mm_w`, `mm_h`, `dir_x`, `dir_y`, `swap_xy`. Чтобы показать плату другой
стороной вверх, переверните оба направления относительно того, что оставила
инициализация:

```c
board_display_orientation(&display, -display.dir_x, -display.dir_y, display.swap_xy);
```

Миллиметры — это измеренный размер картинки как лежит: жесты DGX-DI и шрифты
DGX используют их, чтобы сантиметр был сантиметром на каждой плате.

## Символьный дисплей

```c
struct board_character_display { void *lcd; int cols, rows; };
bool board_character_display_init(struct board_character_display *out);
```

HD44780, который есть у платы, или который приносит модуль на её шине I2C.
Дисплей настроен, очищен, его подсветка включена; `lcd` — это `hd44780_t *`:
`#include "hd44780.h"`, затем `lcd_set_cursor`, `lcd_write_str` и остальное из
этого заголовка. hd44780 компонуется только когда он есть в сборке
(`CONFIG_BOARD_DISPLAY_HD44780`), поэтому в программе, работающей на платах
без него, подключайте его заголовок под этим символом.

## Тач-панель

```c
bool board_touch_start(const struct board_display *display,
                       struct dgx_di_device **device_out, void **pointer_out);
```

Настраивает панель под дисплеем, полученным раньше, и даёт устройство DGX-DI
(`dgx_di_device_t *`) и указатель на нём (`dgx_di_pointer_t *`, передаётся как
`void *`: DGX-DI объявляет этот тип без тега структуры, а `boards.h` ничего из
DGX-DI не включает), откалиброванный измеренной калибровкой платы. Указатель
следует за ориентацией дисплея: после `board_display_orientation` его
координаты — координаты дисплея как он лежит теперь. Задача, которая его
читает, — дело программы:

```c
#include "dgx_di.h"
struct dgx_di_device *device;
void *pointer;
board_touch_start(&display, &device, &pointer);
for (;;) {
    dgx_di_pointer_read(pointer, now_ms);   /* void * converts to dgx_di_pointer_t * in C */
    int x, y;
    if (dgx_di_pointer_first(pointer, &x, &y)) { /* the first finger, in pixels of the display */ }
    vTaskDelay(pdMS_TO_TICKS(10));
}
```

Предупреждения в логе: *the calibration is not this board's* означает, что
калибровка в данных измерена на другом размере дисплея или диапазоне панели;
*a placeholder, not measured* означает, что в данных стоит `"measured": false`.
Тач работает в обоих случаях, только неточно.

```c
bool board_touch_firmware(const uint8_t **start, size_t *size);
```

Хук для панели, которая не хранит собственной прошивки (GSL3680 10,1-дюймовой
Guition): версия компонента слабая и отвечает `false`; программа, встраивающая
прошивку, определяет эту функцию сама. См.
[touch-firmware.md](touch-firmware.md).

## Звук

```c
typedef void (*board_sound_source_t)(int16_t *samples, size_t count);
bool board_sound_start(board_sound_source_t source, uint32_t *rate_out);
void board_sound_source(board_sound_source_t source);
```

`board_sound_start` настраивает кодек (или ЦАП) и запускает задачу, которая
просит у `source` следующие `count` сэмплов, 16-битных моно с частотой
`*rate_out`, и отправляет их; записи блокируются на железе, которое и задаёт
темп. `source` может быть `NULL` для тишины и быть задан позже через
`board_sound_source`. Задача работает, пока не остановится прошивка. Микшер,
громкость, формат, отличный от 16-битного моно, — дело программы: здесь железо
и его темп, ничего больше.

## Шины

```c
struct board_spi_bus { int host, mosi, miso, sclk; unsigned long hz; };
const struct board_spi_bus *board_spi_bus(int host);
bool board_spi_taken(int host);
bool board_bus_get(const char *bus, const char *field, long *out);
```

Для программы, добавляющей собственное устройство. `board_spi_bus(SPI3_HOST)`
даёт пины и скорость обычной шины SPI, которую плата разводит на этом хосте,
или `NULL`; устройство подключается к ней со своим собственным `cs`.
`board_spi_taken` говорит, занят ли хост какой-либо шиной платы, SPI или QSPI,
так что можно найти свободный хост. `board_bus_get("sdio.sdio0", "clk", &pin)`
читает любое число любой шины, которую называют данные, включая роды, которые
компонент не настраивает.

## Кнопка

```c
bool board_button(bool *pressed);
```

`false`, когда у платы её нет; иначе пин настраивается при первом вызове, а
`*pressed` — его состояние сейчас. Подавление дребезга и удержания — дело
программы.

## Что подключать, что компоновать

Компонент компонует библиотеки, которые нужны выбранной плате (DGX, DGX-DI,
hd44780, драйвер тача, esp_codec_dev), и их пути include доходят до программы
через него. Программа, работающая на платах с какой-то частью и без неё,
подключает заголовок библиотеки под символом, который говорит, что часть есть:

```c
#if CONFIG_BOARD_DISPLAY_FRAMEBUFFER
#include "dgx_draw.h"
#endif
#if CONFIG_BOARD_TOUCH
#include "dgx_di.h"
#endif
#if CONFIG_BOARD_DISPLAY_HD44780
#include "hd44780.h"
#endif
```

Программа, у которой дисплей есть всегда, может подключать `dgx_draw.h`
безусловно и назвать `jef-sure/dgx` также и в собственном манифесте.
