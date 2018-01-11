Kirb is an engine that spews http requests quickly.

Dirb.py is like dirb, and is installed as a program into your path.

Installing should be as easy as: pip install git+https://github.com/coalfire/pentest-kirb.git

Argument parsing is a bit.. weird at the moment.

Example: dirb.py google.com <wordlist> 80
         dirb.py google.com <wordlist> 443 -s

Why not infer ssl and port from a url arg? Good point, I should fix that..

Some benchmarks:

Dirb.py:
(p3) [pancho@archlinux pentest-kirb]$ time dirb.py www.google.com /tmp/big.txt 443 -s -t100 -m2|grep CODE:200
+ www.google.com:443// (CODE:200|GET|SIZE:11026)
+ www.google.com:443/ (CODE:200|GET|SIZE:11047)
+ www.google.com:443/advanced_search (CODE:200|GET|SIZE:172127)
+ www.google.com:443/alerts (CODE:200|GET|SIZE:170245)
+ www.google.com:443/m (CODE:200|GET|SIZE:11052)
+ www.google.com:443/pda (CODE:200|GET|SIZE:11052)
+ www.google.com:443/preferences (CODE:200|GET|SIZE:37424)
+ www.google.com:443/shopping (CODE:200|GET|SIZE:28973)
Requests per second: 1313.863676665296
Requests total: 4217
200 responses: 12
Closing out connections...
total:  12

real	0m3.472s
user	0m2.851s
sys	0m0.092s

Dirb222:
[pancho@archlinux dirb222]$ time ./dirb https://www.google.com /tmp/big.txt -r -w -S|grep CODE:200
+ https://www.google.com// (CODE:200|SIZE:11614)
+ https://www.google.com/advanced_search (CODE:200|SIZE:172379)
+ https://www.google.com/alerts (CODE:200|SIZE:170251)
+ https://www.google.com/m (CODE:200|SIZE:11728)
+ https://www.google.com/pda (CODE:200|SIZE:11651)
+ https://www.google.com/preferences (CODE:200|SIZE:35994)
+ https://www.google.com/shopping (CODE:200|SIZE:29911)

real	0m59.130s
user	0m0.713s
sys	0m0.252s

Quick math:
59.130/3.472 = 17.03x speed improvement

TODO: This writeup
