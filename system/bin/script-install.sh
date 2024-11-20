#! /bin/sh

# configuration
SOURCE="/home/data/script/system/initscript"
INSTALL="/etc/script"
TEMPLATE="$SOURCE/template"

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
[ -d "$INSTALL/bin" ] || mkdir "$INSTALL/bin"
[ -d "$INSTALL/share" ] || mkdir "$INSTALL/share"

# update files
cat "$SOURCE/init.sh" > "$INSTALL/init.sh"
chmod 755 "$INSTALL/init.sh"
cp $SOURCE/*.sh "$INSTALL/lib/"

# update bin directory
[ -d "$SOURCE/../bin" ] && cp -r $SOURCE/../bin/* "$INSTALL/bin/"

# update default init/run files
[ -d "$TEMPLATE" ] && cp -r $TEMPLATE/* "$INSTALL"

