cmake_minimum_required(VERSION 3.20)

project(SearchEngine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(search_engine
    src/main.cpp
    src/parser.cpp
    src/tokenizer.cpp
    src/index.cpp
)

target_include_directories(search_engine
    PRIVATE
        ${PROJECT_SOURCE_DIR}/include
)