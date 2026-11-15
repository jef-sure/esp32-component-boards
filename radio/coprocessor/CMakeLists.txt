# The firmware of the radio beside the chip of a board: esp_hosted as a coprocessor, Wi-Fi and Bluetooth over the
# transport of the board. tools/board_radio.py builds it from a copy in the build directory of the program, with the
# esp_hosted the program's build took, so both sides run one version.
cmake_minimum_required(VERSION 3.22)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(board_radio_coprocessor)
