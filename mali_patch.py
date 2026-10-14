import re, pathlib, sys

root = pathlib.Path("node_modules/llama.rn")
ok = True

# --- Edit 1: CMake. Stop forcing Adreno-only kernels.
cm = root / "android/src/main/rnllama/CMakeLists.txt"
t = cm.read_text()
t2, n = re.subn(r"^[ \t]*-DGGML_OPENCL_USE_ADRENO_KERNELS[ \t]*\n", "", t, flags=re.M)
print("edit1 cmake lines removed:", n)
if n != 1:
    ok = False
cm.write_text(t2)

# --- Edit 2: C++. Let Mali GPUs pass the device check (use the generic path).
cpp = root / "vendor/llama.cpp/ggml/src/ggml-opencl/ggml-opencl.cpp"
t = cpp.read_text()
old = '} else if (strstr(dev_ctx->device_name.c_str(), "Intel")) {'
new = ('} else if (strstr(dev_ctx->device_name.c_str(), "Intel") ||\n'
       '               strstr(dev_ctx->device_name.c_str(), "Mali")) {')
n = t.count(old)
print("edit2 cpp matches:", n)
if n != 1:
    ok = False
cpp.write_text(t.replace(old, new))

# --- Edit 3: OpenCL kernels. Add a fallback for GPUs that have
# neither the Intel nor the Qualcomm subgroup extension (Mali).
prelude = (
    "#if !defined(cl_intel_required_subgroup_size) && "
    "!defined(cl_qcom_reqd_sub_group_size)\n"
    "#define INTEL_GPU 1\n"
    "#define REQD_SUBGROUP_SIZE_16\n"
    "#define REQD_SUBGROUP_SIZE_32\n"
    "#define REQD_SUBGROUP_SIZE_64\n"
    "#define REQD_SUBGROUP_SIZE_128\n"
    "#endif\n"
)
count = 0
for f in (root / "vendor/llama.cpp/ggml/src/ggml-opencl/kernels").glob("*.cl"):
    s = f.read_text()
    if "cl_intel_required_subgroup_size" in s and "MALI_PRELUDE" not in s:
        f.write_text("// MALI_PRELUDE\n" + prelude + s)
        count += 1
print("edit3 kernel files patched:", count)
if count < 50:
    ok = False

# --- Edit 4: App (TypeScript). Stop the app from hiding the GPU option
# when the phone has no Adreno GPU.
ts = pathlib.Path("src/utils/deviceCapabilities.ts")
t = ts.read_text()
old = "const hasAdreno = gpuInfo.hasAdreno ?? false;"
n = t.count(old)
print("edit4 ts matches:", n)
if n != 1:
    ok = False
ts.write_text(t.replace(old, "const hasAdreno = true; // Mali experiment"))

# --- Edit 5: Java loader. llama.rn only loads the OpenCL native library on
# Snapdragon phones. Make it load on any phone with dotprod + i8mm.
jv = root / "android/src/main/java/com/rnllama/RNLlama.java"
t = jv.read_text()
old = "if (hasDotProd && hasI8mm && hasHexagon && hasAdreno) {"
n = t.count(old)
print("edit5 java matches:", n)
if n != 1:
    ok = False
jv.write_text(t.replace(old, "if (hasDotProd && hasI8mm) {"))

# --- Edit 6: App (TypeScript). Device list: add Auto + always show GPU.
ds = pathlib.Path("src/utils/deviceSelection.ts")
t = ds.read_text()

# 6a: new optional field on the option type
old = "  experimental?: boolean;\n"
n = t.count(old)
print("edit6a matches:", n)
if n != 1:
    ok = False
t = t.replace(old, old + "  disabled?: boolean;\n")

# 6b: add an Auto option before the CPU option (Android only part)
old = "  // Option 1: CPU (always available, recommended for reliability)\n"
n = t.count(old)
print("edit6b matches:", n)
if n != 1:
    ok = False
auto_opt = (
    "  // Mali experiment: Auto lets llama.cpp choose the device\n"
    "  options.push({\n"
    "    id: 'auto',\n"
    "    label: 'Auto',\n"
    "    description: 'Let llama.cpp pick the device (GPU if available)',\n"
    "    devices: undefined,\n"
    "    n_gpu_layers: 99,\n"
    "    default_flash_attn_type: 'off',\n"
    "    valid_flash_attn_types: ['off'],\n"
    "    platform: 'android',\n"
    "  });\n\n"
)
t = t.replace(old, auto_opt + old)

# 6c: always show a GPU button (greyed out if no GPU was detected)
old = "      deviceInfo: gpuDev,\n    });\n  }\n"
n = t.count(old)
print("edit6c matches:", n)
if n != 1:
    ok = False
new = (
    "      deviceInfo: gpuDev,\n    });\n  } else {\n"
    "    options.push({\n"
    "      id: 'gpu',\n"
    "      label: 'GPU (n/a)',\n"
    "      description: 'No GPU backend was detected on this phone',\n"
    "      devices: undefined,\n"
    "      n_gpu_layers: 99,\n"
    "      default_flash_attn_type: 'off',\n"
    "      valid_flash_attn_types: ['off'],\n"
    "      platform: 'android',\n"
    "      disabled: true,\n"
    "    });\n"
    "  }\n"
)
t = t.replace(old, new)
ds.write_text(t)

# --- Edit 7: App (TypeScript). Settings screen: show Auto, set GPU layers.
ss = pathlib.Path("src/screens/SettingsScreen/SettingsScreen.tsx")
t = ss.read_text()

# 7a: tell Android apart: no devices = Auto, CPU = CPU
old = (
    "    if (!devices || devices.length === 0 || devices[0] === 'CPU') {\n"
    "      return 'cpu';\n"
    "    }\n"
)
n = t.count(old)
print("edit7a matches:", n)
if n != 1:
    ok = False
new = (
    "    if (!devices || devices.length === 0) {\n"
    "      return 'auto';\n"
    "    }\n"
    "    if (devices[0] === 'CPU') {\n"
    "      return 'cpu';\n"
    "    }\n"
)
t = t.replace(old, new)

# 7b: when a device button is tapped on Android, also set GPU layers
old = "    modelStore.setDevices(option.devices);\n"
n = t.count(old)
print("edit7b matches:", n)
if n != 1:
    ok = False
t = t.replace(old, old +
    "    if (Platform.OS === 'android') {\n"
    "      modelStore.setNGPULayers(option.n_gpu_layers);\n"
    "    }\n")

# 7c: let a button be greyed out
old = "                        testID: `device-option-${option.id}`,\n"
n = t.count(old)
print("edit7c matches:", n)
if n != 1:
    ok = False
t = t.replace(old, old + "                        disabled: option.disabled,\n")
ss.write_text(t)

print("ALL GOOD" if ok else "PROBLEM: stop and report this output")
sys.exit(0 if ok else 1)
