# Выбор платы для проекта

Плата называется один раз, в одной командной строке. Всё остальное следует из
этого.

## Новый проект

```sh
idf.py create-project hello && cd hello
```

Компонента пока нет в реестре: берите его из git на определённом коммите, чтобы
завтра сборка дала то же самое. После публикации его место займёт `idf.py
add-dependency "jef-sure/boards^0.0.1"`.

```yaml
# main/idf_component.yml
dependencies:
  jef-sure/boards:
    git: https://github.com/jef-sure/esp32-component-boards.git
    version: <коммит>
```

В `CMakeLists.txt`, до подключения `project.cmake`, прочитайте умолчания платы
перед собственными умолчаниями проекта и держите lock компонентов в каталоге
сборки:

```cmake
cmake_minimum_required(VERSION 3.22)
set(BOARD "" CACHE STRING "a board of this project: its file sdkconfig.defaults.<board>")
if(NOT SDKCONFIG_DEFAULTS)
    if(BOARD)
        if(NOT EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.${BOARD})
            message(FATAL_ERROR "no sdkconfig.defaults.${BOARD} here: run board_select.py ${BOARD} ... . of jef-sure/boards")
        endif()
        set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.${BOARD};sdkconfig.defaults")
    elseif(EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.board)
        set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.board;sdkconfig.defaults")
    endif()
endif()
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
idf_build_set_property(DEPENDENCIES_LOCK ${CMAKE_BINARY_DIR}/dependencies.lock)
project(hello)
```

`BOARD` выбирает одну из нескольких плат (см. ниже); без него читается один файл
`sdkconfig.defaults.board`.

В `main/CMakeLists.txt` — `PRIV_REQUIRES jef-sure__boards`: каталог компонента
под `managed_components/`. (Checkout компонента, взятый через `override_path`
или `EXTRA_COMPONENT_DIRS`, называется по имени своего каталога, а менеджер
компонентов сопоставляет зависимость с локальным компонентом, только если тот
каталог называется `boards` или `jef-sure__boards`. Поэтому пример внутри
этого репозитория берёт компонент через `EXTRA_COMPONENT_DIRS`, ничего не
называет в `main` и даёт `main` зависеть от всех компонентов сборки, как
делает `main` в ESP-IDF, когда не называет ничего.) Затем выберите плату и
соберите:

```sh
idf.py reconfigure            # once: downloads the component into managed_components/
python3 managed_components/jef-sure__boards/tools/board_select.py cyd_s028r .
idf.py build flash monitor
```

`board_select.py` записывает `sdkconfig.defaults.board`: `sdkconfig.defaults`
платы из данных компонента. Его первые строки — `CONFIG_IDF_TARGET="esp32"` и
`CONFIG_BOARD_SELECT_CYD_S028R=y`; остальное — что нужно чипу, памяти и флешу.
ESP-IDF берёт target из первого файла в `SDKCONFIG_DEFAULTS`, который его
называет, поэтому `idf.py set-target` не нужен, а меню *Boards → Board the
program runs on* показывает выбранную плату.

Закоммитьте `sdkconfig.defaults.board`, если проект для одной платы; проект для
нескольких держит вместо него `sdkconfig.defaults.<плата>` (см. ниже).

## Модуль

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py jc1060p470c --module lcd2004_pcf8574 .
```

Умолчания модуля дописываются после умолчаний платы: они включают его опцию в
меню (`CONFIG_BOARD_MODULE_LCD2004_PCF8574=y`), что подтягивает hd44780 и
компилирует клей модуля рядом с клеем платы. См. [modules.md](modules.md).

## Смена платы

ESP-IDF читает `sdkconfig.defaults*` только когда создаёт новый `sdkconfig`.
Чтобы перевести проект на другую плату:

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py jc4827w543c --reset .
```

`--reset` переносит старый `sdkconfig` в `sdkconfig.old` и называет следующую
команду. Каталог сборки хранит цель своего чипа в кеше CMake, а кеш читается
раньше любых умолчаний: если у новой платы другой чип, команда — `idf.py
set-target <цель>`, она чистит сборку и делает новый `sdkconfig` из умолчаний,
затем `idf.py build`; с тем же чипом — `idf.py reconfigure build`. Без `--reset`
`board_select.py` ничего не пишет и выходит с ошибкой, если `sdkconfig` сделан для
другой платы: сборка дала бы ту плату.

## Несколько плат

Проект для нескольких плат держит на каждую файл умолчаний и каталог сборки:

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py cyd_s028r jc1060p470c .
idf.py -B build-cyd_s028r -D SDKCONFIG=build-cyd_s028r/sdkconfig -D BOARD=cyd_s028r build
idf.py -B build-jc1060p470c -D SDKCONFIG=build-jc1060p470c/sdkconfig -D BOARD=jc1060p470c build
```

`board_select.py` пишет `sdkconfig.defaults.<плата>` на каждую плату, со строками
ревизии её чипа, и печатает эти команды. Эти файлы коммитятся: свежий клон читает
их раньше, чем скачан компонент. У каждого каталога сборки своя цель, свой
`sdkconfig` и свой lock компонентов, поэтому платы друг другу не мешают. Файлы
каталога напрямую не читаются: строки ревизии есть только в том, что пишет
`board_select.py`.

`-D SDKCONFIG_DEFAULTS=...` в командной строке побеждает оба варианта: фрагмент
CMake выше задаёт переменную только когда она не задана.

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

## Без board_select.py

Файл, который он записывает, — копия `catalog/boards/<board>/sdkconfig.defaults`.
Любой другой способ попасть этому файлу в `SDKCONFIG_DEFAULTS` работает: путь
внутрь `managed_components/` или в чекаут компонента рядом с проектом, или
копирование строк в собственный `sdkconfig.defaults` проекта. И меню работает
как меню: `idf.py menuconfig`, *Boards*, выбрать; но тогда настройки чипа
(режим PSRAM, размер флеша, ревизия чипа) тоже придётся задавать вам самим —
именно от этого и избавляет файл умолчаний.

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
