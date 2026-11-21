# jef-sure/boards: the boards a program runs on, described as data and set up by the component.
# A directory a board in catalog/boards/ (pins, buses, peripherals), its glue in boards/, the core
# in src/, the code for each library in adapters/<owner>__<name>/.
# The board is chosen by CONFIG_BOARD_SELECT_<BOARD> (its sdkconfig.defaults carries the line,
# the menu follows); what it needs comes as manifest rules (dependencies) and the Kconfig of
# the boards (selects). Kconfig and boards/boards.cmake are made by tools/boards_gen.py --all
# from the data, as the glue is.
# The version of each library whose versions the glue and the code tell apart, as the component manager chose it, for
# their #if: BOARDS_VERSION_<LIBRARY>=BOARDS_VERSION(major,minor,patch), the list in boards/boards.cmake. A library in the
# project's components/ has no COMPONENT_VERSION; the version line of its manifest gives it.
function(boards_library_versions)
    if(CMAKE_BUILD_EARLY_EXPANSION)
        return()
    endif()
    idf_build_get_property(components BUILD_COMPONENTS)
    foreach(entry ${BOARDS_LIBRARY_VERSIONS})
        string(REPLACE "=" ";" parts "${entry}")
        list(GET parts 0 library)
        list(GET parts 1 macro)
        if(NOT library IN_LIST components)
            continue()
        endif()
        idf_component_get_property(version ${library} COMPONENT_VERSION)
        if(NOT version MATCHES "^[0-9]+\\.[0-9]+\\.[0-9]+$")
            idf_component_get_property(dir ${library} COMPONENT_DIR)
            set(version "")
            if(EXISTS "${dir}/idf_component.yml")
                file(STRINGS "${dir}/idf_component.yml" version REGEX "^version:")
            endif()
        endif()
        if(NOT version MATCHES "([0-9]+)\\.([0-9]+)\\.([0-9]+)")
            message(FATAL_ERROR "the version of ${library} is unknown: the component manager gives none, and ${dir}/idf_component.yml "
                                "has no version line; the glue of the board needs it to choose its calls")
        endif()
        target_compile_definitions(${COMPONENT_LIB} PRIVATE "${macro}=BOARDS_VERSION(${CMAKE_MATCH_1},${CMAKE_MATCH_2},${CMAKE_MATCH_3})")
    endforeach()
endfunction()

include("${CMAKE_CURRENT_LIST_DIR}/boards/boards.cmake")

# The computer (the linux target of ESP-IDF, the board host): nothing of a chip is there, and one file gives boards.h over SDL2,
# its display a window of DGX and its touch the mouse as DGX-DI reads it, which the manifest brings by BOARD_DISPLAY_GRAPHICS
# and BOARD_TOUCH as for a board.
if(IDF_TARGET STREQUAL "linux")
    idf_component_register(SRCS "src/board_host.c" "src/board_volume.c" "src/board_button_find.c" INCLUDE_DIRS "include" "adapters/jef-sure__dgx/include" "adapters/jef-sure__dgx-di/include"
                           PRIV_INCLUDE_DIRS "src" REQUIRES freertos PRIV_REQUIRES nvs_flash)
    if(CONFIG_BOARD_DISPLAY_GRAPHICS)
        idf_component_optional_requires(PUBLIC jef-sure__dgx)
    endif()
    if(CONFIG_BOARD_TOUCH)
        idf_component_optional_requires(PUBLIC jef-sure__dgx-di)
    endif()
    # the flash of a program that has partitions (NVS, a file system) kept in the build directory between runs
    idf_build_get_property(_boards_components BUILD_COMPONENTS)
    if("esp_partition" IN_LIST _boards_components)
        idf_build_get_property(_boards_build_dir BUILD_DIR)
        idf_component_optional_requires(PRIVATE esp_partition)
        target_compile_definitions(${COMPONENT_LIB} PRIVATE "BOARDS_HOST_FLASH=\"${_boards_build_dir}/flash.bin\""
                                                            "BOARDS_HOST_TABLE=\"${_boards_build_dir}/partition_table/partition-table.bin\"")
    endif()
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(BOARDS_SDL2 REQUIRED IMPORTED_TARGET sdl2)
    target_link_libraries(${COMPONENT_LIB} PUBLIC PkgConfig::BOARDS_SDL2 m) # libm, which a chip's program always has
    boards_library_versions()
    return()
