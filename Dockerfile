FROM python:bookworm

RUN apt update && apt install -y \
    python3-pip \
    curl

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

CMD python3 ./server.py --development
