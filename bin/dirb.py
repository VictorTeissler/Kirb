#!/usr/bin/env python3
import sys
import argparse
import asyncio
import urllib
import time
from argparse import RawTextHelpFormatter
from kirb import Kirb
from kirb import Request

# TODO: In limited tests, this did not improve speed. Perhaps later?
#import uvloop
#asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Known bugs: Dirb-like size:x output represents request body size
# I'm actually not sure what dirb is returning the size for, probably headers
# TODO: make output more like dirb or gobuster since that seems to be the leading tool

# Implements a dirb-esque scan
class dirb_scan(object):
    def __init__(self, loop, ip, wordlist, portlist, connections = 50, ssl=False, timeout=5):
        self.loop        = loop
        self.host        = ip
        self.wordlist    = wordlist
        self.portlist    = portlist
        self.connections = connections
        self.ssl         = ssl
        self.timeout     = timeout
        self.dcheck      = []        
        self.total       = 0
        self.total_reqs  = 0
        self.start_time  = 0

    def gen_words_file(self, word_filepath):
        with open(word_filepath, 'rb') as words:
            # This mess is intended to resolve some format quirks in dirb wordlists
            for l in words.readlines():
                if l[-2:] == b'\x0d\x0a':
                    l = l[:-2]
                elif l[-1:] == b'\x0a':
                    l = l[:-1]

                l = urllib.parse.quote_from_bytes(l)
                yield l


    def gen_words_file_multi(self, word_filepaths):
        for wp in word_filepaths:
            for w in generate_words_file(wp):
                yield w


    def gen_permutations(self, ip, words, ports, ops, on_reply, on_error, ssl=False):
        for p in ports:
            for w in words:
                for op in ops:
                    if p == '':
                        continue
                    url = ip + ':' + p + '/' + w
                    self.total_reqs += 1
                    yield Request(url, op, self.on_reply, self.on_error, ssl=ssl)


    # dirb 401 verification check works by re-issuing the same request with the url suffixed with a '_' character
    # if the resulting response has a 404 error code, the 401 destination is considered valid
    # this check is implemented in the following generator (working on an array of 401 generating requests)
    def gen_dcheck_requests(self):
        for r in self.dcheck:
            r.url += '_'
            r.handler = self.reply_dcheck_handler
            yield r


    async def on_error(self, request, error):
        if type(error) == asyncio.TimeoutError:
            pass
        # TODO: prototype some kind of back-off algorithm to reduce congestion related errors
        # Should this live in kirb, be external, or some kind of mix-in object..
        elif error.errno == 111: # TCP connect failed. TODO: actually handle this
            pass
        elif error.errno == 101:
            pass
        else:
            print(str(error.errno) + ' ' + str(error))
        

    async def on_reply(self, request, reply):
        t = await reply.read()
        x = len(reply.headers)
        code = reply.status

        if code == 404: # invalid endpoint
            return

        if code == 400:
            self.print_request(request, reply, len(t))
            return
        
        if code == 401:
            self.dcheck.append(request) # catch the 401 request for dirb verification
            return
        
        if code == 200:
            self.print_request(request, reply, len(t))
            return
        
        if code == 403:
            #TODO: Special handling?
            #print('403 - look for net errors')
            #print_request(request, reply, len(t))
            return

    async def scan(self):
        ops = ['GET']
        gen_words = self.gen_words_file(wordlist)
        gen_perms = self.gen_permutations(self.host,
                                          gen_words,
                                          self.portlist,
                                          ops,
                                          self.on_reply,
                                          self.on_error,
                                          ssl=self.ssl)
    
        self.total_reqs = 0
        self.start_time = time.time()
        k = Kirb(self.loop, gen_perms, self.connections, timeout=self.timeout)
        await k.run()

        k.set_request_generator(self.gen_dcheck_requests())
        await k.run()

        self.stop_time = time.time()
        self.show_stats()
        print("Closing out connections...")
        k.stop() # terminates the aiohttp session, otherwise it'll complain

    def show_stats(self):
        rps = self.total_reqs / (self.stop_time - self.start_time)
        print("Requests per second: " + str(rps))
        print("Requests total: "      + str(self.total_reqs))
        print("200 responses: "       + str(self.total))

    async def reply_dcheck_handler(request, reply):
        t = await reply.read()
        x = reply.headers
        code = reply.status
        if code == 404:
            request.url = request.url + '/'
            print_request(request, reply, len(t), 401)

    def print_request(self, request, reply, reply_len, code = 0): # allow for code override
        t = reply.text()
        if code == 0:
            code = reply.status
        print("+ " + request.url + ' (CODE:' + str(code) + '|' + request.operation + '|SIZE:' + str(reply_len) + ')')
        self.total += 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='''
 _  ___      _
| |/ (_)_ __| |__
| ' /| | '__| '_ \ 
| . \| | |  | |_) |
|_|\_\_|_|  |_.__/ v0.1.1''',
    formatter_class=RawTextHelpFormatter)

    parser.add_argument('ip', type=str, nargs='?')
    parser.add_argument('wordlist', type=str, nargs='?')
    parser.add_argument('ports', type=str, nargs='?')
    parser.add_argument('-s', '--ssl', action='store_true', help='Negotiate SSL')
    parser.add_argument('-m', '--max', type=int, help='Max connections')
    parser.add_argument('-t', '--timeout', type=float, help='Timeout in seconds')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    if not args.ip or not args.wordlist or not args.ports:
        parser.print_help()
        sys.exit(1)

    ip = args.ip
    wordlist = args.wordlist
    ports = args.ports.split(',')

    loop = asyncio.get_event_loop()
    scanner = dirb_scan(loop, ip, wordlist, ports, ssl=args.ssl, timeout=args.timeout)
    loop.run_until_complete(scanner.scan())
    print("total: ", scanner.total)
