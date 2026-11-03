# @TITLE@. The board is chosen once, by tools/board_select.py of jef-sure/boards, which writes
# sdkconfig.defaults.board here; a board of this program lies in components/local-boards/.
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

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
# the lock of the components in the build directory: two boards built side by side keep their own
idf_build_set_property(DEPENDENCIES_LOCK ${CMAKE_BINARY_DIR}/dependencies.lock)
project(@NAME@)
