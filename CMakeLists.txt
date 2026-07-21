cmake_minimum_required(VERSION 3.20)

project(SearchEngine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_library(STEMMER_LIB NAMES stemmer libstemmer)

if(NOT STEMMER_LIB)
    message(FATAL_ERROR "libstemmer could not be found! please install libstemmer-dev.")
endif()
add_executable(search_engine
    src/main.cpp
    src/parser.cpp
    src/tokenizer.cpp
    src/index.cpp
    src/stemmer.cpp
)

target_include_directories(search_engine
    PRIVATE
        ${PROJECT_SOURCE_DIR}/include
)

target_link_libraries(search_engine 
    PRIVATE 
        ${STEMMER_LIB}
        )