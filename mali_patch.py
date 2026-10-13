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

print("ALL GOOD" if ok else "PROBLEM: stop and report this output")
sys.exit(0 if ok else 1)
