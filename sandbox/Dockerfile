# Project-specific sandbox image — extends the generic base.
FROM claude-sandbox-base:latest

USER root

# Build toolchain (gcc/g++ needed for native Bazel deps)
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    gcc g++ \
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

USER agent

# Bazel proxy CA trust
RUN mkdir -p /home/agent/.bazel-ssl
COPY bazelrc.sandbox /home/agent/.bazelrc
