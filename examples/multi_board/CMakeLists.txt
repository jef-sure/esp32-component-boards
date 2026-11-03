# One program for several boards: board_select.py writes sdkconfig.defaults.<board> for each, and each board
# builds in a directory of its own with its own sdkconfig and lock of the components:
#
#     python3 ../../tools/board_select.py cyd_s028r jc8012p4a1c .
#     idf.py -B build-cyd_s028r -D SDKCONFIG=build-cyd_s028r/sdkconfig -D BOARD=cyd_s028r build
#     idf.py -B build-jc8012p4a1c -D SDKCONFIG=build-jc8012p4a1c/sdkconfig -D BOARD=jc8012p4a1c build
#
# Nothing here names a board. A -D SDKCONFIG_DEFAULTS=... on the command line wins over the files.
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

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
# the lock of the components in the build directory: two boards built side by side keep their own
idf_build_set_property(DEPENDENCIES_LOCK ${CMAKE_BINARY_DIR}/dependencies.lock)
project(multi_board)
