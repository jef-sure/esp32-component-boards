# The program asks the component for its board by kind; what the board needs (DGX, DGX-DI, a
# touch driver, a codec) the component brings by the rules of its manifest and links itself.
#
# No REQUIRES here: the example takes the component by its directory (EXTRA_COMPONENT_DIRS), so
# its name in the build is the directory's, whatever the checkout is called; main names nothing
# and depends on every component of the build, as ESP-IDF's main does when it names none. A
# project of its own, with the component from the registry (managed_components/jef-sure__boards),
# writes PRIV_REQUIRES jef-sure__boards.
idf_component_register(SRCS "main.c")
