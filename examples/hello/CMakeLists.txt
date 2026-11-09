# hello. The boards are chosen by tools/board_select.py of jef-sure/boards: sdkconfig.defaults.<board> of each and
# CMakePresets.json, whose preset sets BOARD; a board of this program lies in components/local-boards/.
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
        message(FATAL_ERROR "${BOARD} is built for ${_boards_target}, and this configuration asks for ${IDF_TARGET}: set-target "
                            "chooses no board. Build another board by its preset: idf.py --preset <board> build, or in VS Code "
                            "ESP-IDF: Select Project Configuration.")
    endif()
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.${BOARD}")
    if(EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults)
        list(APPEND SDKCONFIG_DEFAULTS "sdkconfig.defaults")
    endif()
elseif(NOT BOARD AND NOT SDKCONFIG)
    # no board: its sdkconfig stays in build/, as idf.py checks the target of <project>/sdkconfig while a board has no build
    set(SDKCONFIG ${CMAKE_BINARY_DIR}/sdkconfig)
endif()

# the computer (BOARD=host_<board>, the linux target of ESP-IDF): only main and what it asks, the drivers of a chip are not there
if(BOARD MATCHES "^host_")
    set(COMPONENTS main)
    # in a shell of ESP-IDF the linker of a chip comes first in PATH: the compiler of the computer looks in /usr/bin first
    set(CMAKE_EXE_LINKER_FLAGS "-B/usr/bin/")
endif()

# cmake run outside ESP-IDF, as CMake Tools of VS Code is before the project's first configuration by idf.py
if(NOT DEFINED ENV{IDF_PATH})
    message(FATAL_ERROR "IDF_PATH is not set: configure the project once with idf.py reconfigure in a terminal of ESP-IDF "
                        "(in VS Code: ESP-IDF: Open ESP-IDF Terminal); that gives CMake Tools the environment in .vscode/settings.json")
endif()
# no BOARD while the presets of board_select.py are here: cmake run with no preset, as the build of the ESP-IDF extension
# with no project configuration chosen, would build none of the boards, or fail at the compiler of the computer
if(NOT BOARD AND NOT SDKCONFIG_DEFAULTS AND EXISTS ${CMAKE_CURRENT_LIST_DIR}/CMakePresets.json)
    file(READ ${CMAKE_CURRENT_LIST_DIR}/CMakePresets.json _boards_presets)
    if(_boards_presets MATCHES "\"jef-sure/boards\"")
        message(FATAL_ERROR "no board chosen: this configuration has no BOARD. In VS Code choose one: ESP-IDF: Select Project "
                            "Configuration, or CMake: Select Configure Preset. On ESP-IDF 6 idf.py build builds the current board "
                            "and idf.py --preset <board> build another; on ESP-IDF 5 idf.py -B build/<board> "
                            "-D SDKCONFIG=build/<board>/sdkconfig -D BOARD=<board> build.")
    endif()
endif()
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
# each board has its lock of the components beside the project, to commit: dependencies.lock.<board>
if(BOARD)
    idf_build_set_property(DEPENDENCIES_LOCK ${CMAKE_CURRENT_LIST_DIR}/dependencies.lock.${BOARD})
endif()
project(hello)
