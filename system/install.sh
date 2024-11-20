#! /bin/sh

# configuration
SOURCE="/home/data/script"
INSTALL="/etc/script"

# create directory
if [ ! -d "$INSTALL" ]; then
	USER_NAME="$(whoami)"
	sudo mkdir -p "$INSTALL"
	sudo chown -R "$USER_NAME" "$INSTALL"
fi

# create sub directory
[ -d "$INSTALL/init" ] || mkdir "$INSTALL/init"
[ -d "$INSTALL/run" ] || mkdir "$INSTALL/run"
[ -d "$INSTALL/lib" ] || mkdir "$INSTALL/lib"

# update files
cat "$SOURCE/system/init.sh" > "$INSTALL/init.sh"
cp "$SOURCE/system/*" "$INSTALL/"

