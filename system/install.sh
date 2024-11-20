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
chmod 755 "$INSTALL/init.sh"
cp $SOURCE/system/* "$INSTALL/lib/"

# update default init/run files
[ -d "$SOURCE/system/init" ] && cp $SOURCE/system/init/* $INSTALL/init
[ -d "$SOURCE/system/run" ] && cp $SOURCE/system/run/* $INSTALL/run

