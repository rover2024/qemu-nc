project(x64nc-hostrt)

file(GLOB _src *.c *.cpp)
add_library(${PROJECT_NAME} SHARED ${_src})

target_include_directories(${PROJECT_NAME} PUBLIC "$<BUILD_INTERFACE:${X64NC_SOURCE_DIR}/include>")
target_include_directories(${PROJECT_NAME} PRIVATE "${X64NC_SOURCE_DIR}/include/x64nc")

target_compile_definitions(${PROJECT_NAME} PRIVATE X64NC_LIBRARY)
target_compile_options(${PROJECT_NAME} PRIVATE -fno-stack-protector -fPIC)
target_link_libraries(${PROJECT_NAME} PRIVATE pthread dl)
target_link_options(${PROJECT_NAME} PRIVATE -Wl,-z,defs)

target_compile_features(${PROJECT_NAME} PUBLIC cxx_std_17)

if (X64NC_INSTALL)
    target_include_directories(${PROJECT_NAME} PUBLIC "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")
    install(TARGETS ${PROJECT_NAME}
        EXPORT ${X64NC_INSTALL_NAME}Targets
        RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}" OPTIONAL
        LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}" OPTIONAL
        ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}" OPTIONAL
    )
endif()