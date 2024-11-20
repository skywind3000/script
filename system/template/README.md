# Preface

The script `init.sh` inside `/etc/script` will do the following things:

- source each file inside `/etc/script/init`
- execute each file with execution privilege inside `/etc/script/run`

Call `init.sh` in your `/etc/rc.local` for convenience.


## Installation

Clone the repo into `/home/data/script` (required location):

    cd /home/data
    git clone https://github.com/skywind3000/script.git

Run installation script:

    sh /home/data/script/system/bin/script-install.sh

If `/etc/rc.local` doesn't exist, create the file with following content:

    #! /bin/sh
    sh /etc/script/init.sh

And grant the execution privilege:

    chmod 755 /etc/rc.local

If `/etc/rc.local` already exists, add this after the last line:

    sh /etc/script/init.sh

And make sure your `rc.local` file has the execution privilege.


## Update

Simply run:

    sh /etc/script/bin/script-update.sh


## Credit

TODO
