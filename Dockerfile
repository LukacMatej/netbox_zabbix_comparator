FROM python:alpine

RUN apk update && apk upgrade && apk add --no-cache \
    python3 \
    py3-pip \
    curl && \
    apk cache clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /
RUN pip3 install -r requirements.txt

WORKDIR /
ADD poznamky.txt /
ADD server.py /
ADD app/ /app
ADD templates/ /templates

EXPOSE 7000

CMD ["python3", "./server.py", "--development"]
