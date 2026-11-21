#pragma once

/* A version as one number, for the #if of the glue and the code: CMakeLists.txt defines BOARDS_VERSION_<LIBRARY> to the
 * version of that library in the build, written with this macro. */
#define BOARDS_VERSION(major, minor, patch) ((major) * 1000000L + (minor) * 1000L + (patch))
