import time
import requests
from optparse import OptionParser


global_total_ms = 0
global_request_num = 0


def timing(method):
    def wrapper(*args, **kw):
        startTime = int(round(time.time() * 1000))
        result = method(*args, **kw)
        endTime = int(round(time.time() * 1000))
        delta = endTime - startTime
        global global_total_ms
        global global_request_num
        global_total_ms += delta
        global_request_num += 1
        print "%sms" % (delta)
        return result
    return wrapper


@timing
def post_request(s, url, vote_num):
    return s.post(url, data={'vote_num': str(vote_num)})


def main():
    usage = "usage: %prog [options] arg"
    parser = OptionParser(usage)
    parser.add_option("-r", "--requests", dest="requests_per", default=1)
    parser.add_option("-d", "--domain", dest="domain", default="www.adventure-prov.com")
    parser.add_option("-l", "--length", dest="vote_length", default=25)
    parser.add_option("-o", "--options", dest="num_options", default=3)
    (options, args) = parser.parse_args()
    if len(args) < 1:
        uri = "/live_vote/"
    elif len(args) == 1:
        uri = args[0]
    requests_per = int(options.requests_per)
    domain = options.domain
    vote_length = int(options.vote_length)
    url = "http://%s%s" % (domain, uri)
    print "Sending requests to ", url
    total_count = 0
    vote_num = 0
    vote_dict = {}
    # Vote the number of seconds the vote lasts for
    for s in range(vote_length):
        for i in range(requests_per):
            # Create a new session
            s = requests.Session()
            # POST
            reponse = post_request(s, url, vote_num)
            # Keep track of the vote numbers
            vote_dict[vote_num] = vote_dict.get(vote_num, 0) + 1
            total_count += 1
        # Increment the vote number, unless it's 3
        if vote_num == int(options.num_options) - 1:
            vote_num = 0
        else:
            vote_num += 1
    for j,value in vote_dict.items():
        print "Option %s votes: %s" % (j, value)
    print "Total count: ", total_count
    print "Average request time: %sms" % (global_total_ms/global_request_num)

if __name__ == "__main__":
    main()
