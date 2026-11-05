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
