# The level of the sound a board is comfortable at, heard: a tone at levels from 5 to 100 percent.
#
# The board is chosen once, by tools/board_select.py of the component, which writes
# sdkconfig.defaults.<board> here (the board's chip, its memory, its flash, and the line that
# chooses it in the menu) and CMakePresets.json, whose preset builds the board in build/<board>:
#
#     python3 ../../tools/board_select.py cyd_s028r .    # or jc1060p470c, jc8012p4a1c, jc4827w543c
#     idf.py build flash monitor
#
# Nothing here names a board.
cmake_minimum_required(VERSION 3.22)
# BOARD=<board>, which the preset of a board sets, builds with sdkconfig.defaults.<board> that board_select.py writes,
# then with the program's own sdkconfig.defaults when it has one. A -D SDKCONFIG_DEFAULTS=... on the command line wins.
set(BOARD "" CACHE STRING "a board of this project: its file sdkconfig.defaults.<board>")
if(NOT SDKCONFIG_DEFAULTS AND BOARD)
    if(NOT EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.${BOARD})
        message(FATAL_ERROR "no sdkconfig.defaults.${BOARD} here: run board_select.py ${BOARD} . of jef-sure/boards")
    endif()
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.${BOARD}")
    if(EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults)
        list(APPEND SDKCONFIG_DEFAULTS "sdkconfig.defaults")
    endif()
endif()

# The component this example lies in, taken as a component of the project by its directory: a
# project of its own takes it from the registry instead (main/idf_component.yml:
# jef-sure/boards: ">=0.0.6") and has nothing of this. BOARDS_COMPONENT_DIR points elsewhere
# when the example is copied out of the checkout (-D BOARDS_COMPONENT_DIR=/path/to/boards).
if(NOT DEFINED BOARDS_COMPONENT_DIR)
    get_filename_component(BOARDS_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
endif()
set(EXTRA_COMPONENT_DIRS "${BOARDS_COMPONENT_DIR}")
# the computer (BOARD=host, the linux target of ESP-IDF): only main and the component, the drivers of a chip are not there
if(BOARD STREQUAL "host")
    get_filename_component(_boards_name "${BOARDS_COMPONENT_DIR}" NAME)
    set(COMPONENTS main ${_boards_name})
    # in a shell of ESP-IDF the linker of a chip comes first in PATH: the compiler of the computer looks in /usr/bin first
    set(CMAKE_EXE_LINKER_FLAGS "-B/usr/bin/")
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
# each board has its lock of the components beside the project, to commit: dependencies.lock.<board>
if(BOARD)
    idf_build_set_property(DEPENDENCIES_LOCK ${CMAKE_CURRENT_LIST_DIR}/dependencies.lock.${BOARD})
endif()
project(sound_level)
