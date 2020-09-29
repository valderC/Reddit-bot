# Packages
import praw             #Python Reddit API Wrapper
import tweepy           #Twitter package to access api
import json
import requests
import time
import os
import urllib.parse
from glob import glob

# Place your Twitter API keys here
ACCESS_TOKEN = ''
ACCESS_TOKEN_SECRET = ''
CONSUMER_KEY = ''
CONSUMER_SECRET = ''

# Place the subreddit you want to look up posts from here
SUBREDDIT_TO_MONITOR = ''

# Place the name of the folder where the images are downloaded
IMAGE_DIR = 'img'

# Place the name of the file to store the IDs of posts that have been posted
POSTED_CACHE = 'posted_posts.txt'

# Place the string you want to add at the end of your tweets (can be empty)
TWEET_SUFFIX = ' #dataviz'

# Place the maximum length for a tweet
TWEET_MAX_LEN = 140

# Place the time you want to wait between each tweets (in seconds)
DELAY_BETWEEN_TWEETS = 30

# Place the lengths of t.co links (cf https://dev.twitter.com/overview/t.co)
T_CO_LINKS_LEN = 24

def setup_connection_reddit(subreddit):
    ''' Creates a connection to the reddit API. '''
    print('[bot] Setting up connection with reddit')
    reddit_api = praw.Reddit('reddit Twitter tool monitoring {}'.format(subreddit))
    return reddit_api.get_subreddit(subreddit)


def tweet_creator(subreddit_info):
    ''' Looks up posts from reddit and shortens the URLs to them. '''
    post_dict = {}
    post_ids = []

    print('[bot] Getting posts from reddit')

    # You can use the following "get" functions to get posts from reddit:
    #   - get_top(): gets the most-upvoted posts (ignoring post age)
    #   - get_hot(): gets the most-upvoted posts (taking post age into account)
    #   - get_new(): gets the newest posts
    #
    # "limit" tells the API the maximum number of posts to look up

    for submission in subreddit_info.get_hot(limit=5):
        if not already_tweeted(submission.id):
            # This stores a link to the reddit post itself
            # If you want to link to what the post is linking to instead, use
            # "submission.url" instead of "submission.permalink"
            post_dict[submission.title] = {}
            post = post_dict[submission.title]
            post['link'] = submission.permalink

            # Store the url the post points to (if any)
            # If it's an imgur URL, it will later be downloaded and uploaded alongside the tweet
            post['img_path'] = get_image(submission.url)

            post_ids.append(submission.id)
        else:
            print('[bot] Already tweeted: {}'.format(str(submission)))

    return post_dict, post_ids


def already_tweeted(post_id):
    ''' Checks if the reddit Twitter bot has already tweeted a post. '''
    found = False
    with open(POSTED_CACHE, 'r') as in_file:
        for line in in_file:
            if post_id in line:
                found = True
                break
    return found


def strip_title(title, num_characters):
    ''' Shortens the title of the post to the 140 character limit. '''

    # How much you strip from the title depends on how much extra text
    # (URLs, hashtags, etc.) that you add to the tweet
    # Note: it is annoying but some short urls like "data.gov" will be
    # replaced by longer URLs by twitter. Long term solution could be to
    # use urllib.parse to detect those.
    if len(title) <= num_characters:
        return title
    else:
        return title[:num_characters - 1] + '…'


def get_image(img_url):
    ''' Downloads i.imgur.com images that reddit posts may point to. '''
    if 'imgur.com' in img_url:
        file_name = os.path.basename(urllib.parse.urlsplit(img_url).path)
        img_path = IMAGE_DIR + '/' + file_name
        print('[bot] Downloading image at URL ' + img_url + ' to ' + img_path)
        resp = requests.get(img_url, stream=True)
        if resp.status_code == 200:
            with open(img_path, 'wb') as image_file:
                for chunk in resp:
                    image_file.write(chunk)
            # Return the path of the image, which is always the same since we just overwrite images
            return img_path
        else:
            print('[bot] Image failed to download. Status code: ' + resp.status_code)
    else:
        print('[bot] Post doesn\'t point to an i.imgur.com link')
    return ''


def tweeter(post_dict, post_ids):
    ''' Tweets all of the selected reddit posts. '''
    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)

    for post, post_id in zip(post_dict, post_ids):
        img_path = post_dict[post]['img_path']

        extra_text = ' ' + post_dict[post]['link'] + TWEET_SUFFIX
        extra_text_len = 1 + T_CO_LINKS_LEN + len(TWEET_SUFFIX)
        if img_path:  # Image counts as a link
            extra_text_len += T_CO_LINKS_LEN
        post_text = strip_title(post, TWEET_MAX_LEN - extra_text_len) + extra_text
        print('[bot] Posting this link on Twitter')
        print(post_text)
        if img_path:
            print('[bot] With image ' + img_path)
            api.update_with_media(filename=img_path, status=post_text)
        else:
            api.update_status(status=post_text)
        log_tweet(post_id)
        time.sleep(DELAY_BETWEEN_TWEETS)


def log_tweet(post_id):
    ''' Takes note of when the reddit Twitter bot tweeted a post. '''
    with open(POSTED_CACHE, 'a') as out_file:
        out_file.write(str(post_id) + '\n')

# driver
def main():
    ''' Runs through the bot posting routine once. '''
    # If the tweet tracking file does not already exist, create it
    if not os.path.exists(POSTED_CACHE):
        with open(POSTED_CACHE, 'w'):
            pass
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)

    subreddit = setup_connection_reddit(SUBREDDIT_TO_MONITOR)
    post_dict, post_ids = tweet_creator(subreddit)
    tweeter(post_dict, post_ids)

    # Clean out the image cache
    for filename in glob(IMAGE_DIR + '/*'):
        os.remove(filename)

if __name__ == '__main__':
    main()
