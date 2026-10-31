# API: boards.h

`#include "boards.h"`. Каждая функция ниже существует на каждой плате. Функция
для части, которой у платы нет, возвращает `false` (или `NULL`) и не трогает свой
выход; программе не нужен `#if` на плату. `boards.h` не называет ни одной библиотеки:
он даёт размеры, миллиметры и ориентацию. Дескрипторы библиотеки даёт заголовок её
адаптера, и дальше программа использует эту библиотеку напрямую: `boards_dgx.h`,
`boards_dgx_di.h`, `boards_hd44780.h`.

## Что это за плата

```c
struct board_info { const char *name, *title, *target; };
const struct board_info *board_info(void);
```

`name` — каталог в `catalog/boards/` (`"cyd_s028r"`), `title` — то, что показывало
меню, `target` — чип (`"esp32"`, `"esp32s3"`, `"esp32p4"`). Для лога и для
страницы настроек, а не для того, чтобы решать, что делать: вместо этого
спрашивайте по роду.

## Графический дисплей

```c
struct board_display {
    int   width, height; /* as it lies, in pixels */
    int   mm_w, mm_h;    /* as it lies, in millimetres; 0 when the data has no size */
    int   dir_x, dir_y;  /* BOARD_DIR_FORWARD: left to right, top to bottom; BOARD_DIR_BACKWARD: the other way */
    bool  swap_xy;
    const char *name; /* its name in the data, for the log */
    int   index;      /* its place among the displays of the board */
};
int  board_display_count(void);
bool board_display_init(struct board_display *out);
bool board_display_init_at(int index, struct board_display *out);
bool board_display_orientation(struct board_display *display, int dir_x, int dir_y, bool swap_xy);
```

Дисплеев на плате может быть несколько. `board_display_init` запускает основной,
`board_display_init_at` принимает его номер, 0 — основной. Повторный вызов отдаёт тот
же дисплей. У дисплеев, которые данные объединяют в один экран (`display_groups`), есть
свой номер: запуск по нему поднимает оба и отдаёт один широкий экран. Такой экран не
поворачивается: `board_display_orientation` возвращает `false`, а у каждого из двух
остаётся своя ориентация. `board_touch_start` принимает дисплей, над которым лежит тач,
и возвращает `false` для другого.

`board_display_init` поднимает панель с включённой подсветкой, ориентированную
так, как показывает плата (`original_orientation` из данных), и заполняет
`*out`. Дескрипторы DGX лежат в `boards_dgx.h`:

```c
dgx_screen_t        *board_dgx_screen(const struct board_display *display);
dgx_bus_protocols_t *board_dgx_bus(const struct board_display *display);
```

На экране рисует `dgx_draw.h`. Шина нужна для того, что знает только она: на
MIPI-DSI это `dgx_dsi_frame_us()`, чтобы задавать темп рисования по кадрам панели, и
`dgx_dsi_bench()` / `dgx_dsi_tune()`, чтобы измерить плату один раз и сохранить числа
(см. [calibration.md](calibration.md)).

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
struct board_character_display { int cols, rows; };
bool board_character_display_init(struct board_character_display *out);
```

HD44780, который есть у платы, или который приносит модуль на её шине I2C.
Дисплей настроен, очищен, его подсветка включена. `board_hd44780(&lcd)` из
`boards_hd44780.h` даёт `hd44780_t *` для `lcd_set_cursor`, `lcd_write_str` и
остального из `hd44780.h`. hd44780 компонуется только когда он есть в сборке
(`CONFIG_BOARD_DISPLAY_HD44780`), поэтому в программе, работающей на платах без него,
подключайте заголовок под этим символом.

## Тач-панель

```c
struct board_touch { int fingers; int x_max, y_max; const char *name; int index; };
int  board_touch_count(void);
bool board_touch_start(const struct board_display *display, struct board_touch *out);
bool board_touch_start_at(int index, const struct board_display *display, struct board_touch *out);
```

Настраивает панель под дисплеем, полученным раньше, с измеренной калибровкой платы.
`board_touch_start` берёт первую панель над этим дисплеем, `board_touch_start_at` — панель по
её месту. Повторный вызов даёт ту же панель. `out` может быть `NULL`. Устройство и указатель на
нём даёт `boards_dgx_di.h`:

```c
dgx_di_device_t  *board_dgx_di_device(const struct board_touch *touch);
dgx_di_pointer_t *board_dgx_di_pointer(const struct board_touch *touch);
```

Указатель следует за ориентацией дисплея: после `board_display_orientation` его
координаты — координаты дисплея как он лежит теперь. Задача, которая его
читает, — дело программы:

```c
#include "boards_dgx_di.h"
struct board_touch touch;
board_touch_start(&display, &touch);
dgx_di_pointer_t *pointer = board_dgx_di_pointer(&touch);
for (;;) {
    dgx_di_pointer_read(pointer, now_ms);
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
Guition): версия компонента слабая и возвращает `false`; программа, встраивающая
прошивку, определяет эту функцию сама. См.
[touch-firmware.md](touch-firmware.md).

