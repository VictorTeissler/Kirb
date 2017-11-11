import sys
import asyncio
import aiohttp
import functools
import async_timeout
import argparse
from argparse import RawTextHelpFormatter

# Known bugs: Dirb-like size:x output represents request body size
# I'm actually not sure what dirb is returning the size for, probably headers
# TODO: make output more like dirb or gobuster since that seems to be the leading tool
# TODO: Support changing user agents
# TODO: Add basic auth
# TODO: !!! Handle retries
class request(object):
    def __init__(self, url, operation, on_reply, on_error = False, ssl = False, data = []):
        self.url       = url
        self.ssl       = ssl
        self.data      = data
        self.tries     = 0 # For future retry functionality
        self.operation = operation
        self.on_reply  = on_reply
        self.on_error  = on_error


class kirb(object):
    def __init__(self, loop, generator, max_con = 20, timeout = 5):
        self.loop      = loop
        self.timeout   = timeout
        self.retries   = []
        self.session   = aiohttp.ClientSession(loop=loop)
        self.generator = generator
        self.semaphore = asyncio.Semaphore(max_con, loop=loop)
        self.opcalls   = { 'HEAD'   : self.session.head,
                           'GET'    : self.session.get,
                           'PUT'    : self.session.put,
                           'POST'   : self.session.post,
                           'DELETE' : self.session.delete }


    def set_request_generator(self, gen):
        self.generator = gen


    def set_timeout(self, timeout):
        self.timeout = timeout


    def get_cookies(self):
        pass # TODO: return current session cookies


    def set_cookies(self):
        pass # TODO: set or clear current session cookies


    # Opcalls dictionary seemed like a good idea at first.. TODO: changeme?
    async def timed_op(self, request):
        try:
            with async_timeout.timeout(self.timeout, loop=self.session.loop):
                request.tries += 1

                if request.ssl == False:
                    url = 'http://' + request.url
                elif request.ssl == True:
                    url = 'https://' + request.url

                if len(request.data) > 0:
                    reply = await self.opcalls[request.operation](url, data=request.data)
                else:
                    reply = await self.opcalls[request.operation](url)

                await self._on_reply(request, reply)
                #await reply.read()

        except aiohttp.errors.ClientOSError as e:
            if self._on_error != False:
                await self.on_error(request, e)

        except asyncio.TimeoutError as e:
        #    await self.on_error(request, e)
            pass # Need to make exception parsing easier on lib users

        self.semaphore.release()


    async def _on_reply(self, request, reply):
        await request.on_reply(request, reply)


    async def _on_error(self, request, error):
        await request.on_error(request, error)


    async def run(self):
        futures = []
        for r in self.generator:
            futures = [f for f in futures if f.done() == False]

            await self.semaphore.acquire()
            futures.append(asyncio.ensure_future(self.timed_op(r)))

        await asyncio.gather(*futures) # wait for remaining futures to finish


    def stop(self):
        self.session.close()

# Implements a dirb-esque scan
def dirb_rest_scan(ip, wordlist, portlist, connections = 50, ssl=False):
    import urllib
    # catches 401 code generating requests, this is for dirb checks explained later on
    dcheck = []

    def gen_words_file(word_filepath):
        with open(word_filepath, 'rb') as words:
            for l in words.readlines():
                l = urllib.parse.unquote(l.decode('utf8'))
                yield l[:-1]


    def gen_words_file_multi(word_filepaths):
        for wp in word_filepaths:
            for w in generate_words_file(wp):
                yield w


    def gen_permutations(ip, words, ports, ops, on_reply, on_error, ssl=False):
        for p in ports:
            for w in words:
                if w == '':
                    continue
                elif w[0] == '/': # we add a slash
                    w = w[1:]

                for op in ops:
                    if p == '':
                        continue
                    url = ip + ':' + p + '/' + w
                    yield request(url, op, on_reply, on_error, ssl=ssl)


    def print_request(request, reply, reply_len, code = 0): # allow for code override
        t = reply.text()
        if code == 0:
            code = reply.status
        print("+ " + request.url + ' (CODE:' + str(code) + '|' + request.operation + '|SIZE:' + str(reply_len) + ')')


    async def on_error(request, error):
        # TODO: prototype some kind of back-off algorithm to reduce congestion related errors
        # Should this live in kirb, be external, or some kind of mix-in object..
        if error.errno != 111: # TCP connect failed. TODO: actually handle this
            print(error)


    async def on_reply(request, reply):
        t = await reply.read()
        x = len(reply.headers)
        code = reply.status

        if code == 404: # invalid endpoint
            return

        if code == 400:
            print_request(request, reply, len(t))
            return
        
        if code == 401:
            dcheck.append(request) # catch the 401 request for dirb verification
            return
        
        if code == 200:
            print_request(request, reply, len(t))
            return
        
        if code == 403:
            #TODO: Special handling?
            #print('403 - look for net errors')
            #print_request(request, reply, len(t))
            return

    # TODO: Make this command line configurable
    # uncomment and use this list if you want to test more operations
    # ops = ['GET', 'PUT', 'POST', 'DELETE']
    ops = ['GET']
    gen_words = gen_words_file(wordlist)
    gen_perms = gen_permutations(ip, gen_words, portlist, ops, on_reply, on_error, ssl=ssl)

    loop = asyncio.get_event_loop()
    k = kirb(loop, gen_perms, connections)
    loop.run_until_complete(k.run())


    async def reply_dcheck_handler(request, reply):
        t = await reply.read()
        x = reply.headers
        code = reply.status
        if code == 404:
            request.url = request.url[:-1]
            print_request(request, reply, len(t), 401)


    # dirb 401 verification check works by re-issuing the same request with the url suffixed with a '_' character
    # if the resulting response has a 404 error code, the 401 destination is considered valid
    # this check is implemented in the following generator (working on an array of 401 generating requests)
    def gen_dcheck_requests():
        for r in dcheck:
            r.url += '_'
            r.handler = reply_dcheck_handler
            yield r


    k.set_request_generator(gen_dcheck_requests())
    loop.run_until_complete(k.run())

    k.stop() # terminates the aiohttp session, otherwise it'll complain


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='''
 _  ___      _
| |/ (_)_ __| |__
| ' /| | '__| '_ \ 
| . \| | |  | |_) |
|_|\_\_|_|  |_.__/ v0.0 AxiomAdder (Alpha-Preview)''',
    formatter_class=RawTextHelpFormatter)

    parser.add_argument('ip', type=str, nargs='?')
    parser.add_argument('wordlist', type=str, nargs='?')
    parser.add_argument('ports', type=str, nargs='?')
    parser.add_argument('-s', '--ssl', action='store_true', help='Negotiate SSL')
    parser.add_argument('-m', '--max', type=int, help='Max connections')
    parser.add_argument('-t', '--timeout', type=int, help='Timeout in seconds')

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

    dirb_rest_scan(ip, wordlist, ports, ssl=args.ssl)
