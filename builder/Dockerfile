FROM python:3.12-slim

RUN pip install --no-cache-dir pyyaml

COPY build.sh /build/build.sh
RUN chmod +x /build/build.sh

ENTRYPOINT ["/build/build.sh"]
