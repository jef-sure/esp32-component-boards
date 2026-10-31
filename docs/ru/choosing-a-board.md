# Выбор платы для проекта

Плата называется один раз, в одной командной строке. Всё остальное следует из
этого.

## Новый проект

```sh
idf.py create-project hello && cd hello
idf.py add-dependency "jef-sure/boards^0.0.1"
```

В `CMakeLists.txt`, до подключения `project.cmake`, прочитайте умолчания
платы перед собственными умолчаниями проекта:

```cmake
cmake_minimum_required(VERSION 3.22)
if(NOT SDKCONFIG_DEFAULTS AND EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.board)
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.board;sdkconfig.defaults")
endif()
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(hello)
```

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

Добавьте `sdkconfig.defaults.board` в `.gitignore` проекта, если проект
собирается для нескольких плат; закоммитьте его, если проект для одной.

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
idf.py build
```

`--reset` переносит старый `sdkconfig` в `sdkconfig.old`. Без него
`board_select.py` записывает файл и сообщает вам, что `sdkconfig` мешает.
Проект, собираемый для нескольких плат сразу, держит каталог сборки на каждую
плату:

```sh
idf.py -B build-cyd_s028r -D SDKCONFIG=build-cyd_s028r/sdkconfig \
       -D SDKCONFIG_DEFAULTS="managed_components/jef-sure__boards/catalog/boards/cyd_s028r/sdkconfig.defaults;sdkconfig.defaults" build
```

`-D SDKCONFIG_DEFAULTS=...` в командной строке побеждает
`sdkconfig.defaults.board`: фрагмент CMake выше задаёт переменную только когда
она не задана.

## Что приходит вместе с выбором

- Драйверы DGX панели платы: `select`-ы в choice в Kconfig компонента
  (`CONFIG_DGX_ENABLE_DSI`, `CONFIG_DGX_ENABLE_JD9165`, ...).
- Остальные части: правила в `idf_component.yml` компонента на скрытых
  символах рядом с choice. Сборка для CYD S028R получает `atanisoft/esp_lcd_touch_xpt2046`
  и ничего от GT911 или ES8311; сборка с выбранным *None* не получает ничего
  из DGX.
- Клей выбранной платы, компилируемый в компонент по
  `CONFIG_BOARD_<BOARD>`; его `board.cmake` называет компоненты, которые ему
  нужны.

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
