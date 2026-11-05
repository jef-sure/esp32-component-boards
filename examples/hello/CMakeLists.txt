# The program of the quick start (docs/en/quick-start.md): the board is chosen by tools/board_select.py of
# jef-sure/boards, which writes sdkconfig.defaults.<board> and CMakePresets.json here.
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
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
if(BOARD)
    idf_build_set_property(DEPENDENCIES_LOCK ${CMAKE_CURRENT_LIST_DIR}/dependencies.lock.${BOARD})
endif()
project(hello)
