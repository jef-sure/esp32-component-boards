# Выбор платы для проекта

Плата называется один раз, в одной командной строке. Всё остальное следует из
этого.

## Новый проект

```sh
idf.py create-project hello && cd hello
idf.py add-dependency "jef-sure/boards>=0.1.0"
```

`>=0.1.0`, а не `^0.1.0`: менеджер компонентов читает «крышку» на версии 0.x как версии до следующей 0.x, `^0.1.0` —
только 0.1.x, и 0.2.0 не взялась бы. То, что взяла сборка, остаётся в lock каждой платы. Коммит, который ещё не
опубликован, берётся из git на этом коммите, чтобы завтра сборка дала то же самое:

```yaml
# main/idf_component.yml
dependencies:
  jef-sure/boards:
    git: https://github.com/jef-sure/esp32-component-boards.git
    version: <коммит>
```

В `CMakeLists.txt`, до подключения `project.cmake`, прочитайте умолчания платы,
которую называет пресет, перед собственными умолчаниями проекта и дайте каждой
плате свой lock компонентов рядом с проектом:

```cmake
cmake_minimum_required(VERSION 3.22)
# BOARD=<board>, which the preset of a board sets, builds with sdkconfig.defaults.<board> that board_select.py writes,
# then with the program's own sdkconfig.defaults when it has one. A -D SDKCONFIG_DEFAULTS=... on the command line wins.
set(BOARD "" CACHE STRING "a board of this project: its file sdkconfig.defaults.<board>")
if(NOT SDKCONFIG_DEFAULTS AND BOARD)
    if(NOT EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.${BOARD})
        message(FATAL_ERROR "no sdkconfig.defaults.${BOARD} here: run board_select.py ${BOARD} . of jef-sure/boards")
    endif()
    # the file of the board names its target; set-target asks another into the build directory of this board
    file(STRINGS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.${BOARD} _boards_target REGEX "^CONFIG_IDF_TARGET=")
    string(REGEX REPLACE "^CONFIG_IDF_TARGET=\"(.*)\"$" "\\1" _boards_target "${_boards_target}")
    if(IDF_TARGET AND _boards_target AND NOT IDF_TARGET STREQUAL _boards_target)
        message(FATAL_ERROR "${BOARD} is built for ${_boards_target}, and this configuration is for ${IDF_TARGET}: a board builds by "
                            "its own preset, idf.py --preset <board> build, or in VS Code ESP-IDF: Select Project Configuration. "
                            "set-target, or -D BOARD with the preset of another board, chooses no board.")
    endif()
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.${BOARD}")
    if(EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults)
        list(APPEND SDKCONFIG_DEFAULTS "sdkconfig.defaults")
    endif()
elseif(NOT BOARD AND NOT SDKCONFIG)
    # no board: its sdkconfig stays in build/, as idf.py checks the target of <project>/sdkconfig while a board has no build
    set(SDKCONFIG ${CMAKE_BINARY_DIR}/sdkconfig)
endif()
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
if(BOARD)
    idf_build_set_property(DEPENDENCIES_LOCK ${CMAKE_CURRENT_LIST_DIR}/dependencies.lock.${BOARD})
endif()
project(hello)
```

`main/CMakeLists.txt` ничего не называет для компонента: менеджер компонентов делает
то, что названо в `main/idf_component.yml`, зависимостью `main` — `jef-sure__boards` по
каталогу под `managed_components/`. (Checkout компонента, взятый через `override_path`
или `EXTRA_COMPONENT_DIRS`, называется по имени своего каталога, а менеджер
компонентов сопоставляет зависимость с локальным компонентом, только если тот
каталог называется `boards` или `jef-sure__boards`. Поэтому пример внутри
этого репозитория берёт компонент через `EXTRA_COMPONENT_DIRS`, ничего не
называет в `main` и даёт `main` зависеть от всех компонентов сборки, как
делает `main` в ESP-IDF, когда не называет ничего.) Затем выберите плату и
соберите:

