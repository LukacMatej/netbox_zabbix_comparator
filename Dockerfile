FROM python:3.11-bookworm

RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    python3-pip \
    curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /
RUN pip3 install -r requirements.txt 

WORKDIR /
ADD server.py /
ADD netbox-zabbix-sync-main /
ADD app/ /app
ADD templates/ /templates


RUN pip install pynetbox
RUN pip install pyzabbix


EXPOSE 7000

CMD ["python3", "./server.py", "--development"]
