# https://mitsuba.readthedocs.io/en/latest/src/developer_guide/compiling.html
# syntax=docker/dockerfile:1

############################
# Builder
############################
FROM ubuntu:24.04 AS builder

ARG DEBIAN_FRONTEND=noninteractive

# cpu: scalar_rgb + llvm_ad_rgb (base)
# gpu: scalar_rgb + cuda_ad_rgb (base)
ARG MI_PRESET=cpu

# Add extra variants (space or comma separated). Examples:
#   --build-arg MI_EXTRA_VARIANTS="scalar_spectral llvm_ad_spectral"
#   --build-arg MI_EXTRA_VARIANTS="scalar_spectral,llvm_ad_spectral"
ARG MI_EXTRA_VARIANTS=""

ARG MI_NINJA_JOBS=2
ENV MI_NINJA_JOBS=${MI_NINJA_JOBS}

ENV MI_PRESET=${MI_PRESET}
ENV MI_EXTRA_VARIANTS=${MI_EXTRA_VARIANTS}

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates \
    clang-17 cmake ninja-build \
    libpng-dev libjpeg-dev \
    python3 python3-pip python3-setuptools \
    libpython3-dev \
    && rm -rf /var/lib/apt/lists/*

ENV CC=clang-17
ENV CXX=clang++-17

SHELL ["/bin/bash", "-c"]

WORKDIR /opt
RUN git clone -b v3.7.0 --recursive https://github.com/mitsuba-renderer/mitsuba3

WORKDIR /opt/mitsuba3

RUN <<'BASH'
set -euo pipefail

mkdir -p build
cd build
cmake -GNinja -DPython_EXECUTABLE=/usr/bin/python3 ..

python3 - <<'PY'
import os, re, pathlib, json

preset = os.environ.get("MI_PRESET", "cpu").strip().lower()
extra_raw = os.environ.get("MI_EXTRA_VARIANTS", "").strip()

if preset not in ("cpu", "gpu"):
    raise SystemExit(f"[ERROR] Unknown MI_PRESET={preset!r}. Use cpu or gpu.")

base_required = ["scalar_rgb"]
base_ad = "llvm_ad_rgb" if preset == "cpu" else "cuda_ad_rgb"
base = base_required + [base_ad]
python_default = base_ad

extras = []
if extra_raw:
    tokens = extra_raw.replace(",", " ").split()
    extras = [t.strip() for t in tokens if t.strip()]

if preset == "cpu":
    cuda_like = [v for v in extras if v.startswith("cuda")]
    if cuda_like:
        raise SystemExit(
            "[ERROR] MI_PRESET=cpu does not allow cuda_* variants. "
            f"Remove: {cuda_like} or build with --build-arg MI_PRESET=gpu."
        )

enabled_list = []
for v in (base + extras):
    if v not in enabled_list:
        enabled_list.append(v)

if len(enabled_list) > 5:
    raise SystemExit(
        "[ERROR] Too many enabled variants. Limit is 5 total (base + extras).\n"
        f"  preset={preset}\n"
        f"  base={base}\n"
        f"  extras={extras}\n"
        f"  enabled_count={len(enabled_list)}\n"
        f"  enabled={enabled_list}\n"
        "Reduce MI_EXTRA_VARIANTS so that enabled_count <= 5."
    )

p = pathlib.Path("mitsuba.conf")
s = p.read_text(encoding="utf-8")

enabled_block = '"enabled": [\n        ' + ", ".join([f'"{v}"' for v in enabled_list]) + '\n    ]'
s = re.sub(r'"enabled"\s*:\s*\[[^\]]*\]', enabled_block, s, count=1, flags=re.S)

s = re.sub(r'"python-default"\s*:\s*"[^"]+"', f'"python-default": "{python_default}"', s, count=1)

p.write_text(s, encoding="utf-8")
print("[OK] preset:", preset)
print("[OK] enabled variants:", enabled_list)
print("[OK] python-default:", python_default)
PY

ninja -j "${MI_NINJA_JOBS}"
BASH

############################
# Runtime
############################
FROM ubuntu:24.04 AS runtime

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    python3 python-is-python3 \
    libpng16-16 libjpeg-turbo8 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/mitsuba3 /opt/mitsuba3

RUN <<'BASH'
set -eu

cat > /usr/local/bin/mitsuba-env <<'SH'
#!/usr/bin/env bash
set -euo pipefail

# set -u 対策：未定義の環境変数を空として扱う
export PYTHONPATH="${PYTHONPATH:-}"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
export PATH="${PATH:-}"

if [ -f /opt/mitsuba3/build/setpath.sh ]; then
  # shellcheck disable=SC1091
  source /opt/mitsuba3/build/setpath.sh
fi

exec "$@"
SH

chmod +x /usr/local/bin/mitsuba-env
BASH

RUN <<'BASH'
set -eu

cat >> /etc/bash.bashrc <<'RC'

# Mitsuba 3: enable environment automatically for interactive shells.
if [ -f /opt/mitsuba3/build/setpath.sh ]; then
  export PYTHONPATH="${PYTHONPATH:-}"
  export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
  # suppress noise; don't fail the shell if setpath has a minor issue
  source /opt/mitsuba3/build/setpath.sh >/dev/null 2>&1 || true
fi
RC
BASH

ENTRYPOINT ["/usr/local/bin/mitsuba-env"]
CMD ["bash"]
