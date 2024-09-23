Set ws = CreateObject("Wscript.Shell")
ws.run "wsl -d debian -u root /etc/init.wsl start", vbhide