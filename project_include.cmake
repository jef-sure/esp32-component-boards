# The primary display of the board chosen, as shown, for the CMake of a program: BOARD_PIXELS (width height)
# and BOARD_MM (width height in millimetres, 0 0 when the data has no size), empty for a board with no pixel
# display. ESP-IDF includes this file after it reads the configuration, so main/CMakeLists.txt sees them; the
# early expansion of the requirements does not include it, and there they are empty.
# The numbers are in boards/<board>/display.cmake, made by tools/boards_gen.py, here or in components/local-boards.
file(GLOB _boards_displays "${COMPONENT_DIR}/boards/*/display.cmake" "${PROJECT_DIR}/components/local-boards/boards/*/display.cmake")
foreach(_boards_display ${_boards_displays})
    get_filename_component(_boards_dir "${_boards_display}" DIRECTORY)
    get_filename_component(_boards_name "${_boards_dir}" NAME)
    string(TOUPPER "${_boards_name}" _boards_upper)
    if(CONFIG_BOARD_${_boards_upper})
        include("${_boards_display}")
    endif()
endforeach()
# the computer shows a board: its numbers, a board of the program first, as board_select.py reads it
if(CONFIG_BOARD_SELECT_HOST)
    if(EXISTS "${PROJECT_DIR}/components/local-boards/boards/${CONFIG_BOARD_HOST_SHOWS}/display.cmake")
        include("${PROJECT_DIR}/components/local-boards/boards/${CONFIG_BOARD_HOST_SHOWS}/display.cmake")
    elseif(EXISTS "${COMPONENT_DIR}/boards/${CONFIG_BOARD_HOST_SHOWS}/display.cmake")
        include("${COMPONENT_DIR}/boards/${CONFIG_BOARD_HOST_SHOWS}/display.cmake")
    endif()
endif()
unset(_boards_displays)
unset(_boards_display)
unset(_boards_dir)
unset(_boards_name)
unset(_boards_upper)

# BOARD names the board a build is for (the CMake of a project board_select.py serves, its presets): the configuration
# must have chosen it. A preset of another chip under ESP-IDF 6, an sdkconfig of another board in the build directory
# would otherwise build another board, or none, with no error.
if(BOARD AND DEFINED CONFIG_IDF_TARGET AND EXISTS "${PROJECT_DIR}/sdkconfig.defaults.${BOARD}")
    file(STRINGS "${PROJECT_DIR}/sdkconfig.defaults.${BOARD}" _boards_record LIMIT_COUNT 1)
    string(TOUPPER "${BOARD}" _boards_upper)
    if(_boards_record MATCHES "^# board_select.py " AND NOT CONFIG_BOARD_SELECT_${_boards_upper})
        set(_boards_chosen "none")
        get_cmake_property(_boards_variables VARIABLES)
        foreach(_boards_variable ${_boards_variables})
            if(_boards_variable MATCHES "^CONFIG_BOARD_SELECT_(.+)$" AND "${${_boards_variable}}")
                string(TOLOWER "${CMAKE_MATCH_1}" _boards_chosen)
            endif()
        endforeach()
        file(STRINGS "${PROJECT_DIR}/sdkconfig.defaults.${BOARD}" _boards_target REGEX "^CONFIG_IDF_TARGET=")
        message(FATAL_ERROR "the board ${BOARD} was asked for, but the configuration chose ${_boards_chosen}: this build is for "
                            "${CONFIG_IDF_TARGET}, sdkconfig.defaults.${BOARD} has ${_boards_target}. On ESP-IDF 6 a board builds by its "
                            "preset, idf.py --preset ${BOARD} build; on ESP-IDF 5 by idf.py -B build/${BOARD} -D SDKCONFIG=build/${BOARD}/sdkconfig "
                            "-D BOARD=${BOARD} build. An sdkconfig of another board in the build directory does the same: remove it.")
    endif()
endif()
unset(_boards_record)
unset(_boards_upper)
unset(_boards_chosen)
unset(_boards_variables)
unset(_boards_variable)
unset(_boards_target)

# CMake Tools of VS Code builds by the presets in the environment of VS Code, which has no ESP-IDF: this configuration
# has it and gives it to the project's .vscode/settings.json, see tools/vscode_env.py
idf_build_get_property(_boards_python PYTHON)
execute_process(COMMAND "${_boards_python}" "${COMPONENT_DIR}/tools/vscode_env.py" "${PROJECT_DIR}"
                RESULT_VARIABLE _boards_status OUTPUT_VARIABLE _boards_said ERROR_VARIABLE _boards_said OUTPUT_STRIP_TRAILING_WHITESPACE)
if(_boards_status)
    message(WARNING "tools/vscode_env.py: ${_boards_said}")
elseif(_boards_said)
    message(STATUS "${_boards_said}")
endif()
unset(_boards_python)
unset(_boards_status)
unset(_boards_said)