endif()
idf_component_register(SRCS "src/boards.c" "src/board_bus.c" "src/board_i2c.c" "src/board_spi.c" "src/board_button.c" "src/board_sound.c" "src/board_touch.c"
                            "src/board_touch_fw.c" "src/board_display_none.c" "src/board_volume.c" "src/board_button_find.c" "src/board_radio.c"
                            "src/board_ethernet.c" "src/board_ethernet_none.c"
                       INCLUDE_DIRS "include" ${BOARDS_ADAPTER_INCLUDES}
                       PRIV_INCLUDE_DIRS "src" ${BOARDS_ADAPTER_DIRS}
                       PRIV_REQUIRES esp_driver_i2c esp_driver_gpio esp_driver_spi nvs_flash)

# The glue of the boards and the modules, beside the core: only the chosen board's is compiled,
# by the symbol its data owns (CONFIG_BOARD_<BOARD>, 1 when chosen), and a module's by its
# option (CONFIG_BOARD_MODULE_<MODULE>). The lists come from the data: boards/boards.cmake.
set(_boards_glue "")
if(CONFIG_BOARD_SELECT_NONE)
    # no board: the tables of a glue, all empty, so that every function of boards.h returns false
    list(APPEND _boards_glue src/board_none.c)
endif()
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
boards_library_versions()
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

