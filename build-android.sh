#!/usr/bin/env bash
# Cross-compiles libphonemize for Android.
#
# Requires:
#   ANDROID_NDK   – NDK root
#   ORT_DIR       – directory containing headers/ (onnxruntime_cxx_api.h)
#                   and jni/<abi>/libonnxruntime.so, e.g. the `1.23.2/`
#                   directory a sherpa-onnx Android build downloads.
#
# Produces build-android/<abi>/install/{lib/libphonemize.a,include/phonemize.h}

set -euo pipefail

: "${ANDROID_NDK:?set ANDROID_NDK}"
: "${ORT_DIR:?set ORT_DIR (sherpa onnxruntime download dir)}"

ABIS=(arm64-v8a armeabi-v7a x86_64 x86)

for abi in "${ABIS[@]}"; do
  echo "== libphonemize android ${abi}"
  build_dir="build-android/${abi}"
  cmake -S . -B "${build_dir}" \
    -DCMAKE_TOOLCHAIN_FILE="${ANDROID_NDK}/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI="${abi}" \
    -DANDROID_PLATFORM=android-24 \
    -DCMAKE_BUILD_TYPE=Release \
    -DPHONEMIZE_BUILD_TESTS=OFF \
    -DPHONEMIZE_ENABLE_ONNX=ON \
    -DONNXRUNTIME_INCLUDE_DIR="${ORT_DIR}/headers" \
    -DONNXRUNTIME_LIBRARY="${ORT_DIR}/jni/${abi}/libonnxruntime.so" \
    -DCMAKE_INSTALL_PREFIX="${build_dir}/install" > /dev/null
  cmake --build "${build_dir}" -j8 > /dev/null
  cmake --install "${build_dir}" > /dev/null
  mkdir -p "${build_dir}/install/lib"
  cp "${build_dir}/libphonemize.a" "${build_dir}/install/lib/"
  echo "   -> ${build_dir}/install/lib/libphonemize.a"
done
