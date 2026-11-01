# Добавление платы

Плата — это каталог в `catalog/boards/` с двумя файлами. Всё остальное
генерируется.

## 1. Опишите её

Скопируйте ближайшую плату:

```sh
cp -r catalog/boards/jc1060p470c catalog/boards/myboard
```

Отредактируйте `catalog/boards/myboard/board.json`: `name` должно совпадать с
именем каталога; затем чип, шины так, как плата их разводит, устройства на
них. Формат — в [data-format.md](data-format.md). Откуда берутся данные, в порядке
доверия: схема платы, примеры производителя, ухоженный список пинов от
сообщества и измерение самой платы.

Напишите `catalog/boards/myboard/sdkconfig.defaults` вручную. Его первые две
строки выбирают чип и плату; остальное — что нужно чипу, его памяти и флешу,
с причиной для каждой строки в комментарии. Причины важны: их прочитает
следующий человек, а в ревизии чипа или скорости PSRAM легко ошибиться
незаметно.

```
CONFIG_IDF_TARGET="esp32s3"
CONFIG_BOARD_SELECT_MYBOARD=y
CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y
# 8 MB octal PSRAM: the frame buffer lives in it
CONFIG_SPIRAM=y
CONFIG_SPIRAM_MODE_OCT=y
CONFIG_SPIRAM_SPEED_80M=y
```

## 2. Сгенерируйте и проверьте

```sh
python3 tools/boards_gen.py --all
python3 tools/check_boards.py --host-syntax
python3 tools/board_pins.py myboard
```

Генератор записывает клей, `boards/boards.cmake`, `Kconfig`, зависимости
манифеста и таблицы README. Проверка сравнивает их с данными, проверяет
умолчания, покрытие API и карту пинов и компилирует клей против `test/fake/`.
Карта пинов показывает каждый GPIO и его владельца, с отмеченными конфликтами.

Новый чип библиотеки, которую компонент уже запускает, — это запись в её файле в
`catalog/libraries/`. Новая библиотека — это файл там же и, если компонент должен её
запускать, каталог в `adapters/` и поле `adapter`; новому роду части может понадобиться ещё
генератор и заголовки-заглушки в `test/fake/`;
новая плата известного рода — это только данные.

## 3. Соберите её

```sh
python3 tools/board_select.py myboard examples/hello_board
cd examples/hello_board && idf.py build flash monitor
```

Пример печатает, что он нашёл, и рисует кадр. Добавьте плату в матрицу в
`.github/workflows/build.yml`, чтобы CI с этого момента её собирал.

## 4. Измерьте тач

Тач работает и без калибровки, измеренной на плате, но неточно. Измерьте её с
помощью `dgx_di_calibrate_measure` из DGX-DI (его пример `touch_check` делает
это на дисплее платы), затем отдайте лог `tools/board_calibration.py`. До тех пор
оставьте в калибровке
`"measured": false`: клей предупреждает при старте, и таблица README об этом
говорит. См. [calibration.md](calibration.md).

## 5. Закоммитьте

Коммитьте данные, умолчания и сгенерированные файлы вместе: программа, берущая
компонент из реестра компонентов, собирается без запуска генератора.
`check_boards.py` в CI отвергает коммит, где они расходятся.

## Собственная плата вне компонента

В каталоге лежат платы и модули, которые может купить каждый. То, что вы соединили и назвали сами,
остаётся в вашей программе: `components/local-boards/`, дерево того же вида, что `catalog/`.

```
components/local-boards/
    boards/my_board/board.json       kind project поверх платы каталога или kind board
    modules/my_display/module.json   модуль, которого нет в каталоге
    devices/my_chip/device.json      чип, которого нет в каталоге
```

Инструменты читают это дерево раньше каталога. Имя платы программы не должно совпадать с именем
платы каталога.

```sh
python3 путь/к/boards/tools/board_select.py my_board .
idf.py build
```

`board_select.py` создаёт клей рядом с данными, записывает `CMakeLists.txt` и `Kconfig.projbuild`
этой папки, и плата появляется в меню плат. Если у платы нет своего `sdkconfig.defaults`, берётся
файл платы, которую она расширяет. Пины проверяются так же, как у плат каталога:
`tools/board_pins.py my_board --project .`. `examples/local_boards` — такая программа.
