#! /bin/sh

# configuration
SOURCE="/home/data/script/system"
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
[ -d "$INSTALL/bin" ] || mkdir "$INSTALL/bin"
[ -d "$INSTALL/share" ] || mkdir "$INSTALL/share"

# update files
cp -r $SOURCE/template/* "$INSTALL/" 
chmod 755 "$INSTALL/init.sh" 2> /dev/null

# update bin/lib directory
[ -d "$SOURCE/bin" ] && cp -r $SOURCE/bin/* "$INSTALL/bin/"
[ -d "$SOURCE/lib" ] && cp -r $SOURCE/lib/* "$INSTALL/lib/"


