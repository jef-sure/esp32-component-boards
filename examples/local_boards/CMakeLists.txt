# A program with a board of its own: components/local-boards holds it, in the layout of catalog/.
#
#     python3 ../../tools/board_select.py my_board .
#     idf.py build flash monitor
#
cmake_minimum_required(VERSION 3.22)
# BOARD=<board> builds with sdkconfig.defaults.<board>, which board_select.py writes for several boards; one board
# is sdkconfig.defaults.board. A -D SDKCONFIG_DEFAULTS=... on the command line wins over both.
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

# The component this example lies in, taken as a component of the project by its directory: a
# project of its own takes it from the registry instead (main/idf_component.yml:
# jef-sure/boards: "^0.0.1") and has nothing of this. BOARDS_COMPONENT_DIR points elsewhere
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
# the lock of the components in the build directory: two boards built side by side keep their own
idf_build_set_property(DEPENDENCIES_LOCK ${CMAKE_BINARY_DIR}/dependencies.lock)
project(local_boards)
