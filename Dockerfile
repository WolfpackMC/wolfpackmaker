FROM archlinux

COPY requirements.txt /requirements.txt

RUN pacman -Sy --noconfirm python3 git

RUN python3 -m ensurepip

RUN python3 -m pip install -r requirements.txt

