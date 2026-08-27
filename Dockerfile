FROM python:slim

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /
RUN pip3 install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

WORKDIR /
ADD server.py /
ADD app/ /app
ADD templates/ /templates

EXPOSE 7000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7000"]
