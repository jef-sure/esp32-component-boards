# Быстрый старт

Программа с графикой сначала на компьютере, в окне с дисплеем выбранной платы, потом на самой плате. Компонент
настраивает плату, а программа запрашивает её части по типу, а не по имени платы, поэтому один и тот же код идёт и туда,
и туда. Пример здесь — CYD S028R (ESP32-2432S028R, 2,8 дюйма); для другой платы вместо `cyd_s028r` подставьте её имя из
[таблицы README](../../README.ru.md#платы).

Путь проверен в VS Code 1.145 с расширениями ESP-IDF 2.3.0, CMake Tools 1.24 и clangd 0.6.0 на Linux, с ESP-IDF 6.1.

## Что нужно

- ESP-IDF 5.5 или 6.x. Его ставит установщик Espressif EIM, в VS Code — «ESP-IDF: Open ESP-IDF Installation Manager».
- VS Code с расширением ESP-IDF от Espressif. CMake Tools, который VS Code предлагает поставить, увидев файлы CMake, не
  мешает: компонент даёт ему окружение ESP-IDF.
- Для программы на компьютере — Linux с SDL2 и libbsd (`libsdl2-dev`, `libbsd-dev`). Windows целью ESP-IDF `linux`
  не является.
- Для второй половины — плата на USB.
- Расширение clangd (`llvm-vs-code-extensions.vscode-clangd`): с ним работают подсказки и переход к определению, F12.
  Расширение ESP-IDF настраивает его само: `clangd` из ESP-IDF и сборка текущей платы. IntelliSense расширения C/C++ от
  Microsoft выключите, `"C_Cpp.intelliSenseEngine": "disabled"`, чтобы не работали два движка.

В ESP-IDF 6.1 `clangd` ставится всегда, но без заголовков самого clang, и редактор пишет `'stddef.h' file not found`.
Один раз на установку их кладут рядом с ним (Linux x86-64):

```sh
source ~/.espressif/tools/activate_idf_v6.1.sh
cd "$(dirname "$(which clangd)")/.."     # esp-clangd этой установки
V=$(basename "$(dirname "$PWD")")         # его версия, esp-21.1.3_20260408
curl -L https://github.com/espressif/llvm-project/releases/download/$V/libs-clang-$V-x86_64-linux-gnu.tar.xz |
    tar -xJ --strip-components=1 esp-clang/lib/clang
```

Архив — 83 МБ, из него берутся только заголовки, 8 МБ, в `lib/clang/21`. Затем в VS Code: Ctrl+Shift+P → «clangd:
Restart language server». В ESP-IDF 5.5 и 6.0 `clangd` входит в esp-clang, который ставится по запросу.

## Терминал ESP-IDF

Все команды ниже — `compote`, `idf.py`, `python3 managed_components/…` — выполняются в терминале, где ESP-IDF
активирован: в нём `idf.py --version` отвечает. Обычный терминал VS Code (Ctrl+`) не такой: в нём будет
`command not found`.

- В VS Code, в окне с открытой папкой: Ctrl+Shift+P → «ESP-IDF: Open ESP-IDF Terminal». Если расширение ещё не знает,
  какую установку брать, сначала «ESP-IDF: Select Current ESP-IDF Version». Терминал открывается в своём окне VS Code: в
  новом окне — снова «Open ESP-IDF Terminal». Расширение кладёт в этот терминал `IDF_TARGET` — цель, которую оно
  считает текущей. `board_select.py` сообщает ему текущую плату, но расширение перечитывает цель при своём запуске.
  После смены платы: «Developer: Reload Window» (CMake Tools при этом спросит пресет — выберите в списке ту же плату),
  затем новый терминал ESP-IDF, а прежние закройте: терминал, который был открыт, VS Code после перезагрузки окна
  подключает к тому же процессу, с прежними переменными. Если `idf.py` пишет, что `IDF_TARGET` не совпадает с целью
  платы, выполните в терминале `unset IDF_TARGET`: плату и её цель задаёт пресет.
- В обычном терминале — команда активации вашей установки: у EIM это
  `source ~/.espressif/tools/activate_idf_v6.1.sh` (с вашей версией), у установки через `install.sh` —
  `. ~/esp/esp-idf/export.sh`. Такой терминал `IDF_TARGET` не задаёт, и пресет каждой платы сам даёт её цель.

## 1. Проект

Проекта ещё нет, и открыть в VS Code пока нечего, поэтому он создаётся в обычном терминале системы, где ESP-IDF
активирован командой вашей установки:

```sh
source ~/.espressif/tools/activate_idf_v6.1.sh      # EIM; с установкой через install.sh — . ~/esp/esp-idf/export.sh
compote project create-from-example -p my_project jef-sure/boards:hello
code my_project
```

Папка `my_project` должна быть новой или пустой: в непустую пример не ложится. В ней уже есть `.gitignore`,
`CMakeLists.txt`, который читает плату, и программа `main/main.c`. Компонент берётся из реестра, клон репозитория не
нужен.

Пример называется `hello`, и программа собралась бы в `hello.elf`. Своё имя задайте сразу, до выбора платы: последнюю
строку `CMakeLists.txt`, `project(hello)`, замените на `project(my_project)`. Это имя берёт и страница: плату программы
она называет `<проект>_<плата>` и запоминает имя в `selection.json`.

Пока это только папка на вашей машине. Отправить её на GitHub можно потом, когда проект соберётся (шаг 5). Репозиторий
на GitHub не создают заранее и не клонируют сюда: с лицензией или README папка уже не пуста.

Последняя команда открывает папку в VS Code (то же — File → Open Folder). В этом окне откройте терминал ESP-IDF,
Ctrl+Shift+P → «ESP-IDF: Open ESP-IDF Terminal», и выполните в нём:

```sh
idf.py reconfigure
```

Команда скачивает компонент в `managed_components/` и записывает в `.vscode/settings.json` окружение ESP-IDF, с которым
CMake Tools собирает проект, а в `.vscode/extensions.json` — расширения ESP-IDF и clangd в рекомендованные: недостающее
VS Code показывает в «Extensions: Show Recommended Extensions». Расширение ESP-IDF, открыв папку, само предлагает внизу
справа «compile_commands.json is missing…» с кнопкой «Generate compile_commands.json»: она запускает ту же `idf.py
reconfigure` («ESP-IDF: Run idf.py reconfigure Task»), так что вместо команды можно нажать её.

## 2. Плата

Плата, которую вы знаете, — одна команда, компьютер — вторая:

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py cyd_s028r .
python3 managed_components/jef-sure__boards/tools/board_select.py host --as cyd_s028r .
```

Первая пишет `sdkconfig.defaults.cyd_s028r`, пресет платы в `CMakePresets.json` и её lock компонентов. Вторая делает то же
для компьютера `host_cyd_s028r`: окно с дисплеем CYD, повёрнутым так, как плату держат. Ещё одно `--as` даёт ещё один
компьютер рядом, например `host_jc1060p470c`. Текущей становится плата, названная последней, здесь компьютер. Без
`set-target` и без `menuconfig`. В VS Code после смены платы перезагрузите окно («Developer: Reload Window»), в списке
пресетов, который тогда покажет CMake Tools, выберите текущую плату и откройте новый терминал ESP-IDF: так расширение
возьмёт цель текущей платы. Прежние терминалы ESP-IDF закройте: в них осталась старая цель.

Если плата ещё не выбрана, её помогает выбрать страница компонента — `editor/index.html` из его копии в
`managed_components/`. На ней описывают устройство: кладут на холст то, что ему нужно, — дисплей, тач, датчики, — а
справа появляются платы каталога, которые это дают, и модули, которые к ним придётся докупить. У каждой платы видно, что
на ней есть и на каких выводах, какие провода тянуть к модулям, сколько всё стоит и какие библиотеки запускает плата.
Выбранное страница может записать в проект. Работает она на вашей машине: её открывают в браузере через небольшой
сервер компонента. Запустите его из папки проекта:

```sh
python3 managed_components/jef-sure__boards/tools/boards_mcp.py --serve
```

Он печатает ссылку. Откройте её во встроенном браузере VS Code: Ctrl+Shift+P → «Browser: Open Integrated Browser» и
вставьте ссылку в адресную строку; с настройкой `workbench.browser.openLocalhostLinks` хватает Ctrl+клика по ссылке в
терминале. Плату проекта страница показывает отдельной карточкой, а её детали — в левом списке: деталь оттуда ложится
на холст с характеристиками этой платы. См. [tools.md](tools.md#страница).

Холст страница сразу сохраняет в браузере, но для своего адреса. Сервер при каждом запуске берёт свободный порт, и на
новом порту холст пустой; `--serve --port 8765` держит адрес постоянным. В проект страница пишет только по кнопке
«make the project of these boards…» (или «make a project…» на карточке) и после вашего разрешения:
- файлы платы;
- плату программы `components/local-boards/boards/<проект>_<плата>`, если на холсте не всё, что есть у платы: её клей
  запускает только то, что на холсте;
- компьютер, который показывает плату программы, `host_<проект>_<плата>`, если в проекте есть компьютер для самой платы:
  у него тоже только то, что на холсте, и текущим он становится вместо прежнего; прежний остаётся в проекте;
- `selection.json` с холстом — при следующем открытии папки страница начинает с него.

Программу, `main/main.c`, страница не пишет. Дисплей запускает `board_display_init()`, а как его запускать на этой
плате, знает клей платы.

## 3. На компьютере

В VS Code: Ctrl+Shift+P → «CMake: Select Configure Preset» → «the computer as CYD (ESP32-2432S028R)», затем F7
(«CMake: Build») и Ctrl+Shift+F5 («CMake: Run Without Debugging»). Откроется окно: белый экран и синяя полоса сверху.
Тач — это мышь, кнопка BOOT — клавиша B.

То же из терминала ESP-IDF:

```sh
idf.py build
build/host_cyd_s028r/my_project.elf
```

ESP-IDF 6 собирает текущую плату по её пресету. ESP-IDF 5 пресеты не читает:
`idf.py -B build/host_cyd_s028r -D SDKCONFIG=build/host_cyd_s028r/sdkconfig -D BOARD=host_cyd_s028r build`.

Программа, `main/main.c`:

```c
#include <stdio.h>

#include "boards.h"
#include "sdkconfig.h"
#if CONFIG_BOARD_DISPLAY_GRAPHICS
#include "boards_dgx.h"
#include "dgx_bits.h"
#include "dgx_colors.h"
#include "dgx_draw.h"
#endif

void app_main(void)
{
    const board_info_t *board = board_info();
    printf("the board: %s (%s), %s\n", board->title, board->name, board->target);

    /* Start every part before any other work. On an ESP32 both SPI hosts share one DMA, and board_touch_start sets up
     * the touch's host, which resets that DMA: a transfer still on its way, as a picture to the display, breaks. */
    board_display_t display = {0};
    bool            shown   = board_display_init(&display);
    if (shown) printf("the display: %d x %d pixels, %d x %d mm\n", display.width, display.height, display.mm_w, display.mm_h);

    board_touch_t touch;
    if (board_touch_start(&display, &touch)) printf("the touch: %d fingers\n", touch.fingers);

    bool pressed;
    if (board_button(&pressed)) printf("the button: %s\n", pressed ? "held" : "free");

#if CONFIG_BOARD_DISPLAY_GRAPHICS
    if (shown) {
        /* colors of dgx_colors.h packed for 16 bits, RGB565, the depth most displays take; 12, 18 and 24 bits have their
         * dgx_rgb_to_*, and a screen of 1 or 4 bits takes a brightness */
        dgx_screen_t *screen = board_dgx_screen(&display);
        dgx_fill_rectangle(screen, 0, 0, display.width, display.height, DGX_WHITE(dgx_rgb_to_16));
        dgx_fill_rectangle(screen, 0, 0, display.width, display.height / 8, DGX_BLUE(dgx_rgb_to_16)); /* a band at the top */
    }
#endif
}
```

Каждая функция `boards.h` есть на каждой плате; для части, которой у платы нет, она возвращает `false`. Поменяйте цвет
полосы на красный, `DGX_RED(dgx_rgb_to_16)` вместо `DGX_BLUE(dgx_rgb_to_16)`, нажмите F7 и Ctrl+Shift+F5 — полоса станет
красной. Имена цветов — в `dgx_colors.h` DGX.

## 4. На плате

Подключите плату по USB. В VS Code: Ctrl+Shift+P → «ESP-IDF: Select Project Configuration» → «CYD (ESP32-2432S028R)»,
затем «ESP-IDF: Select Port to Use» и «ESP-IDF: Build, Flash and Start a Monitor on Your Device». Расширение собирает
плату в `build/cyd_s028r`. Из терминала ESP-IDF 6 то же: `idf.py --preset cyd_s028r build flash monitor`.

Лог CYD S028R:

```
the board: CYD (ESP32-2432S028R) (cyd_s028r), esp32
the display: 320 x 240 pixels, 58 x 43 mm
the touch: 1 fingers
the button: free
```

На экране та же картинка, что в окне на компьютере. Монитор держит порт: перед следующей прошивкой закройте его, Ctrl+].

## 5. На GitHub, по желанию

Когда проект собрался, он готов к первому коммиту. В папке проекта:

```sh
git init -b main
git add .
git commit -m "new project"
```

`.gitignore` проекта не пускает в коммит `build/`, `managed_components/`, `sdkconfig`, индекс clangd `.cache/` и
`.vscode/` с путями этой машины. Файлы `sdkconfig.defaults.<плата>`, `CMakePresets.json` и `dependencies.lock.<плата>`
коммитятся: без них проект не собирается.

С [GitHub CLI](https://cli.github.com/) (`gh`), после одного `gh auth login`, лицензия и репозиторий — три команды:

```sh
gh repo license view mit > LICENSE      # впишите год и имя вместо [year] и [fullname]
git add LICENSE && git commit -m "add the licence"
gh repo create my_project --public --source . --push
```

Лицензию `gh repo create` вместе с `--source` не берёт, поэтому она кладётся файлом.

Без `gh`: на github.com создайте пустой репозиторий `my_project` — без README, `.gitignore` и лицензии, иначе первый
`push` откажет, — и отправьте в него проект:

```sh
git remote add origin https://github.com/<ваше имя>/my_project.git
git push -u origin main
```

Лицензию тогда добавляет сам GitHub: Add file → Create new file, имя `LICENSE`, кнопка «Choose a license template»;
после этого `git pull`.

## 6. Дальше

- Рисование: [DGX](https://components.espressif.com/components/jef-sure/dgx), его README. Экран, который даёт
  `board_dgx_screen()`, тот же на компьютере и на плате.
- Другая плата или несколько: [choosing-a-board.md](choosing-a-board.md).
- Своя программа, которая уже есть: [moving-a-program.md](moving-a-program.md).
- Подбор платы вместе с агентом: `python3 managed_components/jef-sure__boards/tools/boards_mcp.py --install` один раз на
  машину, до страницы; см. [tools.md](tools.md#boards_mcppy).

## Чего не делать

| что сделали | что увидите | как правильно |
|---|---|---|
| ничего: так ставит ESP-IDF 6.1 | `'stddef.h' file not found` в редакторе, F12 не находит | заголовки clang рядом с `clangd`, см. «Что нужно» |
| `idf.py` или `compote` в обычном терминале без активации | `command not found` | команда активации ESP-IDF или терминал «ESP-IDF: Open ESP-IDF Terminal» |
| `idf.py build` в терминале ESP-IDF, когда расширение считает текущей другую цель | `was generated for target 'linux', but environment variable IDF_TARGET is set to 'esp32'` | `unset IDF_TARGET` в этом терминале |
| `idf.py set-target`, как советует `idf.py` | сборка уходит в корневой `build/` и падает | не нужен: цель и каталог задаёт пресет платы |
| создали пример в непустой папке, например в клоне с одной лицензией | `is not empty` | новая папка; репозиторий на GitHub — в конце, из готовой папки |
| открыли `editor/index.html` правым кликом → «Open in Integrated Browser» | страница без каталога и с командой сервера | `boards_mcp.py --serve` из папки проекта и его ссылка |
| CMake Tools сконфигурировал проект до первого `idf.py` | `IDF_PATH is not set` | `idf.py reconfigure` в терминале ESP-IDF, затем снова конфигурация CMake Tools |
| «Build Project» расширения ESP-IDF без выбранной конфигурации | `no board chosen` и платы проекта | «ESP-IDF: Select Project Configuration» |
| F5 («Run and Debug») для программы на компьютере | просьба создать `launch.json`, программа `a.out` | Ctrl+Shift+F5, «CMake: Run Without Debugging» |
| «ESP-IDF: Launch Debug», и кнопкой внизу | просьба создать `launch.json` или собрать проект; после сборки — ничего | это отладка на чипе: перед стартом расширение сверяет программу с чипом через порт по `build/<плата>/flasher_args.json`, а сборка для компьютера его не делает. Программу на компьютере отлаживает `gdb build/host_cyd_s028r/my_project.elf`; у CYD нет своего JTAG по USB |
| прошивка при открытом мониторе | `the port is busy or doesn't exist` | закрыть монитор, Ctrl+] |
| на ESP32 нарисовали, а потом запустили тач | конец картинки неверный | сначала все части, потом работа: см. [api.md](api.md) |
| положили на холст вид детали, которой в каталоге нет, например символьный дисплей | ничего не подходит | пока подходят только детали каталога; модулей символьных дисплеев в нём нет |
