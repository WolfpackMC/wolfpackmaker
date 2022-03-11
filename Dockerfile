FROM archlinux:base-devel

COPY requirements.txt /requirements.txt

RUN pacman -Sy --noconfirm git zip python3

RUN python3 -m ensurepip

WORKDIR /

RUN python3 -m pip install -r requirements.txt

