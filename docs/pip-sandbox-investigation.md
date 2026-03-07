# Pip Installation Failures in Docker Sandbox

Investigation of issue #110. Conducted 2026-03-06 from inside a live sandbox.

## Summary

**pip install does not work** inside Docker Code sandboxes due to SSL certificate misconfiguration. The `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` environment variables point to the proxy's self-signed CA cert only, which lacks the real root CAs needed for HTTPS connections that bypass the proxy.

**Bazel's pip integration has the same root cause** but a different manifestation — `rules_python` runs pip in `--isolated` mode, which ignores env vars entirely, requiring a separate patching mechanism.

## Root Cause

The Docker sandbox proxy infrastructure sets these env vars:

```
SSL_CERT_FILE=/usr/local/share/ca-certificates/proxy-ca.crt
REQUESTS_CA_BUNDLE=/usr/local/share/ca-certificates/proxy-ca.crt
```

This file contains **only** the Docker Sandboxes Proxy CA certificate — a single self-signed cert. It does **not** contain the ~151 real root CAs (GlobalSign, DigiCert, Let's Encrypt, etc.) that are in the system bundle at `/etc/ssl/certs/ca-certificates.crt`.

The proxy uses **CONNECT tunnels** for most HTTPS traffic (including `files.pythonhosted.org`), meaning the real server certificates come through unmodified. Python/pip needs the real root CAs to verify these certificates, but `SSL_CERT_FILE` overrides the default CA search path to point at the proxy-only cert.

`curl` works fine because it uses a different CA resolution path that falls back to the system bundle.

### Why sandbox-init.sh doesn't fix it

`sandbox-init.sh` (line 91-93) appends the proxy CA to `/etc/ssl/certs/ca-certificates.crt`. This solves a different problem — it adds the proxy CA **to** the system bundle so Go programs (tailscale) can trust proxy-intercepted connections. But it doesn't help pip because:

1. `SSL_CERT_FILE` env var **overrides** the system bundle path entirely
2. Even if the system bundle is updated, pip's vendored certifi reads from `SSL_CERT_FILE` first

## Error Messages

### Attempt 1: Default pip install

```
$ pip install requests
error: externally-managed-environment
× This environment is externally managed
```

PEP 668 blocks system-wide pip installs. The `--break-system-packages` flag bypasses this.

### Attempt 2: pip install --break-system-packages

```
$ pip install --break-system-packages requests
SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate
```

The real error. Pip cannot verify the GlobalSign certificate chain for `files.pythonhosted.org` because `SSL_CERT_FILE` only contains the proxy CA.

### Attempt 3: pip with corrected env vars (WORKS)

```
$ SSL_CERT_FILE=/tmp/combined-ca-bundle.crt \
  REQUESTS_CA_BUNDLE=/tmp/combined-ca-bundle.crt \
  pip install --break-system-packages --no-cache-dir requests
Successfully installed certifi-2026.2.25 charset_normalizer-3.4.4 idna-3.11 requests-2.32.5 urllib3-2.6.3
```

Where `/tmp/combined-ca-bundle.crt` = system CAs + proxy CA concatenated.

### Attempt 4: Bazel pip fetch

```
$ bazel fetch @pip//...
pip._vendor.urllib3.exceptions.ReadTimeoutError: HTTPSConnectionPool(host='pypi.org', port=443): Read timed out.
```

Bazel's `rules_python` runs pip in `--isolated` mode, ignoring `SSL_CERT_FILE`. The `.bazelrc` sets `--repo_env=SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` but the system bundle doesn't contain the proxy CA either (sandbox-init.sh may not have run, or the append is lost between sessions).

## Additional Issues

### python3-venv not installed

```
$ python3 -m venv /tmp/test-venv
The virtual environment was not created successfully because ensurepip is not available.
```

`python3.13-venv` is not in the Docker image. This blocks the PEP 668 recommended workflow of using venvs.

### certifi module not installed

```python
>>> import certifi
ModuleNotFoundError: No module named 'certifi'
```

The system Python doesn't have `certifi` installed — not a blocker but means the common `certifi.where()` pattern can't be used.

## Recommended Fixes

### Fix 0: CONNECT passthrough for package registries (PRIMARY FIX — IMPLEMENTED)

Switch package registry hosts from MITM interception to CONNECT passthrough
in `sandbox/claude-proxy-bypass.sh`. This eliminates the MITM proxy from the
TLS path entirely for these hosts, so clients see real certificates and the
chunked encoding timeout issue disappears.

Bypassed hosts: `pypi.org`, `files.pythonhosted.org`, `maven.google.com`,
`repo1.maven.org`, `bcr.bazel.build`, `mirror.bazel.build`,
`objects.githubusercontent.com`, `raw.githubusercontent.com`.
(`github.com` is already bypassed in `claude.sh`.)

With CONNECT passthrough active, the combined CA bundle and `bazelrc.sandbox`
SSL overrides below become defense-in-depth rather than the primary fix.

### Fix 1: Create combined CA bundle at sandbox init (defense-in-depth)

In `sandbox-init.sh`, after step 1 (CA cert fix), create a combined bundle:

```bash
# --- Step 1c: Combined CA bundle for pip/Python ---
COMBINED_CA="/etc/ssl/certs/combined-ca-bundle.crt"
if [[ -f "$PROXY_CA" && ! -f "$COMBINED_CA" ]]; then
    echo "Creating combined CA bundle for pip..."
    sudo bash -c "cat '$CA_BUNDLE' '$PROXY_CA' > '$COMBINED_CA'"
    echo "Combined CA bundle created at $COMBINED_CA"
fi
```

Then update the env vars in the sandbox persistent environment:

```bash
echo "export SSL_CERT_FILE=$COMBINED_CA" >> /etc/sandbox-persistent.sh
echo "export REQUESTS_CA_BUNDLE=$COMBINED_CA" >> /etc/sandbox-persistent.sh
```

### Fix 2: Update bazelrc.sandbox

Change `bazelrc.sandbox` to reference the combined bundle:

```
common --repo_env=REQUESTS_CA_BUNDLE=/etc/ssl/certs/combined-ca-bundle.crt
common --repo_env=SSL_CERT_FILE=/etc/ssl/certs/combined-ca-bundle.crt
common --repo_env=CURL_CA_BUNDLE=/etc/ssl/certs/combined-ca-bundle.crt
```

### Fix 3: Install python3-venv in Dockerfile

Add to `sandbox/Dockerfile` or `sandbox/claude-sandbox/Dockerfile.base`:

```dockerfile
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    python3-venv python3.13-venv \
    && rm -rf /var/lib/apt/lists/*
```

### Fix 4: Add --break-system-packages to pip config (optional)

If venvs are not desired, create a pip config during image build:

```dockerfile
RUN mkdir -p /home/agent/.config/pip && \
    printf '[global]\nbreak-system-packages = true\n' > /home/agent/.config/pip/pip.conf && \
    chown -R agent:agent /home/agent/.config/pip
```

### Fix 5: Patch Bazel hermetic certifi (already partially implemented)

`sandbox-init.sh` already has a `patch-certifi.sh` script (lines 123-142) that appends the proxy CA to Bazel's hermetic certifi bundles. This should work **after** the first `bazel build` creates the cache, but needs the combined bundle fix to work for the initial pip fetch within rules_python.

## Bazel pip vs Regular pip

| Aspect | Regular pip | Bazel pip (rules_python) |
|--------|------------|------------------------|
| Binary | `/usr/bin/pip` (system) | Hermetic Python 3.12 in Bazel cache |
| CA source | `SSL_CERT_FILE` env var → proxy-only cert | `--repo_env=SSL_CERT_FILE` → system bundle (no proxy CA) |
| Isolation | Respects env vars | `--isolated` mode ignores most env vars |
| Fix needed | Combined CA bundle in `SSL_CERT_FILE` | Combined CA bundle in `--repo_env` + certifi patching |
| Root cause | Same: proxy CA not combined with real root CAs |

## Files to Modify

| File | Change |
|------|--------|
| `sandbox/claude-sandbox/sandbox-init.sh` | Add step 1c to create combined CA bundle + update env vars |
| `sandbox/bazelrc.sandbox` | Point `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` at combined bundle |
| `sandbox/claude-sandbox/Dockerfile.base` or `sandbox/Dockerfile` | Install `python3-venv` |

## Verification

After applying fixes, these should all succeed:

```bash
# Regular pip
pip install --break-system-packages requests

# Virtual env pip
python3 -m venv /tmp/test && /tmp/test/bin/pip install requests

# Bazel pip
bazel fetch @pip//...

# Bazel build with Python deps
bazel build //mcp/...
```
