# No REQUIRES: see main/CMakeLists.txt of hello_board. A project of its own, with the component
# from the registry, writes PRIV_REQUIRES jef-sure__boards.
idf_component_register(SRCS "main.c")