```sh
idf.py reconfigure            # один раз: скачивает компонент в managed_components/
python3 managed_components/jef-sure__boards/tools/board_select.py cyd_s028r .
idf.py build flash monitor
```

`board_select.py` записывает `sdkconfig.defaults.cyd_s028r`: команду, которая его
сделала, затем `sdkconfig.defaults` платы из данных компонента. Его первые настройки —
`CONFIG_IDF_TARGET="esp32"` и `CONFIG_BOARD_SELECT_CYD_S028R=y`; остальное — что нужно
чипу, памяти и флешу. ESP-IDF берёт target из первого файла в `SDKCONFIG_DEFAULTS`,
который его называет, поэтому `idf.py set-target` не нужен, а меню *Boards → Board the
program runs on* показывает выбранную плату. Ещё он пишет `CMakePresets.json`: пресет
`cyd_s028r`, который задаёт `BOARD` и собирает в `build/cyd_s028r` со своим `sdkconfig` в папке проекта,
`sdkconfig.cyd_s028r`, и пресет `default` — его копию, которую `idf.py` берёт, когда пресет не назван.
Первый `reconfigure`, без платы, собирает в `build/` и держит свой `sdkconfig` там же; платы его не читают. В папке
проекта `sdkconfig` с целью esp32 остановил бы первую сборку компьютера в терминале с `IDF_TARGET=linux`: пока у платы
нет своей сборки, `idf.py` сверяет цель с этим файлом.

ESP-IDF 5 пресетов не читает; плата называется в командной строке:

```sh
idf.py -B build/cyd_s028r -D SDKCONFIG=sdkconfig.cyd_s028r -D BOARD=cyd_s028r build
```

Закоммитьте `sdkconfig.defaults.<плата>`, `CMakePresets.json` и
`dependencies.lock.<плата>`: свежий клон читает их раньше, чем скачан компонент.

## Модуль

Модуль, подключённый к плате, даёт плату программы: `components/local-boards/boards/<плата>/board.json`
называет плату, на которой она стоит, и её модули с их шинами и пинами. Страница пишет её для комплекта с
модулями; в `examples/local_boards` она написана руками. `board_select.py <плата> .` берёт её как плату
каталога и делает её клей рядом с её данными. Плата программы, которую потом изменили так, что ей нужна другая
библиотека, получает её, когда удалены её `dependencies.lock.<плата>` и `build/<плата>`: менеджер компонентов
решает lock заново, когда меняется манифест, а не плата. См. [modules.md](modules.md).

## Другая плата

Названная другая плата добавляется к платам проекта и становится текущей:

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py jc4827w543c .
idf.py build flash monitor            # jc4827w543c, в build/jc4827w543c
idf.py --preset cyd_s028r build       # прежняя плата никуда не делась
```

Каждая плата собирается в своём каталоге, со своей целью и своим `sdkconfig`, поэтому
плате с другим чипом не нужен `set-target` и ничего не чистится. В одном каталоге
сборки плата не меняется: чип каталога сборки закреплён в кеше CMake раньше, чем
читается `CMakeLists.txt`, поэтому строка в нём другой чип выбрать не может. Плата
убирается удалением её `sdkconfig.defaults.<плата>`, затем `board_select.py --again .`
пишет пресеты остальных; её `build/<плата>` и `dependencies.lock.<плата>` больше не
читаются.

## Несколько плат

Несколько плат можно назвать и сразу:

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py cyd_s028r jc1060p470c .
idf.py build                          # ESP-IDF 6: первая плата, cyd_s028r
idf.py --preset jc1060p470c build     # другая
```

`board_select.py` пишет `sdkconfig.defaults.<плата>` на каждую плату, со строками
ревизии её чипа, и пресеты всех плат проекта: сначала те, что были, затем названные, в
том порядке, в каком названы. У каждой платы свой lock компонентов,
`dependencies.lock.<плата>` рядом с проектом, поэтому платы друг другу не мешают;
версии компонентов остаются такими, какими их выбрали. В первый раз `board_select.py`
копирует `dependencies.lock` проекта каждой плате, так что проект, сделанный раньше,
сохраняет свои версии; дальше каждая плата читает свой, а `dependencies.lock` больше не
читается. Один lock на две платы держал бы решение первой: менеджер компонентов решает
заново, когда меняется манифест, а не плата. Файлы каталога напрямую не читаются:
строки ревизии есть только в том, что пишет `board_select.py`.

