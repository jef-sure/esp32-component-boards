# Инструменты

Все в `tools/`, Python 3.8 или новее, никаких пакетов сверх стандартной
библиотеки. Запускайте их из корня репозитория (или из
`managed_components/jef-sure__boards/`).

## boards_gen.py

```sh
python3 tools/boards_gen.py --all          # everything, from every board and module
python3 tools/boards_gen.py cyd            # one board's glue and board.cmake only
```

Читает `boards-data/*/board.json`, отказывается от того, для чего не может
сделать клей (см. [data-format.md](data-format.md)), и записывает:

- `boards/<board>/<board>.c` и `board.cmake` для каждой платы и модуля;
- `boards/boards.cmake`: списки, по которым компилирует `CMakeLists.txt` компонента;
- `Kconfig`: choice, опции модулей, скрытые символы;
- `dependencies:` в `idf_component.yml`, между `# boards: dependencies
  generated` и `# boards: end of generated`;
- таблицу плат в `README.md` и `README.ru.md`, между
  `<!-- boards:table -->` и `<!-- boards:end -->`.

Он записывает файл только когда его содержимое меняется. Таблицы в его начале
— это знание, которое у него есть сверх данных: какой заголовок DGX и какие
символы `DGX_ENABLE_*` принимает драйвер панели, какие глубины пикселя, какие
роды тача, какой компонент реестра и какую версию приносит каждая возможность.

## check_boards.py

```sh
python3 tools/check_boards.py                 # the data and the generated agree
python3 tools/check_boards.py --host-syntax   # and every glue and the core compile against test/fake
python3 tools/check_boards.py --fix           # write what differs instead of complaining
```

Код возврата 1 и по строке на каждую находку в stderr, когда: `board.json` не
читается; сгенерированный файл расходится с тем, что говорят данные, или
отсутствует; `sdkconfig.defaults` платы отсутствует или не выбирает её чип и
её саму; `sdkconfig.defaults` модуля не включает его; клей не определяет
каждую функцию `boards.h`; два владельца делят один GPIO или выход управляет
GPIO только для ввода; у компонента, который называют данные, нет правила
манифеста; правило называет символ, которого нет в Kconfig. CI запускает его
первым.

`--host-syntax` компилирует каждый клей и исходники ядра в `src/` хостовым `gcc -std=gnu11
-fsyntax-only -Wall -Wextra -Werror` против `test/fake/` — заголовков-заглушек,
повторяющих форму настоящих объявлений ESP-IDF, DGX, DGX-DI и hd44780. Когда
настоящий заголовок меняет форму, генератор и заглушки меняются вместе.
Секунды, без ESP-IDF; настоящей проверкой остаётся сборка в CI.

## board_pins.py

```sh
python3 tools/board_pins.py cyd           # GPIO -> owner, conflicts marked
python3 tools/board_pins.py cyd --tree    # chip -> buses -> devices -> pins
python3 tools/board_pins.py --all         # every board's conflicts, for CI
```

Карта, по которой делаются проверки, — чтобы на неё смотрел человек: каждый
GPIO, который называют данные, кто им владеет и в каком направлении, с
пометками *TWO OWNERS*, *INPUT ONLY, DRIVEN* и *NOT A GPIO OF THIS CHIP* рядом
с нарушителями.

## board_select.py

```sh
python3 tools/board_select.py cyd ~/myproject
python3 tools/board_select.py jc1060p470 --module lcd2004_pcf8574 --reset ~/myproject
```

Записывает `~/myproject/sdkconfig.defaults.board`: умолчания платы, затем
каждого модуля. С `--reset` переносит существующий `sdkconfig` в
`sdkconfig.old`, чтобы новые умолчания были прочитаны. См.
[choosing-a-board.md](choosing-a-board.md).

## Редактор

`editor/index.html`, Vue 3 и Pinia с CDN, Bootstrap для внешнего вида, без
шага сборки: откройте его в браузере. *Open a board.json* загружает файл;
форма редактирует его, проверяя правила генератора на лету (проблемы
перечислены сверху, *Save* недоступна, пока хоть одна остаётся); *Save
board.json* скачивает результат. Поле калибровки принимает C-инициализатор,
который печатает `dgx_di_calibrate_measure`, и превращает его в поля данных.
Числа с плавающей точкой в файле сохраняют своё написание (`5.0` остаётся
`5.0`).

## test/fake

Заголовки-заглушки для `--host-syntax`. Не входят в пакет реестра. Новому
include в сгенерированном клее нужна заглушка здесь с тем же именем и формой
того, что клей вызывает.

## Workflow CI

`.github/workflows/build.yml`: `check_boards.py --host-syntax` и
`board_pins.py --all`, затем `examples/hello_board`, собранный для каждой платы
под двумя версиями ESP-IDF, плюс одна сборка с модулем 2004, каждая в своём
job. Добавляйте плату в матрицу, когда добавляете её в данные.
