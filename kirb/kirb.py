import asyncio
import aiohttp
import async_timeout

# This is the heart of Kirb.
# Its an event loop that spews request up to a set limit, regulated by a semaphore.



# TODO: Support changing user agents
# TODO: Add basic auth
# TODO: !!! Handle retries
class Request(object):
    def __init__(self, url, operation, on_reply, on_error = False, ssl = False, data = [], timeout=5):
        self.url       = url
        self.ssl       = ssl
        self.data      = data
        self.tries     = 0 # For future retry functionality
        self.operation = operation
        self.on_reply  = on_reply
        self.on_error  = on_error
        self.timeout   = timeout

class Kirb(object):
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

        except aiohttp.ClientOSError as e:
            await self._on_error(request, e)

        except asyncio.TimeoutError as e:
            await self._on_error(request, e)

        self.semaphore.release()


    async def _on_reply(self, request, reply):
        await request.on_reply(request, reply)


    async def _on_error(self, request, error):
        if request.on_error != None:
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
