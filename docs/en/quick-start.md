# Quick start

A program with graphics, first on the computer, in a window with the display of the board chosen, then on the board
itself. The component sets the board up and the program asks for its parts by kind, never by the board's name, so the
same code goes to both. The example here is the CYD S028R (ESP32-2432S028R, 2.8-inch); for another board, its name from
the [README table](../../README.md#the-boards) goes instead of `cyd_s028r`.

The path was checked in VS Code 1.145 with the ESP-IDF 2.3.0 and CMake Tools 1.24 extensions on Linux, with ESP-IDF 6.1.

## What you need

- ESP-IDF 5.5 or 6.x. The EIM installer of Espressif puts it in; in VS Code, "ESP-IDF: Open ESP-IDF Installation Manager".
- VS Code with the ESP-IDF extension of Espressif. CMake Tools, which VS Code offers when it sees CMake files, does no
  harm: the component gives it the environment of ESP-IDF.
- For the program on the computer: Linux with SDL2 and libbsd (`libsdl2-dev`, `libbsd-dev`). Windows is not a target of
  the `linux` target of ESP-IDF.
- For the second half: the board on USB.

## The terminal of ESP-IDF

Every command below, `compote`, `idf.py`, `python3 managed_components/…`, runs in a terminal where ESP-IDF is
activated: `idf.py --version` answers in it. The plain terminal of VS Code (Ctrl+`) is not one: it answers
`command not found`.

- In VS Code, in a window with a folder open: Ctrl+Shift+P → "ESP-IDF: Open ESP-IDF Terminal". When the extension
  does not know yet which installation to take, "ESP-IDF: Select Current ESP-IDF Version" first. The terminal belongs to
  its window of VS Code: in a new window, "Open ESP-IDF Terminal" again. The extension puts into that terminal the
  `IDF_TARGET` it takes for the current one. `board_select.py` tells it the current board, but the extension reads the
  target when it starts. After a change of the board: "Developer: Reload Window" (CMake Tools then asks for a preset:
  choose the same board in its list), then a new terminal of ESP-IDF, and close the old ones: a terminal that was open
  is joined again to the same process by VS Code after the reload, with its old variables. When `idf.py` says
  `IDF_TARGET` differs from the target of the board, run `unset IDF_TARGET` in the terminal: the preset gives the board
  and its target.
- In a plain terminal, the activation of your installation: for EIM,
  `source ~/.espressif/tools/activate_idf_v6.1.sh` (with your version); for an installation by `install.sh`,
  `. ~/esp/esp-idf/export.sh`. Such a terminal sets no `IDF_TARGET`, and the preset of each board gives its target.

## 1. The project

There is no project yet, and nothing to open in VS Code, so it is made in a plain terminal of the system, where ESP-IDF
is activated by the command of your installation:

```sh
source ~/.espressif/tools/activate_idf_v6.1.sh      # EIM; with an installation by install.sh, . ~/esp/esp-idf/export.sh
compote project create-from-example -p my_project jef-sure/boards:hello
code my_project
```

The folder `my_project` is a new one or an empty one: the example does not go into a folder with files. It has a
`.gitignore`, a `CMakeLists.txt` that reads the board, and the program `main/main.c`. The component comes from the
registry; no clone of the repository is needed.

The example is named `hello`, and the program would build into `hello.elf`. Give it its own name at once, before the
board: the last line of `CMakeLists.txt`, `project(hello)`, becomes `project(my_project)`. The page takes that name
too: it names the board of the program `<project>_<board>` and keeps the name in `selection.json`.

So far it is a folder on your machine. It goes to GitHub later, once the project builds (step 5). A repository on
GitHub is not made first and cloned here: with a licence or a README the folder is no longer empty.

The last command opens the folder in VS Code (as File → Open Folder does). In that window open a terminal of ESP-IDF,
Ctrl+Shift+P → "ESP-IDF: Open ESP-IDF Terminal", and run in it:

```sh
idf.py reconfigure
```

It downloads the component into `managed_components/` and writes into `.vscode/settings.json` the environment of ESP-IDF
that CMake Tools builds the project with. The ESP-IDF extension, once the folder is open, offers "compile_commands.json is
missing…" at the bottom right with the button "Generate compile_commands.json": it runs the same `idf.py reconfigure`
("ESP-IDF: Run idf.py reconfigure Task"), so the button does instead of the command.

## 2. The board

A board you know is one command, the computer another:

```sh
python3 managed_components/jef-sure__boards/tools/board_select.py cyd_s028r .
python3 managed_components/jef-sure__boards/tools/board_select.py host --as cyd_s028r .
```

The first writes `sdkconfig.defaults.cyd_s028r`, the preset of the board in `CMakePresets.json` and its lock of the
components. The second does the same for the computer `host_cyd_s028r`: a window with the display of the CYD, turned as
the board is held. Another `--as` gives another computer beside it, as `host_jc1060p470c`. The board named last is the
current one, here the computer. No `set-target` and no `menuconfig`. In VS Code, after a change of the board, reload the
window ("Developer: Reload Window"), choose the current board in the list of presets CMake Tools then shows, and open a
new terminal of ESP-IDF: so the extension takes the target of the current board. Close the old terminals of ESP-IDF:
they keep the old target.

When the board is not chosen yet, the page of the component helps to choose it: `editor/index.html` of its copy in
`managed_components/`. On it a device is described: what it needs goes on the canvas, a display, a touch, sensors, and
the boards of the catalog that give it come on the right, with the modules to buy for them. Each board shows what it has
and on which pins, the wires to the modules, what it all costs and the libraries the board starts. The page can write
what is chosen into the project. It runs on your machine: it is opened in a browser through a small server of the
component. Start it from the folder of the project:

```sh
python3 managed_components/jef-sure__boards/tools/boards_mcp.py --serve
```

It prints a link. Open it in the integrated browser of VS Code: Ctrl+Shift+P → "Browser: Open Integrated Browser" and the
link in its address bar; with the setting `workbench.browser.openLocalhostLinks`, Ctrl+click on the link in the terminal
does. The board of the project has a card of its own, and its parts are in the list on the left: a part from there goes
on the canvas with the characteristics it has on that board. See [tools.md](tools.md#the-page).

The page keeps the canvas in the browser at once, but for its address. The server takes a free port each time it starts,
and on a new port the canvas is empty; `--serve --port 8765` keeps the address. Into the project the page writes only by
the button "make the project of these boards…" (or "make a project…" on a card), once you allow it:
- the files of the board;
- a board of the program, `components/local-boards/boards/<project>_<board>`, when the canvas has not all the board has:
  its glue starts only what is on the canvas;
- `selection.json` with the canvas, which the page starts from when the folder is opened again.

The page does not write the program, `main/main.c`. `board_display_init()` starts the display, and the glue of the board
knows how to start it on that board.

## 3. On the computer

In VS Code: Ctrl+Shift+P → "CMake: Select Configure Preset" → "the computer as CYD (ESP32-2432S028R)", then F7
("CMake: Build") and Ctrl+Shift+F5 ("CMake: Run Without Debugging"). A window opens: white, with a blue band at the
top. The touch is the mouse, the BOOT button the key B.

The same from a terminal of ESP-IDF:

```sh
idf.py build
build/host_cyd_s028r/my_project.elf
```

ESP-IDF 6 builds the current board by its preset. ESP-IDF 5 does not read presets:
`idf.py -B build/host_cyd_s028r -D SDKCONFIG=build/host_cyd_s028r/sdkconfig -D BOARD=host_cyd_s028r build`.

The program, `main/main.c`:

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

Every function of `boards.h` exists on every board; one for a part the board does not have returns `false`. Change the
colour of the band to red, `DGX_RED(dgx_rgb_to_16)` for `DGX_BLUE(dgx_rgb_to_16)`, press F7 and Ctrl+Shift+F5: the band
is red. The names of the colours are in `dgx_colors.h` of DGX.

## 4. On the board

Connect the board by USB. In VS Code: Ctrl+Shift+P → "ESP-IDF: Select Project Configuration" → "CYD (ESP32-2432S028R)",
then "ESP-IDF: Select Port to Use" and "ESP-IDF: Build, Flash and Start a Monitor on Your Device". The extension builds
the board in `build/cyd_s028r`. From a terminal of ESP-IDF 6 the same is `idf.py --preset cyd_s028r build flash monitor`.

The log of the CYD S028R:

```
the board: CYD (ESP32-2432S028R) (cyd_s028r), esp32
the display: 320 x 240 pixels, 58 x 43 mm
the touch: 1 fingers
the button: free
```

The screen shows the picture of the window on the computer. The monitor holds the port: close it, Ctrl+], before the
next flash.

## 5. On GitHub, if you want

Once the project builds, it is ready for its first commit. In the folder of the project:

```sh
git init -b main
git add .
git commit -m "new project"
```

The `.gitignore` of the project keeps out `build/`, `managed_components/`, `sdkconfig`, the clangd index `.cache/` and
`.vscode/` with the paths of this machine. The files `sdkconfig.defaults.<board>`, `CMakePresets.json` and
`dependencies.lock.<board>` are committed: the project does not build without them.

With the [GitHub CLI](https://cli.github.com/) (`gh`), after one `gh auth login`, the licence and the repository are
three commands:

```sh
gh repo license view mit > LICENSE      # put the year and the name for [year] and [fullname]
git add LICENSE && git commit -m "add the licence"
gh repo create my_project --public --source . --push
```

`gh repo create` with `--source` takes no licence, so the licence is a file.

Without `gh`: on github.com make an empty repository `my_project`, with no README, `.gitignore` or licence, or the first
`push` is refused, and send the project to it:

```sh
git remote add origin https://github.com/<your name>/my_project.git
git push -u origin main
```

GitHub adds the licence then: Add file → Create new file, the name `LICENSE`, the button "Choose a license template";
then `git pull`.

## 6. Next

- Drawing: [DGX](https://components.espressif.com/components/jef-sure/dgx), its README. The screen `board_dgx_screen()`
  gives is the same on the computer and on the board.
- Another board, or several: [choosing-a-board.md](choosing-a-board.md).
- A program you have already: [moving-a-program.md](moving-a-program.md).
- Choosing a board with an agent: `python3 managed_components/jef-sure__boards/tools/boards_mcp.py --install` once a
  machine, before the page; see [tools.md](tools.md#boards_mcppy).

## What not to do

| what was done | what you see | the right way |
|---|---|---|
| `idf.py` or `compote` in a plain terminal with no activation | `command not found` | the activation of ESP-IDF, or a terminal of "ESP-IDF: Open ESP-IDF Terminal" |
| `idf.py build` in a terminal of ESP-IDF while the extension takes another target for the current one | `was generated for target 'linux', but environment variable IDF_TARGET is set to 'esp32'` | `unset IDF_TARGET` in that terminal |
| `idf.py set-target`, as `idf.py` advises | the build goes to the root `build/` and fails | not needed: the preset of the board gives the target and the directory |
| the example made in a folder with files, as a clone with only a licence | `is not empty` | a new folder; the repository on GitHub last, from the folder made |
| `editor/index.html` opened by a right click → "Open in Integrated Browser" | the page with no catalog, naming the command of its server | `boards_mcp.py --serve` from the folder of the project, and its link |
| CMake Tools configured the project before the first `idf.py` | `IDF_PATH is not set` | `idf.py reconfigure` in a terminal of ESP-IDF, then the configure of CMake Tools again |
| "Build Project" of the ESP-IDF extension with no project configuration chosen | `no board chosen` and the boards of the project | "ESP-IDF: Select Project Configuration" |
| F5 ("Run and Debug") for the program on the computer | a request for `launch.json`, a program `a.out` | Ctrl+Shift+F5, "CMake: Run Without Debugging" |
| "ESP-IDF: Launch Debug", or its button at the bottom | a request for `launch.json` or to build the project; after the build, nothing | that is debugging on the chip: before it starts, the extension compares the program with the chip through the port by `build/<board>/flasher_args.json`, which a build for the computer does not make. `gdb build/host_cyd_s028r/my_project.elf` debugs the program on the computer; the CYD has no JTAG of its own on USB |
| a flash while the monitor is open | `the port is busy or doesn't exist` | close the monitor, Ctrl+] |
| on an ESP32, drawn first and the touch started after | the end of the picture wrong | every part first, then the work: see [api.md](api.md) |
| a kind of part on the canvas that the catalog has none of, as a character display | nothing fits | only parts of the catalog fit for now; it has no module of a character display |
