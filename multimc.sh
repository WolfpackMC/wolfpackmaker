#!/bin/bash

DESKTOP=$XDG_CURRENT_DESKTOP

cd $INST_DIR


cmd="-e sh src/wolfpackmaker.sh $@ -d .minecraft/mods"

echo $cmd


if [ $DESKTOP == "KDE" ];
then
    konsole $cmd
elif [ $DESKTOP == "GNOME" ];
then
    gnome-terminal $cmd
else
    xterm $cmd
fi

