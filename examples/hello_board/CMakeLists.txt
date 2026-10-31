# The board the program runs on, as it is: the smallest program of jef-sure/boards.
#
# The board is chosen once, by tools/board_select.py of the component, which writes
# sdkconfig.defaults.board here (the board's chip, its memory, its flash, and the line that
# chooses it in the menu):
#
#     python3 ../../tools/board_select.py cyd_s028r .    # or jc1060p470c, jc8012p4a1c, jc4827w543c
#     python3 ../../tools/board_select.py jc1060p470c --module lcd2004_pcf8574 .
#     idf.py build flash monitor
#
# Nothing here names a board. A -D SDKCONFIG_DEFAULTS=... on the command line wins over the file.
cmake_minimum_required(VERSION 3.22)
if(NOT SDKCONFIG_DEFAULTS AND EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.board)
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.board;sdkconfig.defaults")
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
project(hello_board)