`default` — текущая плата, первая названная, если `--current <плата>` не назвал другую:
`idf.py build`, `flash` и `monitor` берут её без лишних слов. Другую на одну команду
берёт `idf.py --preset <плата>` или `IDF_PRESET=<плата>` в окружении;
`board_select.py --current <плата> .` делает текущей другую и меняет только `default`,
так что платы остаются в своём порядке, и `current` в `selection.json`, если он в проекте есть. Расширение ESP-IDF для VS Code показывает
пресеты как конфигурации проекта: *ESP-IDF: Select Project Configuration* выбирает
одну, строка состояния её называет.

Страница делает то же из своих комплектов: *add to the project* на карточке добавляет комплект в платы проекта,
переключатель рядом с каждой делает одну текущей, а *make the project of these boards…* их записывает. Она пишет
`selection.json`, где `boards` держат порядок добавления, `current` — текущую плату, а `name` — имя проекта, плату программы
`<проект>_<плата>` для комплекта со своим проектом и `sdkconfig.defaults.<плата>` каждой с командой, которая его
делает, в первой строке: `board_select.py --again .` делает остальное — умолчания, пресеты и клей. Открытая из
`tools/boards_mcp.py`, страница пишет через него, а сервер сам запускает `--again`, и проект сразу собирается; она же
начинает с `selection.json` проекта, чтобы добавить плату. Плата пресетов, для которой у страницы нет комплекта, —
названная командой или та, чей комплект не подходит под нынешние ответы, — стоит среди плат проекта со своим
переключателем и остаётся в проекте. Если такая плата — компьютер, `host_<плата>`, а страница пишет плату программы
`<проект>_<плата>`, она пишет и компьютер `host_<проект>_<плата>`, который показывает плату программы, с тем же набором
частей; был текущим прежний компьютер — текущим становится новый.

`CMakePresets.json`, который `board_select.py` не писал, не трогается: команда об этом
говорит, и пресеты добавляются руками. `board_select.py --again .` делает каждый файл
заново по команде в его первой строке, и пресеты — в их порядке и с их текущей платой, а в
первый раз — как в `selection.json`. Пресеты помнят текущую плату, с которой сделаны, а каждая
команда, которая её меняет, пишет её и в `current` файла `selection.json`, поэтому текущая плата,
которую страница с тех пор поменяла, берётся, а выбранная командой остаётся. Страница открывает проект с порядком и текущей платой его пресетов. ESP-IDF
читает умолчания только в новый `sdkconfig`: чтобы взять изменённое, удалите
`sdkconfig.<плата>`. `sdkconfig` платы лежит в папке проекта, а не в `build/`, поэтому `build/` удаляют, как в любом
проекте ESP-IDF; версия до 0.1.1 держала его в `build/<плата>/`, и `board_select.py --again .` переносит его.
Сборка, конфигурация которой не выбрала плату из `BOARD`, останавливается на конфигурации
и говорит, какую плату она выбрала и для какого чипа: на ESP-IDF 6 форма `-B ... -D BOARD=<плата>` берёт чип пресета
`default`, а `sdkconfig` другой платы в каталоге сборки оставляет свою плату.
Сборка без `BOARD` в проекте, где `board_select.py` уже сделал файлы плат, тоже останавливается и называет его платы:
так собирает `cmake` без пресета, например расширение ESP-IDF для VS Code, пока в нём не выбрана конфигурация проекта.
`idf.py` ESP-IDF 6 без `--preset` берёт пресет `default`, то есть текущую плату.

`-D SDKCONFIG_DEFAULTS=...` в командной строке побеждает оба варианта: фрагмент
CMake выше задаёт переменную только когда она не задана.

## Компьютер

