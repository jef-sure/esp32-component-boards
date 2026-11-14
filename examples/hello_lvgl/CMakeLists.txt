# LVGL on the chosen board. The board is chosen by tools/board_select.py, as for hello_board:
#
#     python3 ../../tools/board_select.py cyd_s028r .    # or jc1060p470c, jc8012p4a1c, jc4827w543c
#     idf.py build flash monitor
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
        message(FATAL_ERROR "${BOARD} is built for ${_boards_target}, and this configuration is for ${IDF_TARGET}: a board builds by "
                            "its own preset, idf.py --preset <board> build, or in VS Code ESP-IDF: Select Project Configuration. "
                            "set-target, or -D BOARD with the preset of another board, chooses no board.")
    endif()
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults.${BOARD}")
    if(EXISTS ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults)
        list(APPEND SDKCONFIG_DEFAULTS "sdkconfig.defaults")
    endif()
elseif(NOT BOARD AND NOT SDKCONFIG)
    # no board: its sdkconfig stays in build/, as idf.py checks the target of <project>/sdkconfig while a board has no build
    set(SDKCONFIG ${CMAKE_BINARY_DIR}/sdkconfig)
endif()

# The component this example lies in. A project of its own takes it from the registry instead
# (main/idf_component.yml: jef-sure/boards: "^0.1.4"). BOARDS_COMPONENT_DIR points elsewhere
# when the example is copied out of the checkout.
if(NOT DEFINED BOARDS_COMPONENT_DIR)
    get_filename_component(BOARDS_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
endif()
set(EXTRA_COMPONENT_DIRS "${BOARDS_COMPONENT_DIR}")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
# each board has its lock of the components beside the project, to commit: dependencies.lock.<board>
if(BOARD)
    idf_build_set_property(DEPENDENCIES_LOCK ${CMAKE_CURRENT_LIST_DIR}/dependencies.lock.${BOARD})
endif()
project(hello_lvgl)
