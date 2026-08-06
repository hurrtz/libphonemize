#!/usr/bin/env bash
# Builds libphonemize static libraries for iOS device and simulator.
#
# Requires ORT_XCFRAMEWORK pointing at an onnxruntime.xcframework that
# contains Headers/ plus static onnxruntime.a slices (the one a
# sherpa-onnx-espeak-free iOS build downloads works directly).
#
# Produces:
#   build-ios/os64/install       (device arm64)
#   build-ios/simulator/install  (simulator arm64 + x86_64)

set -euo pipefail

: "${ORT_XCFRAMEWORK:?set ORT_XCFRAMEWORK (path to onnxruntime.xcframework)}"

build_slice() {
  local name="$1" sysroot="$2" archs="$3" ort_slice="$4"
  echo "== libphonemize ios ${name}"
  local build_dir="build-ios/${name}"
  cmake -S . -B "${build_dir}" \
    -DCMAKE_SYSTEM_NAME=iOS \
    -DCMAKE_OSX_SYSROOT="${sysroot}" \
    -DCMAKE_OSX_ARCHITECTURES="${archs}" \
    -DCMAKE_OSX_DEPLOYMENT_TARGET=13.0 \
    -DCMAKE_BUILD_TYPE=Release \
    -DPHONEMIZE_BUILD_TESTS=OFF \
    -DPHONEMIZE_ENABLE_ONNX=ON \
    -DONNXRUNTIME_INCLUDE_DIR="${ORT_XCFRAMEWORK}/Headers" \
    -DONNXRUNTIME_LIBRARY="${ORT_XCFRAMEWORK}/${ort_slice}/onnxruntime.a" \
    -DCMAKE_INSTALL_PREFIX="${build_dir}/install" > /dev/null
  cmake --build "${build_dir}" -j8 > /dev/null
  cmake --install "${build_dir}" > /dev/null
  mkdir -p "${build_dir}/install/lib"
  cp "${build_dir}/libphonemize.a" "${build_dir}/install/lib/"
  echo "   -> ${build_dir}/install/lib/libphonemize.a"
}

build_slice os64 iphoneos "arm64" ios-arm64
build_slice simulator iphonesimulator "arm64;x86_64" \
  ios-arm64_x86_64-simulator
