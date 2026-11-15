# The program that brings the radio beside the chip to the firmware of the program's esp_hosted: it stands for a
# moment in the place of the program's app, says the version the radio runs and passes an image from USB to it.
# tools/board_radio.py builds it from a copy in the build directory, with the chip settings of the program's build.
cmake_minimum_required(VERSION 3.22)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(board_radio_updater)
