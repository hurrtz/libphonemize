cmake_minimum_required(VERSION 3.20)
project(libphonemize VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(PHONEMIZE_BUILD_TESTS "Build unit and golden-fixture tests" ON)
# The neural fallback needs onnxruntime; lexicon+rules work without it so the
# library stays usable in minimal embeddings.
option(PHONEMIZE_ENABLE_ONNX "Enable the ONNX neural G2P fallback layer" OFF)

add_library(phonemize
  src/phonemize.cc
)
target_include_directories(phonemize PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

if(PHONEMIZE_ENABLE_ONNX)
  find_package(onnxruntime REQUIRED)
  target_link_libraries(phonemize PRIVATE onnxruntime::onnxruntime)
  target_compile_definitions(phonemize PRIVATE PHONEMIZE_HAVE_ONNX=1)
endif()

install(TARGETS phonemize)
install(FILES include/phonemize.h DESTINATION include)

if(PHONEMIZE_BUILD_TESTS)
  enable_testing()
  add_executable(phonemize_smoke_test tests/smoke_test.cc)
  target_link_libraries(phonemize_smoke_test PRIVATE phonemize)
  add_test(NAME smoke COMMAND phonemize_smoke_test)
endif()
