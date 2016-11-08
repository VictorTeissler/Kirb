import sys
import asyncio
import aiohttp
import functools
import async_timeout

class request(object):
    def __init__(self, url, operation, handler, ssl = False, data = []):
        self.url = url
        self.ssl = ssl
        self.data = data
        self.tries = 0 # For future retry functionality
        self.handler = handler
        self.operation = operation
    pass

class kirb(object):

    OPS = ['GET', 'PUT', 'POST', 'DELETE']
    def __init__(self, loop, generator, xhandler, max_con = 500, timeout = 50):
        self.loop      = loop
        self.timeout   = timeout
        self.xhandler  = xhandler
        self.gen_requests  = generator
        self.session   = aiohttp.ClientSession(loop=loop)
        self.semaphore = asyncio.Semaphore(max_con, loop=loop)
        self.opcalls   = { 'GET'    : self.session.get,
                           'PUT'    : self.session.put,
                           'POST'   : self.session.post,
                           'DELETE' : self.session.delete }

    def set_request_generator(self, gen):
        self.gen_requests = gen

    # TODO: Catch timeouts and other net-related errors, throw the requests into a retry bucket for later
    # Opcalls dictionary seemed like a good idea at first.. TODO: changeme?
    async def timed_op(self, request):
        with async_timeout.timeout(self.timeout, loop=self.session.loop):
            try:
                request.tries += 1

                if request.ssl == False:
                    url = 'http://' + request.url
                elif request.ssl == True:
                    url = 'https://' + request.url

                if len(request.data) > 0: # conditionally supply post data
                    reply = await self.opcalls[request.operation](url, data=request.data)
                else:
                    reply = await self.opcalls[request.operation](url)

                await self.handler(request, reply)
                await reply.text() # TODO: don't wait for data?

                self.semaphore.release()

            except(aiohttp.errors.ClientOSError):
                print("ClientOSError:")
            #except:
            #    print('uncaught error')

    async def handler(self, request, reply):
        # TODO: track performance metrics
        await request.handler(request, reply)

    async def run(self):

        futures = []
        for r in self.gen_requests:
            futures = [f for f in futures if f.done() == False] # remove completed futures

            await self.semaphore.acquire() # ensure we have more then max_con connections
            futures.append(asyncio.ensure_future(self.timed_op(r)))

        await asyncio.gather(*futures)

    def stop(self):
        self.session.close()

# example code 
def dirb_rest_scan(ip, wordlist, portlist):
    # catches 401 code generating requests, this is for dirb checks explained later on
    dcheck = []

    def gen_words_file(word_filepath):
        with open(word_filepath, 'r') as words:
            for l in words.readlines():
                yield l[:-1]

    def gen_words_file_multi(word_filepaths):
        for wp in word_filepaths:
            for w in generate_words_file(wp):
                yield w

    def gen_requests(ip, words, ports, ops, handler, ssl=False):
        for p in ports:
            for w in words:
                for op in ops:
                    if w[0] == '/':
                        w = w[1:]
                    url = ip + ':' + p + '/' + w
                    yield request(url, op, handler, ssl)

    def print_request(request, reply, reply_len, code = 0): # allow for code override
        t = reply.text()
        if code == 0:
            code = reply.status
        print("+ " + request.url + ' (CODE:' + str(code) + '|' + request.operation + '|SIZE:' + str(reply_len) + ')')

    async def reply_handler(request, reply):
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
            print('403 - look for net errors')
            print_request(request, reply, len(t))
            return

    ops = ['GET', 'PUT', 'POST', 'DELETE']
    gen = gen_words_file(wordlist)
    g = gen_requests(ip, gen, portlist, ops, reply_handler, ssl=False)

    loop = asyncio.get_event_loop()
    k = kirb(loop, g, reply_handler)
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

# This code demos some of kirb's data spewing/reading capability by reimplementing dirb, only faster
if __name__ == "__main__":
    if len(sys.argv) != 4:
        print('usage: scan.py <ip> <wordlist> <port1,port2,etc>')
        exit(1)
    ports = sys.argv[3].split(',')
    wordlist = sys.argv[2]
    ip = sys.argv[1]
    dirb_rest_scan(ip, wordlist, ports)

