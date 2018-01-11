Kirb is an engine that spews http requests quickly.

Dirb.py is like dirb, and is installed as a program into your path.

Installing should be as easy as: pip install git+https://github.com/coalfire/pentest-kirb.git

Argument parsing is a bit.. weird at the moment.

Example: dirb.py google.com <wordlist> 80
         dirb.py google.com <wordlist> 443 -s

Why not infer ssl and port from a url arg? Good point, I should fix that..

TODO: This writeup
