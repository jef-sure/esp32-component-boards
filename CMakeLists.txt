# jef-sure/boards: the boards a program runs on, described as data and set up by the component.
# A directory a board in catalog/boards/ (pins, buses, peripherals), its glue in boards/, the core
# in src/, the code for each library in adapters/<owner>__<name>/.
# The board is chosen by CONFIG_BOARD_SELECT_<BOARD> (its sdkconfig.defaults carries the line,
# the menu follows); what it needs comes as manifest rules (dependencies) and the Kconfig of
# the boards (selects). Kconfig and boards/boards.cmake are made by tools/boards_gen.py --all
# from the data, as the glue is.
include("${CMAKE_CURRENT_LIST_DIR}/boards/boards.cmake")
idf_component_register(SRCS "src/boards.c" "src/board_i2c.c" "src/board_spi.c" "src/board_button.c" "src/board_sound.c" "src/board_touch.c" "src/board_touch_fw.c"
                       INCLUDE_DIRS "include" ${BOARDS_ADAPTER_INCLUDES}
                       PRIV_INCLUDE_DIRS "src" ${BOARDS_ADAPTER_DIRS}
                       PRIV_REQUIRES esp_driver_i2c esp_driver_gpio esp_driver_spi)

# The glue of the boards and the modules, beside the core: only the chosen board's is compiled,
# by the symbol its data owns (CONFIG_BOARD_<BOARD>, 1 when chosen), and a module's by its
# option (CONFIG_BOARD_MODULE_<MODULE>). The lists come from the data: boards/boards.cmake.
set(_boards_glue "")
foreach(_board ${BOARDS_LIST})
    string(TOUPPER "${_board}" _upper)
    if(CONFIG_BOARD_${_upper})
        list(APPEND _boards_glue boards/${_board}/${_board}.c)
        # what the board's glue needs at link (its panel driver, its touch, its codec), named
        # by the board itself in its directory, beside the data it is for
        include("${CMAKE_CURRENT_LIST_DIR}/boards/${_board}/board.cmake")
    endif()
endforeach()
# A board of the program: its glue lies in the component local-boards of the project, made by tools/board_select.py.
idf_build_get_property(_project_dir PROJECT_DIR)
file(GLOB _local_boards "${_project_dir}/components/local-boards/boards/*/board.cmake")
foreach(_cmake ${_local_boards})
    get_filename_component(_dir "${_cmake}" DIRECTORY)
    get_filename_component(_board "${_dir}" NAME)
    string(TOUPPER "${_board}" _upper)
    if(CONFIG_BOARD_${_upper})
        list(APPEND _boards_glue "${_dir}/${_board}.c")
        include("${_cmake}")
    endif()
endforeach()
foreach(_module ${BOARDS_MODULES})
    string(TOUPPER "${_module}" _upper)
    if(CONFIG_BOARD_MODULE_${_upper})
        list(APPEND _boards_glue boards/${_module}/${_module}.c)
        include("${CMAKE_CURRENT_LIST_DIR}/boards/${_module}/board.cmake")
    endif()
endforeach()
# The code of the adapters: each source by the symbol its library's record names, SYMBOL=path.
foreach(_entry ${BOARDS_ADAPTER_SOURCES})
    string(REPLACE "=" ";" _parts "${_entry}")
    list(GET _parts 0 _symbol)
    list(GET _parts 1 _source)
    if(CONFIG_${_symbol})
        list(APPEND _boards_glue ${_source})
    endif()
endforeach()
list(LENGTH _boards_glue _boards_len)
if(_boards_len)
    target_sources(${COMPONENT_LIB} PRIVATE ${_boards_glue})
endif()
unset(_project_dir)
unset(_local_boards)
unset(_cmake)
unset(_dir)
unset(_boards_glue)
unset(_boards_len)
unset(_board)
unset(_module)
unset(_upper)
unset(_entry)
unset(_parts)
unset(_symbol)
unset(_source)
