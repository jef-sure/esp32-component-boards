# LVGL on the chosen board. The board is chosen by tools/board_select.py, as for hello_board:
#
#     python3 ../../tools/board_select.py cyd_s028r .    # or jc1060p470c, jc8012p4a1c, jc4827w543c
#     idf.py build flash monitor
cmake_minimum_required(VERSION 3.22)
if(NOT SDKCONFIG_DEFAULTS AND EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults.board)
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.board;sdkconfig.defaults")
endif()

# The component this example lies in. A project of its own takes it from the registry instead
# (main/idf_component.yml: jef-sure/boards: "^0.0.1"). BOARDS_COMPONENT_DIR points elsewhere
# when the example is copied out of the checkout.
if(NOT DEFINED BOARDS_COMPONENT_DIR)
    get_filename_component(BOARDS_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
endif()
set(EXTRA_COMPONENT_DIRS "${BOARDS_COMPONENT_DIR}")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(hello_lvgl)
