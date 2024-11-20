#! /bin/sh

# configuration
SOURCE="/home/data/script"
INSTALL="/etc/script"

# git update
cd "$SOURCE"
git pull

# update files
sh "$SOURCE/system/bin/script-install.sh"

