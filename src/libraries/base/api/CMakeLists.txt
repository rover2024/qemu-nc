project(${CURRENT_LIBRARY_NAME}_api)
add_library(${PROJECT_NAME} INTERFACE)
target_include_directories(${PROJECT_NAME} INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/..)
target_compile_definitions(${PROJECT_NAME} INTERFACE CURRENT_LIBRARY_NAME="${CURRENT_LIBRARY_NAME}")