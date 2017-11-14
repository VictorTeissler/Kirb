def gen_words_file(word_filepath):
    with open(word_filepath, 'rb') as words:
        for l in words.readlines():
            l = urllib.parse.unquote(l[:-1].decode('utf8')) # FIXME: is this right? I dunno
            yield l


def gen_words_file_multi(word_filepaths):
    for wp in word_filepaths:
        for w in generate_words_file(wp):
            yield w


def gen_permutations(ip, words, ports, request_factory):
    for p in ports:
        for w in words:
            for op in ops:
                if p == '':
                    continue
                url = ip + ':' + p + '/' + w
                yield Request(url)


