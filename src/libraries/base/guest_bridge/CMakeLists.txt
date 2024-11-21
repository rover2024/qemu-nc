project(${CURRENT_LIBRARY_NAME}_guest_bridge)

file(GLOB _src *.h *.c *.cpp)
add_library(${PROJECT_NAME} SHARED ${_src})

target_link_libraries(${PROJECT_NAME} PUBLIC ${CURRENT_LIBRARY_NAME}_api)
target_link_libraries(${PROJECT_NAME} PRIVATE x64nc-guestrt dl)

target_compile_features(${PROJECT_NAME} PUBLIC cxx_std_17)