## Звук

```c
typedef void (*board_sound_source_t)(int16_t *samples, size_t count);
int  board_sound_count(void);
bool board_sound_start(board_sound_source_t source, uint32_t *rate_out);
bool board_sound_start_at(int index, board_sound_source_t source, uint32_t *rate_out);
void board_sound_source(board_sound_source_t source);
void board_sound_source_at(int index, board_sound_source_t source);
```

Функции без `_at` относятся к первому выходу.

`board_sound_start` настраивает кодек, усилитель или ЦАП и запускает задачу, которая
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
возвращает пины и скорость шины SPI платы на этом хосте; устройство подключается
к ней со своим `cs`.

`NULL` возвращается, если такой шины нет, а также если на шине только дисплей.
Такую шину настраивает DGX и не отпускает её между рисованиями, поэтому
устройство программы на ней ждало бы шину вечно.

Если на шине дисплея по данным платы есть ещё тач или SD, шину настраивает
компонент, а дисплей подключается к ней через `dgx_spi_init_on_bus()`. Тогда
дисплей занимает шину только на время рисования. Своим устройством можно
пользоваться между рисованиями, но не внутри пакета `dgx_screen_progress_up()`
в той же задаче: дисплей держит шину до конца пакета.

`board_spi_taken` говорит, занят ли хост какой-либо шиной платы, SPI или QSPI,
так что можно найти свободный хост. `board_bus_get("nfc_in_nfc", "cs", &pin)` даёт линии
устройства, которое компонент не настраивает, по его имени в данных.
`board_bus_get("sdio.sdio0", "clk", &pin)`
читает любое число любой шины, которую называют данные, включая роды, которые
компонент не настраивает.

## Кнопки

```c
int         board_button_count(void);
const char *board_button_name(int index);
bool        board_button(bool *pressed);
bool        board_button_at(int index, bool *pressed);
```

`false`, когда у платы её нет; иначе пин настраивается при первом вызове, а
`*pressed` — его состояние сейчас. Подавление дребезга и удержания — дело
программы.

## Что подключать, что компоновать

Компонент компонует библиотеки, которые нужны выбранной плате (DGX, DGX-DI,
hd44780, драйвер тача, esp_codec_dev), и их пути include доходят до программы
через него. Программа, работающая на платах с какой-то частью и без неё,
подключает заголовок адаптера под символом, который говорит, что часть есть:

```c
#if CONFIG_BOARD_DISPLAY_GRAPHICS
#include "boards_dgx.h"
#include "dgx_draw.h"
#endif
#if CONFIG_BOARD_TOUCH
#include "boards_dgx_di.h"
#endif
#if CONFIG_BOARD_DISPLAY_HD44780
#include "boards_hd44780.h"
#endif
```

Программа, у которой дисплей есть всегда, может подключать эти заголовки
безусловно и назвать `jef-sure/dgx` также и в собственном манифесте.
