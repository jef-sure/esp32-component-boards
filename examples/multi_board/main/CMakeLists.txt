# No REQUIRES: main depends on every component of the build, the boards among them, as ESP-IDF's main does.
idf_component_register(SRCS "main.c")
