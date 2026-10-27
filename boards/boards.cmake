# The boards and the modules the component has glue for, made by tools/boards_gen.py --all
# from boards-data/: CMakeLists.txt compiles the chosen board's glue (CONFIG_BOARD_<BOARD>)
# and every module turned on (CONFIG_BOARD_MODULE_<MODULE>). Do not edit by hand.
set(BOARDS_LIST cyd jc1060p470 jc4827w543 jc8012p4a1c)
set(BOARDS_MODULES lcd2004_pcf8574)
