# @TITLE@. The board is chosen once, by tools/board_select.py of jef-sure/boards, which writes
# sdkconfig.defaults.board here; a board of this program lies in components/local-boards/.
cmake_minimum_required(VERSION 3.22)
if(NOT SDKCONFIG_DEFAULTS AND EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.board)
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.board;sdkconfig.defaults")
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(@NAME@)
