FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 65532 verifier \
    && useradd --uid 65532 --gid 65532 --no-create-home --shell /usr/sbin/nologin verifier \
    && mkdir -p /opt/verifier /state \
    && chown 65532:65532 /state \
    && chmod 0700 /state

COPY authority.py manifest.json /opt/verifier/
RUN chmod 0555 /opt/verifier/authority.py \
    && chmod 0444 /opt/verifier/manifest.json

LABEL ai.recursive.verifier.authority="true" \
      ai.recursive.verifier.runtime="isolated-container-v1" \
      org.opencontainers.image.title="recursive-ai verifier authority"

USER 65532:65532
WORKDIR /tmp
VOLUME ["/state"]

ENTRYPOINT ["python", "-I", "-S", "/opt/verifier/authority.py"]
