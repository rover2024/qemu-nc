project(${CURRENT_LIBRARY_NAME}_host_bridge)

file(GLOB _src *.h *.c *.cpp)
add_library(${PROJECT_NAME} SHARED ${_src})

target_include_directories(
    ${PROJECT_NAME} PUBLIC "$<BUILD_INTERFACE:${X64NC_SOURCE_DIR}/include>"
    ${PROJECT_NAME} PRIVATE "${X64NC_SOURCE_DIR}/include/x64nc"
)

target_link_libraries(${PROJECT_NAME} PUBLIC ${CURRENT_LIBRARY_NAME}_api)
target_link_libraries(${PROJECT_NAME} PRIVATE dl)

target_compile_features(${PROJECT_NAME} PUBLIC cxx_std_17)