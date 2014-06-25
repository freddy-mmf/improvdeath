import time
import requests
from optparse import OptionParser


def main():
    usage = "usage: %prog [options] arg"
    parser = OptionParser(usage)
    parser.add_option("-r", "--requests", dest="requests_per", default=1)
    parser.add_option("-d", "--domain", dest="domain", default="adventure-prov.com")
    parser.add_option("-l", "--length", dest="vote_length", default=25)
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
            reponse = s.post(url, data={'vote_num': str(vote_num)})
            # Keep track of the vote numbers
            vote_dict[vote_num] = vote_dict.get(vote_num, 0) + 1
            total_count += 1
        # Increment the vote number, unless it's 3
        if vote_num == 2:
            vote_num = 0
        else:
            vote_num += 1
        time.sleep(.5)
    for j,value in vote_dict.items():
        print "Option %s votes: %s" % (j, value)
    print "Total count: ", total_count

if __name__ == "__main__":
    main()
