# API: boards.h

`#include "boards.h"`. Каждая функция ниже существует на каждой плате. Функция
для части, которой у платы нет, возвращает `false` (или `NULL`) и не трогает свой
выход; программе не нужен `#if` на плату. `boards.h` не называет ни одной библиотеки:
он даёт размеры, миллиметры и ориентацию. Дескрипторы библиотеки даёт заголовок её
адаптера, и дальше программа использует эту библиотеку напрямую: `boards_dgx.h`,
`boards_dgx_di.h`, `boards_hd44780.h`. У каждой публичной структуры есть typedef
с окончанием `_t`, например `board_display_t`; тег остаётся, чтобы заголовок
программы мог объявить её заранее (`struct board_display;`).

## Что это за плата

```c
typedef struct board_info { const char *name, *title, *target; } board_info_t;
const board_info_t *board_info(void);
```

`name` — каталог в `catalog/boards/` (`"cyd_s028r"`), `title` — то, что показывало
меню, `target` — чип, как его называет `CONFIG_IDF_TARGET` (`"esp32"`, `"esp32s3"`, `"esp32p4"`, `"esp32c3"`). Для лога и для
страницы настроек, а не для того, чтобы решать, что делать: вместо этого
спрашивайте по роду.

## Графический дисплей

```c
typedef struct board_display {
    int   width, height; /* as shown, in pixels */
    int   mm_w, mm_h;    /* as shown, in millimetres; 0 when the data has no size */
    int   dir_x, dir_y;  /* BOARD_DIR_FORWARD: left to right, top to bottom; BOARD_DIR_BACKWARD: the other way */
    bool  swap_xy;
    const char *name; /* its name in the data, for the log */
    int   index;      /* its place among the displays of the board */
} board_display_t;
int  board_display_count(void);
bool board_display_init(board_display_t *out);
bool board_display_init_at(int index, board_display_t *out);
bool board_display_orientation(board_display_t *display, int dir_x, int dir_y, bool swap_xy);
```

Дисплеев на плате может быть несколько. `board_display_init` запускает основной,
`board_display_init_at` принимает его номер, 0 — основной. Повторный вызов отдаёт тот
же дисплей. У дисплеев, которые данные объединяют в один экран (`display_groups`), есть
свой номер: запуск по нему поднимает оба и отдаёт один широкий экран. Такой экран не
поворачивается: `board_display_orientation` возвращает `false`, а у каждого из двух
остаётся своя ориентация. `board_touch_start` принимает дисплей под тачем,
и возвращает `false` для другого.

`board_display_init` поднимает панель с включённой подсветкой, ориентированную
так, как показывает плата (`original_orientation` из данных), и заполняет
`*out`. Дескрипторы DGX лежат в `boards_dgx.h`:

