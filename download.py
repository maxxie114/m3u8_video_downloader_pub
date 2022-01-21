# A python script to find and download a video in m3u8 format from some websites

import logging
import os.path
import m3u8, requests
import os, subprocess
import re
from urllib.parse import urlparse

# Variables
headers = {"User-Agent": "Mozilla"}
new_url = ""

# Debug mode
debug = True

# Functions


def find(string, regex):
    """Find all m3u8 urls from a string using a given regex"""
    url = re.findall(regex, string)
    return url


def get_filename_from_url(url):
    """Get the filename from a url"""
    m3u8_url_data = urlparse(url)
    m3u8_url_path = m3u8_url_data.path.split("/")
    return m3u8_url_path[-1]


def search_video_url(video_name):
    """Search for the actual video url from website database, 
       if no result, return False
    """
    search_url = f"https://url_redacted"
    r = requests.get(search_url, headers=headers)
    regex = f"(https:\/\/.+{video_name.lower()}[-9a-zA-Z!@#$%^&*()_+-=]+\/)"

    # Decode the byte string
    data = r.content.decode("utf-8")
    video_url = find(data, regex)[0]

    if len(video_url) == 0:
        logger.error(
            f"Couldn't find anything related to {video_name} on {search_url}."
        )
        return False

    logger.debug(f"search result for the video url: {video_url}")
    return video_url


def get_m3u8_url(video_name):
    """Get the m3u8 url of a video, return False if nothing is found"""
    url = f"https://url_redacted"
    r = requests.get(url, headers=headers)

    if r.status_code == 404:
        logger.error(
            f"Error occured, request to {url} return 404 status code, attempting a search."
        )
        url = search_video_url(video_name)
        if url == False:
            logger.error("Couldn't find anything in the search, returning.")
            return False
        r = requests.get(url, headers=headers)
    # Decode the byte string
    data = r.content.decode("utf-8")
    m3u8_link = find(data, "(https:\/\/.+m3u8)")[0]

    if len(m3u8_link) == 0:
        logger.error(
            f"Error occurred, m3u8 link could not be found at {url}")
        return False

    logger.debug(f"search result: {m3u8_link}")

    return m3u8_link


def download_from_url(url, headers, path):
    """Download a file with a given url, and write to a path
       Return the status code, if the download does not success,
       it will not be written to the path 
    """
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        open(path, "wb").write(r.content)
    return r.status_code


def get_key(playlist):
    """Return the key of the m3u8 playlist
       Return False if no key exists
    
       playlist - m3u8 object
    """
    # Determine if key exists
    if playlist.data["keys"][0] == None:
        logger.debug(f"has key: False")
        return False
    key = playlist.data['keys'][0]['uri']
    logger.debug(f"key file: {key}")
    return key


def get_ts_list(playlist):
    """Return a list of ts files from an m3u8 playlist
       playlist - m3u8 playlist
    """
    ts_list = []
    for i in range(len(playlist.data['segments'])):
        ts_list.append(playlist.data['segments'][i]['uri'])
    return ts_list


def strip_url(url):
    """Strip the filename at the end of a url out of the url"""
    # break down the m3u8 url to prepare for file download
    m3u8_url_data = urlparse(url)
    m3u8_url_path = m3u8_url_data.path.split("/")
    new_url = f"https://{m3u8_url_data.netloc}{'/'.join(m3u8_url_path[:-1])}/"
    logger.debug(f"new url: {new_url}")
    return new_url


def download_ts_file(headers, path, video_name, ts_filename):
    """Download a ts file from a provided url, if download failed
       it will call get_m3u8_url() to get a new url
       headers - header for get request
       path - path to store data
       video_name - the name of the video
       ts_filename - the filename of the ts file
    """
    # If 410 error, get a new link and try again
    download_succeed = False
    global new_url
    while not download_succeed:
        r = requests.get(new_url + ts_filename, headers=headers)
        logger.info(
            f"{ts_filename}: {'200 OK' if r.status_code == 200 else r.status_code}"
        )
        if r.status_code == 200:
            download_succeed = True
            open(path, 'wb').write(r.content)
        else:
            logger.error(
                f"Download failed, getting another url, error code: {r.status_code}"
            )
            m3u8_link = get_m3u8_url(video_name)
            new_url = strip_url(m3u8_link)


