# Project-specific sandbox image — extends the generic base.
FROM claude-sandbox-base:latest

USER root

# Build toolchain (gcc/g++ needed for native Bazel deps)
# python3-venv enables PEP 668 venvs for pip installs without --break-system-packages
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    gcc g++ python3-venv \
    && rm -rf /var/lib/apt/lists/*

# x86_64 emulation for Android SDK build-tools (aapt2) and platform-tools (adb).
# Google does not publish Linux aarch64 SDK packages; the x86_64 binaries run
# under QEMU user-mode emulation with the amd64 dynamic linker and libc.
RUN dpkg --add-architecture amd64 \
    && printf 'Types: deb\nURIs: http://archive.ubuntu.com/ubuntu/\nSuites: questing questing-updates questing-security\nComponents: main universe\nArchitectures: amd64\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n' \
       > /etc/apt/sources.list.d/amd64.sources \
    && sed -i '/^Signed-By:/a Architectures: arm64' /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends \
       qemu-user-static libc6:amd64 libstdc++6:amd64 zlib1g:amd64 \
    && rm -rf /var/lib/apt/lists/*

# Bazelisk
RUN curl -fsSL -o /usr/local/bin/bazelisk \
    https://github.com/bazelbuild/bazelisk/releases/download/v1.25.0/bazelisk-linux-arm64 \
    && chmod +x /usr/local/bin/bazelisk \
    && ln -sf /usr/local/bin/bazelisk /usr/local/bin/bazel

# Android SDK
ENV ANDROID_HOME=/opt/android-sdk
ENV PATH=${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${PATH}

RUN mkdir -p ${ANDROID_HOME}/cmdline-tools \
    && cd ${ANDROID_HOME}/cmdline-tools \
    && curl -fsSL https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip \
       -o cmdline-tools.zip \
    && unzip -q cmdline-tools.zip \
    && mv cmdline-tools latest \
    && rm cmdline-tools.zip

RUN mkdir -p ${ANDROID_HOME}/licenses \
    && echo -e "\n24333f8a63b6825ea9c5514f83c2829b004d1fee" > ${ANDROID_HOME}/licenses/android-sdk-license \
    && echo -e "\nd975f751698a77e662f1cd25de68a5e9b2075571" >> ${ANDROID_HOME}/licenses/android-sdk-license \
    && echo -e "\n84831b9409646a918e30573bab4c9c91346d8abd" > ${ANDROID_HOME}/licenses/android-sdk-preview-license

# Keep API level in sync with CI runner (rules_android auto-detects from installed SDK).
RUN sdkmanager "platform-tools" "platforms;android-36" "build-tools;36.0.0"

RUN chown -R agent:agent ${ANDROID_HOME}

# Verify SDK tools are executable (catches architecture mismatches early)
RUN ${ANDROID_HOME}/build-tools/36.0.0/aapt2 version \
    && ${ANDROID_HOME}/platform-tools/adb version

# Pre-built instance manager client.
# Build on the host first: bazel build //instance_manager:instance_manager_client_zip
# Then copy: cp bazel-bin/instance_manager/instance_manager_client.zip sandbox/
COPY instance_manager_client.zip /opt/vanpilot/instance_manager_client.zip
RUN printf '#!/bin/bash\nexec python3 /opt/vanpilot/instance_manager_client.zip "$@"\n' \
    > /usr/local/bin/im && chmod +x /usr/local/bin/im

# Runtime init script — imports proxy CA into JDK/Bazel truststores.
# Must run at sandbox start (not image build) because the proxy CA cert
# is injected by the sandbox infrastructure after container creation.
COPY project-init.sh /usr/local/bin/project-init.sh
RUN chmod +x /usr/local/bin/project-init.sh

USER agent

# Bazel proxy CA trust (directory only — populated at runtime by project-init.sh)
RUN mkdir -p /home/agent/.bazel-ssl
COPY bazelrc.sandbox /home/agent/.bazelrc
