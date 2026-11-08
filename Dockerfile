FROM python:3.9-alpine

LABEL Maintainer="danielgoepp"
LABEL org.opencontainers.image.source="https://github.com/danielgoepp/propane-sync"

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY ./vm_propane_sync.py .

CMD [ "python", "./vm_propane_sync.py" ]