def generate_mp4(video_name, m3u8_filename):
    """Package all ts files into an mp4 file, and write out the ffmpeg log"""
    # Remove MP4 file if it already exists
    mp4_file = f"{video_name}.mp4"
    if os.path.exists(mp4_file):
        logger.info(f"{mp4_file} already exists, removing file.")
        subprocess.run(["rm", "-r", mp4_file])

    out = subprocess.getoutput(
        f'ffmpeg -i {video_name}/{m3u8_filename} -c:v copy {mp4_file}')
    open(f"ffmpeg_{video_name}.log", "w").write(out)


def download_video(video_name):
    """Download a video from website with a given video name"""
    global headers, new_url

    logger.info(f"Begin downloading {video_name}.")

    # Create directory
    if os.path.exists(video_name):
        logger.info(f"{video_name} already exists, removing directory.")
        subprocess.run(["rm", "-r", video_name])
    logger.info(f"Creating directory {video_name}")
    os.mkdir(video_name)

    # Find the url of the m3u8 file
    m3u8_link = get_m3u8_url(video_name)

    if m3u8_link == False:
        logger.error(
            "Error occurred, couldn't retrieve m3u8 link, skipping this video."
        )
        logger.info(f"Removing directory {video_name}.")
        subprocess.run(["rm", "-r", video_name])
        return False

    # Download the m3u8
    m3u8_filename = get_filename_from_url(m3u8_link)
    m3u8_path = f"{video_name}/{m3u8_filename}"
    status_code = download_from_url(m3u8_link, headers, m3u8_path)
    logger.debug(
        f"{m3u8_filename}: {'200 OK' if status_code == 200 else status_code}")

    # Get data from the m3u8
    playlist = m3u8.load(m3u8_path)
    temp = get_key(playlist)
    key = "" if temp == False else temp
    has_key = False if temp == False else True
    ts_list = get_ts_list(playlist)

    logger.debug(f"ts list length: {len(ts_list)}")
    logger.debug(f"first: {ts_list[0]}")
    logger.debug(f"last: {ts_list[-1]}")
    total_file_count = len(ts_list) + 1 if has_key else len(ts_list)

    # Download all the ts files one by one
    # If key exist, first download the key file
    counter, total_downloaded = 0, 0
    current_ts_file = key if has_key else ts_list[counter]
    new_url = strip_url(m3u8_link)

    logger.debug(f"total_file_count: {total_file_count}")
    while True:
        logger.debug(f"current_ts_file: {current_ts_file}")
        logger.debug(f"total_downloaded: {total_downloaded}")
        logger.debug(f"counter: {counter}")

        # Download current_ts_file
        download_ts_file(headers, f"{video_name}/{current_ts_file}",
                         video_name, current_ts_file)

        # If the file downloaded is the key file, do not increase the counter
        logger.debug(f"current ts file is key: {current_ts_file == key}")
        logger.debug(f"current ts file: {current_ts_file}")
        logger.debug(f"current key: {key}")
        if not current_ts_file == key:
            counter += 1
            logger.debug("counter increased")

        total_downloaded += 1
        if total_downloaded == total_file_count:
            logger.info(
                "All files downloaded, no more new files, exiting loop.")
            break

        # When total_downloaded == total_file_count, it will break the loop
        # before this line is executed, which avoid index out of range
        current_ts_file = ts_list[counter]

    logger.info("Packaging the TS files into MP4 file.")
    generate_mp4(video_name, m3u8_filename)
    logger.info(f"Removing directory {video_name}.")
    subprocess.run(["rm", "-r", video_name])
    return True


if __name__ == '__main__':
    # Set up logger
    log_level = logging.DEBUG
    if debug == False:
        log_level = logging.INFO
    logger = logging.getLogger()
    logging.basicConfig(filename='debug.log',
                        filemode='a',
                        format='[%(levelname)s %(asctime)s] %(message)s',
                        datefmt='%m/%d/%Y %H:%M:%S',
                        level=log_level)
    logger.addHandler(logging.StreamHandler())
    logger.info("Program Started.")

    try:
        # Read movie names from file
        names = []
        with open("names.txt", "r") as f:
            for line in f:
                names.append(line.strip())
        logger.debug(f"movie names: {names}")

        for video_name in names:
            result = download_video(video_name)
            if result == True:
                logger.info(f"{video_name} downloaded.")
            else:
                logger.error(f"{video_name} downloading failed.")
    except:
        logger.critical("Unknown exception occurred, exiting program.")
        logger.exception("Unknown exception occurred:")