# The radio beside the chip (an ESP32-C6 of esp_hosted): a step of the flash keeps its firmware at the esp_hosted this
# build took, when the data says the program sets that firmware. boards/<board>/board.cmake, made by
# tools/boards_gen.py, names the radio: BOARD_RADIO_TARGET, BOARD_RADIO_TRANSPORT, BOARD_RADIO_FIRMWARE and
# BOARD_RADIO_HARDWARE. The facts the step needs go to board_radio.json in the build directory; tools/board_radio.py
# reads them and builds the update program and the image of the radio only when the radio runs another version.
# The target is there in every build that flashes, doing nothing for a board with no such radio: a pre-flash task left in a
# preset of VS Code finds it either way.
if(TARGET flash AND NOT CMAKE_BUILD_EARLY_EXPANSION)
    idf_build_get_property(_boards_components BUILD_COMPONENTS)
    if(NOT BOARD_RADIO_FIRMWARE STREQUAL "program" OR NOT "espressif__esp_hosted" IN_LIST _boards_components)
        add_custom_target(board_radio)
    else()
        idf_build_get_property(_boards_build_dir BUILD_DIR)
        idf_build_get_property(_boards_python PYTHON)
        idf_build_get_property(_boards_project PROJECT_NAME)
        idf_component_get_property(_boards_hosted_dir espressif__esp_hosted COMPONENT_DIR)
        idf_component_get_property(_boards_hosted_version espressif__esp_hosted COMPONENT_VERSION)
        # what the update program shares with the program: the revision of the chip it is built for, the flash, the table
        string(TOUPPER "${IDF_TARGET}" _boards_chip)
        set(_boards_lines "[]")
        set(_boards_host "CONFIG_${_boards_chip}_REV_MIN_${CONFIG_${_boards_chip}_REV_MIN_FULL}=y"
                         "CONFIG_ESPTOOLPY_FLASHSIZE_${CONFIG_ESPTOOLPY_FLASHSIZE}=y"
                         "CONFIG_PARTITION_TABLE_OFFSET=${CONFIG_PARTITION_TABLE_OFFSET}"
                         "CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_${CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ}=y")
        if(CONFIG_${_boards_chip}_SELECTS_REV_LESS_V3)
            list(APPEND _boards_host "CONFIG_${_boards_chip}_SELECTS_REV_LESS_V3=y")
        endif()
        # the L2 cache too: the update program starts from the program's bootloader, which gives the cache its size, and on
        # revision 3 of an ESP32-P4 a program built for another size panics before its first line
        foreach(_boards_cache 128KB 256KB 512KB LINE_64B LINE_128B)
            if(CONFIG_CACHE_L2_CACHE_${_boards_cache})
                list(APPEND _boards_host "CONFIG_CACHE_L2_CACHE_${_boards_cache}=y")
            endif()
        endforeach()
        set(_boards_count 0)
        foreach(_boards_line ${_boards_host})
            string(JSON _boards_lines SET "${_boards_lines}" ${_boards_count} "\"${_boards_line}\"")
            math(EXPR _boards_count "${_boards_count} + 1")
        endforeach()
        set(_boards_board "${BOARD}")
        if(NOT _boards_board)
            set(_boards_board "${BOARD_RADIO_HARDWARE}")
        endif()
        # where the version of esp_hosted comes from, for the step to name when it brings the radio back to an older one
        idf_build_get_property(_boards_lock DEPENDENCIES_LOCK)
        if(NOT _boards_lock)
            idf_build_get_property(_boards_lock PROJECT_DIR)
            set(_boards_lock "${_boards_lock}/dependencies.lock")
        endif()
        file(TO_CMAKE_PATH "${_boards_build_dir}" _boards_build_dir)
        file(TO_CMAKE_PATH "${_boards_hosted_dir}" _boards_hosted_dir)
        file(TO_CMAKE_PATH "${_boards_lock}" _boards_lock)
        string(JSON _boards_facts SET "{}" "board" "\"${_boards_board}\"")
        string(JSON _boards_facts SET "${_boards_facts}" "hardware" "\"${BOARD_RADIO_HARDWARE}\"")
        string(JSON _boards_facts SET "${_boards_facts}" "build_dir" "\"${_boards_build_dir}\"")
        string(JSON _boards_facts SET "${_boards_facts}" "project_name" "\"${_boards_project}\"")
        string(JSON _boards_facts SET "${_boards_facts}" "lock" "\"${_boards_lock}\"")
        # a URL, not a path: TO_CMAKE_PATH would split it; its backslashes and quotes are escaped for the JSON
        string(REPLACE "\\" "\\\\" _boards_storage "$ENV{IDF_COMPONENT_LOCAL_STORAGE_URL}")
        string(REPLACE "\"" "\\\"" _boards_storage "${_boards_storage}")
        string(JSON _boards_facts SET "${_boards_facts}" "storage" "\"${_boards_storage}\"")
        string(JSON _boards_facts SET "${_boards_facts}" "radio"
               "{\"target\": \"${BOARD_RADIO_TARGET}\", \"transport\": \"${BOARD_RADIO_TRANSPORT}\", \"firmware\": \"${BOARD_RADIO_FIRMWARE}\"}")
        string(JSON _boards_facts SET "${_boards_facts}" "esp_hosted"
               "{\"dir\": \"${_boards_hosted_dir}\", \"version\": \"${_boards_hosted_version}\"}")
        string(JSON _boards_facts SET "${_boards_facts}" "host" "{\"target\": \"${IDF_TARGET}\", \"lines\": ${_boards_lines}}")
        file(WRITE "${_boards_build_dir}/board_radio.json" "${_boards_facts}\n")
        # idf.py flash names the port in ESPPORT; the ESP-IDF extension of VS Code runs this target before its own flash
        add_custom_target(board_radio
                          COMMAND "${_boards_python}" "${COMPONENT_DIR}/tools/board_radio.py" "${_boards_build_dir}/board_radio.json"
                          USES_TERMINAL VERBATIM)
        add_dependencies(flash board_radio)
    endif()
endif()
unset(_boards_components)
unset(_boards_build_dir)
unset(_boards_python)
unset(_boards_project)
unset(_boards_hosted_dir)
unset(_boards_hosted_version)
unset(_boards_chip)
unset(_boards_lines)
unset(_boards_host)
unset(_boards_count)
unset(_boards_line)
unset(_boards_board)
unset(_boards_lock)
unset(_boards_storage)
unset(_boards_facts)