Программа работает на компьютере так же, как на плате: плата `host_<плата>`, цель `linux` ESP-IDF, окно DGX с дисплеем
платы, которую она показывает.

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py host --as jc8012p4a1c .
idf.py -B build/host_jc8012p4a1c -D SDKCONFIG=sdkconfig.host_jc8012p4a1c -D BOARD=host_jc8012p4a1c build
build/host_jc8012p4a1c/<project>.elf
```

Каждое `--as` — свой компьютер со своим именем, файлом, пресетом и каталогом сборки: `host --as cyd_s028r --as jc1060p470c`
даёт `host_cyd_s028r` и `host_jc1060p470c`, и они собираются и запускаются рядом. На ESP-IDF 6 —
`idf.py --preset host_jc8012p4a1c build`.

В терминале лог идёт сразу; через трубу он буферизуется, и `stdbuf -o0 build/host_jc8012p4a1c/<project>.elf` выдаёт его без
задержки.

В 0.0.7 компьютер был один и назывался `host`. В проекте того времени строка `if(BOARD STREQUAL "host")` в
`CMakeLists.txt` меняется на `if(BOARD MATCHES "^host_")` — `board_select.py` говорит об этом и до правки ничего не
пишет, — а `board_select.py --again .` переименовывает `sdkconfig.defaults.host` и `dependencies.lock.host` в
`…host_<плата>`; `build/host` можно удалить. Удаляется и `sdkconfig` в папке проекта, который оставил первый
`reconfigure`, а в CMake приходят строки выше, которые держат его в `build/`.

`board_select.py` пишет `sdkconfig.defaults.host_<плата>` рядом с файлами плат проекта, а CMake заготовки собирает для компьютера
только `main` и то, что он требует. `BOARD_PIXELS` и `BOARD_MM` берутся у показываемой платы. Окно — экран DGX для компьютера
(`dgx_host_screen_init`, DGX 0.10.10 и новее): стекло дисплея платы, повёрнутое так, как плату держат, с экраном в той
ориентации, с которой плата стартует. Поэтому `board_display_init` даёт те же ширину, высоту и ориентацию, что на плате, а
`board_dgx_screen()` рисует на нём так же, как на панели. В заголовке окна видно, сколько отправленные байты шли бы по
шине этой платы, если это SPI или QSPI, и сколько памяти держат программа и DGX. Дисплей, который стартует зеркально, и
группа из двух показываются так, как их видно, без поворота.
Окно показывает та задача, которая запустила дисплей, в своих ожиданиях (`vTaskDelay`), поэтому дисплей запускают из
`app_main` или из задачи, у которой свободно не меньше 48 КБ стека; `sdkconfig.defaults.host_<плата>` даёт `app_main` 128 КБ
(`CONFIG_ESP_MAIN_TASK_STACK_SIZE=16384`, в словах по 8 байт). Когда `app_main` вернётся, окно остаётся, пока его не
закроют; закрытое окно завершает программу. Если у показываемой платы есть тач, это мышь (`CONFIG_BOARD_HOST_TOUCH`;
только тогда приходит DGX-DI): нажатая на окне, она становится пальцем на стекле
(`dgx_di_host.h`, DGX-DI 0.1.5 и новее). Программа читает её через `board_dgx_di_pointer()`, как на плате, без
калибровки, и палец поворачивается вместе с дисплеем. Звук идёт в динамики компьютера: источник, как на плате, зовёт
задача. Флеш программы с разделами (NVS, файловая система) сохраняется между запусками в `build/host_<плата>/flash.bin`, пока
таблица разделов сборки та же; удалённый файл — стёртая флеш. Кнопки — это клавиши: кнопки показываемой платы, `boot`
на B, и кнопки геймпада, среди них WASD и стрелки (см. кнопки в [api.md](api.md)); `DGX_HOST_SCRIPT` из DGX нажимает их
и мышь, когда за компьютером никого нет. Нужны SDL2 и libbsd (`libsdl2-dev`, `libbsd-dev`); работает на Linux, Windows целью ESP-IDF не является.

## Что приходит вместе с выбором

- Драйверы DGX панели платы: `select`-ы в choice в Kconfig компонента
  (`CONFIG_DGX_ENABLE_DSI`, `CONFIG_DGX_ENABLE_JD9165`, ...).
- Остальные части: правила в `idf_component.yml` компонента на скрытых
  символах рядом с choice. Сборка для CYD S028R получает `atanisoft/esp_lcd_touch_xpt2046`
  и ничего от GT911 или ES8311; сборка с выбранным *None* не получает ничего
  из DGX и собирается: каждая функция `boards.h` возвращает `false`.
- Клей выбранной платы, компилируемый в компонент по
  `CONFIG_BOARD_<BOARD>`; его `board.cmake` называет компоненты, которые ему
  нужны.
- Размер основного дисплея для CMake программы, в том виде, как он показан:
  `BOARD_PIXELS` (ширина и высота) и `BOARD_MM` (в миллиметрах, `0 0`, если в данных
  размера нет). Их задаёт `project_include.cmake` компонента. В `main/CMakeLists.txt`
  они есть и до `idf_component_register`, и после; при раннем раскрытии зависимостей
  они пусты, как и у платы без пиксельного дисплея. Игра один раз отдаёт их DGX:
  `dgx_fonts_board(PIXELS ${BOARD_PIXELS} MM ${BOARD_MM})`.

Менеджер компонентов вычисляет свои правила по `sdkconfig`. Когда у проекта
его ещё нет, первый `idf.py build` генерирует его из умолчаний, видит, что
набор зависимостей изменился (*Direct dependencies have changed, solving
dependencies* в логе), и сам разрешает их заново в том же запуске. Одного
`idf.py build` достаточно; лог показывает, какие необязательные зависимости
были пропущены.

## Что остаётся программе

Плата приносит то, что нужно её железу: драйверы своей панели и, для двух дисплеев, показанных как один,
`CONFIG_DGX_ENABLE_VSCREEN` и `CONFIG_DGX_ENABLE_VSCREEN_2H`. То, чем программа пользуется сама, остаётся в её
собственном `sdkconfig.defaults`, который читается после файла платы, и одинаково на любой плате: тик FreeRTOS,
оптимизация, возможность библиотеки, которую она зовёт. Игра dgx-ge рисует в экран в памяти и шагает циклом по
миллисекундам, поэтому её умолчания говорят

```
CONFIG_FREERTOS_HZ=1000
CONFIG_COMPILER_OPTIMIZATION_PERF=y
CONFIG_DGX_ENABLE_VSCREEN=y
```

там, где каталоги плат dgx-ge повторяли `CONFIG_DGX_ENABLE_VSCREEN` для каждой платы. Строка файла программы, которую
задаёт и файл платы, побеждает как более поздняя.

## Без board_select.py

Файл, который он записывает, — `catalog/boards/<board>/sdkconfig.defaults` со строками
ревизии чипа платы и строками каждого модуля. Любой другой способ попасть этим строкам в
`SDKCONFIG_DEFAULTS` работает: путь внутрь `managed_components/` или в чекаут
компонента рядом с проектом, или копирование строк в собственный `sdkconfig.defaults`
проекта. И меню работает как меню: `idf.py menuconfig`, *Boards*, выбрать; но тогда
настройки чипа (режим PSRAM, размер флеша, ревизия чипа) тоже придётся задавать вам
самим — именно от этого и избавляет файл умолчаний.

## Ревизии чипа

Платы на ESP32-P4 приходят с чипами ревизии 1.x или 3.x, и сборка для одной не
запускается на другой. Ревизии различаются возможностями: 360 или 400 МГц у CPU,
200 или 250 МГц у PSRAM, а от этой PSRAM зависит панель MIPI-DSI. `mcu.revision`
платы называет ревизию, на которой её измеряли, а `tools/board_select.py` пишет
строки этой ревизии из `catalog/mcu/`. Для платы с другим чипом есть `--revision`.
Проверьте свой чип (`esptool.py chip_id` или лог загрузки) перед первой прошивкой:

```sh
python3 tools/board_select.py jc1060p470c --revision 3.1 .
```
