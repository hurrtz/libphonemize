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
  src/lexicon_pack.cc
)
target_include_directories(phonemize PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

add_executable(phonemize-pack src/pack_main.cc)
target_link_libraries(phonemize-pack PRIVATE phonemize)
target_include_directories(phonemize-pack PRIVATE src)

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
  target_include_directories(phonemize_smoke_test PRIVATE src)
  add_test(NAME smoke COMMAND phonemize_smoke_test)

  add_executable(phonemize_golden_test tests/golden_test.cc)
  target_link_libraries(phonemize_golden_test PRIVATE phonemize)
  target_include_directories(phonemize_golden_test PRIVATE src)

  # Regression floor against the espeak-ng oracle fixtures. Exact-match is a
  # deliberately strict proxy: the residual gap is dominated by espeak's own
  # dictionary choices diverging from CMUdict pronunciations, not by
  # notation. Raise the floor as calibration improves; never lower it.
  # Floors reflect current calibration per language; raise only.
  foreach(pair "en-us;40" "es;65" "fr;38" "de;25" "it;18")
    list(GET pair 0 lang)
    list(GET pair 1 floor)
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/tests/golden/${lang}.tsv
       AND EXISTS ${CMAKE_CURRENT_BINARY_DIR}/data/${lang}.lpk)
      add_test(NAME golden-${lang}
        COMMAND phonemize_golden_test ${CMAKE_CURRENT_BINARY_DIR}/data ${lang}
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/golden/${lang}.tsv ${floor})
    endif()
  endforeach()
endif()
