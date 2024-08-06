project(loaderapi)

file(GLOB _src *.c *.cpp)
add_library(${PROJECT_NAME} STATIC ${_src})

target_include_directories(
    ${PROJECT_NAME} PUBLIC "$<BUILD_INTERFACE:${X64NC_SOURCE_DIR}/include>"
    ${PROJECT_NAME} PRIVATE "${X64NC_SOURCE_DIR}/include/x64nc"
)