```c
dgx_screen_t        *board_dgx_screen(const board_display_t *display);
dgx_bus_protocols_t *board_dgx_bus(const board_display_t *display);
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

Миллиметры — это измеренный размер картинки в том виде, как она показана: жесты DGX-DI и шрифты
DGX используют их, чтобы сантиметр был сантиметром на каждой плате.

## Символьный дисплей

```c
typedef struct board_character_display { int cols, rows; } board_character_display_t;
bool board_character_display_init(board_character_display_t *out);
```

HD44780, который есть у платы, или который приносит модуль на её шине I2C.
Дисплей настроен, очищен, его подсветка включена. `board_hd44780(&lcd)` из
`boards_hd44780.h` даёт `hd44780_t *` для `lcd_set_cursor`, `lcd_write_str` и
остального из `hd44780.h`. hd44780 компонуется только когда он есть в сборке
(`CONFIG_BOARD_DISPLAY_HD44780`), поэтому в программе, работающей на платах без него,
подключайте заголовок под этим символом.

## Тач-панель

```c
typedef struct board_touch { int fingers; int x_max, y_max; const char *name; int index; } board_touch_t;
int  board_touch_count(void);
bool board_touch_start(const board_display_t *display, board_touch_t *out);
bool board_touch_start_at(int index, const board_display_t *display, board_touch_t *out);
```

Настраивает панель под дисплеем, полученным раньше, с измеренной калибровкой платы.
`board_touch_start` берёт первую панель над этим дисплеем, `board_touch_start_at` — панель по
её месту. Повторный вызов даёт ту же панель. `out` может быть `NULL`. Устройство и указатель на
нём даёт `boards_dgx_di.h`:

```c
dgx_di_device_t  *board_dgx_di_device(const board_touch_t *touch);
dgx_di_pointer_t *board_dgx_di_pointer(const board_touch_t *touch);
```

Указатель следует за ориентацией дисплея: после `board_display_orientation` его
координаты — координаты дисплея в его нынешней ориентации. Задача, которая его
читает, — дело программы:

```c
#include "boards_dgx_di.h"
board_touch_t touch;
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
void board_touch_firmware_set(const uint8_t *start, size_t size);
```

Прошивка панели, которая не хранит своей (GSL3680 10,1-дюймовой Guition):
программа, встраивающая её, передаёт байты здесь, до `board_touch_start`. Без этого
тач такой платы выключен. См. [touch-firmware.md](touch-firmware.md).

## Звук

```c
typedef struct board_sound { uint32_t rate; const char *name; int index; } board_sound_t;
typedef void (*board_sound_source_t)(int16_t *samples, size_t count);
int  board_sound_count(void);
bool board_sound_init(board_sound_t *out);
bool board_sound_init_at(int index, board_sound_t *out);
bool board_sound_start(board_sound_source_t source, uint32_t *rate_out);
bool board_sound_start_at(int index, board_sound_source_t source, uint32_t *rate_out);
void board_sound_source(board_sound_source_t source);
void board_sound_source_at(int index, board_sound_source_t source);
```

Функции без `_at` относятся к первому выходу.

`board_sound_init` настраивает кодек, усилитель или ЦАП и возвращает частоту, а
заголовок адаптера даёт дескриптор библиотеки: `board_esp_codec_dev()` в
`boards_esp_codec_dev.h` (ES8311: запись через `esp_codec_dev_write`, громкость
через `esp_codec_dev_set_out_vol`), `board_i2s_channel()` в
`boards_esp_driver_i2s.h` (усилитель на I2S), `board_dac_continuous()` в
`boards_esp_driver_dac.h` (ЦАП ESP32, 8 бит на сэмпл). Программа со своим
микшером пишет туда сама и `board_sound_start` не вызывает.

`board_sound_start` делает ту же настройку и запускает задачу, которая
просит у `source` следующие `count` сэмплов, 16-битных моно с частотой
`*rate_out`, и отправляет их; записи блокируются на железе, которое и задаёт
темп. `source` может быть `NULL` для тишины и быть задан позже через
`board_sound_source`. Задача работает, пока не остановится прошивка. Повторный
вызов любой из двух функций возвращает тот же звук, из любой задачи. Микшер и
формат, отличный от 16-битного моно, — дело программы: здесь железо и его темп,
ничего больше.

## Шины

```c
typedef struct board_spi_bus { int host, mosi, miso, sclk; unsigned long hz; } board_spi_bus_t;
const board_spi_bus_t *board_spi_bus(int host);
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
устройства, которое компонент не настраивает, по его имени в данных, и шину, на
которой оно стоит: `"host"` (хост SPI, например `SPI3_HOST`, для `board_spi_bus`),
`"port"` (I2C или UART) и `"address"` (7 бит, на I2C, если он есть в данных). Так
программа берёт считыватель без единого пина платы в своём коде:

```c
long host, cs;
const board_spi_bus_t *bus;
if (board_bus_get("nfc_in_nfc", "host", &host) && board_bus_get("nfc_in_nfc", "cs", &cs) && (bus = board_spi_bus((int)host)))
    reader = pn532_spi_init(bus->host, bus->sclk, bus->miso, bus->mosi, cs, 0);
```

`board_bus_get("sdio.sdio0", "clk", &pin)`
читает любое число любой шины, которую называют данные, включая роды, которые
компонент не настраивает.

```c
struct i2c_master_bus_t *board_i2c(int port);   /* i2c_master_bus_handle_t ESP-IDF */
bool board_i2c_taken(int port);
```

`board_i2c(0)` возвращает мастер I2C платы на порту 0. Первый вызов из любой задачи
создаёт его, следующие возвращают тот же мастер, которым пользуются и части платы на
этой шине, например тач или кодек.
Устройство, которое добавляет программа, садится на него через
`i2c_master_bus_add_device`; второй геймпад с тем же адресом — на другой порт.
ESP-IDF допускает один мастер на порт, поэтому программа создаёт свой мастер
только на порту, который `board_i2c_taken` называет свободным. NULL, если на
этом порту у платы нет шины или мастер не создаётся.

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
#if CONFIG_BOARD_SOUND_ES8311
#include "boards_esp_codec_dev.h"
#endif
```

Программа, у которой дисплей есть всегда, может подключать эти заголовки
безусловно и назвать `jef-sure/dgx` также и в собственном манифесте.
