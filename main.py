import codecs
import json
import os
import sys
from getpass import getpass

import requests
from instagram_private_api import (Client, ClientCookieExpiredError,
                                   ClientError, ClientLoginError,
                                   ClientLoginRequiredError)


def mkdirs(path):
    try:
        os.makedirs(path)
    except:
        pass


if len(sys.argv) < 2:
    print("username required", file=sys.stderr)
    exit(1)

user_name = sys.argv[1]
password = getpass(f"{user_name}'s password: ")

mkdirs('cookies')

saved_dir = os.path.join('saved', user_name, 'posts')
saved_json = os.path.join('saved', user_name, 'json')
settings_file = os.path.join('cookies', f"{user_name}_settings.json")
from_cache = '--from-cache' in sys.argv
no_cache = '--no-cache' in sys.argv


def from_json(json_object):
    if '__class__' in json_object and json_object['__class__'] == 'bytes':
        return codecs.decode(json_object['__value__'].encode(), 'base64')
    return json_object


def to_json(python_object):
    if isinstance(python_object, bytes):
        return {'__class__': 'bytes',
                '__value__': codecs.encode(python_object, 'base64').decode()}
    raise TypeError(repr(python_object) + ' is not JSON serializable')


def onlogin_callback(api, new_settings_file):
    cache_settings = api.settings
    with open(new_settings_file, 'w') as outfile:
        json.dump(cache_settings, outfile, default=to_json)
        print('SAVED: {0!s}'.format(new_settings_file))


try:
    if not os.path.isfile(settings_file):
        print('Unable to find file: {0!s}'.format(settings_file))
        api = Client(user_name, password,
                     on_login=lambda x: onlogin_callback(x, settings_file))
    else:
        with open(settings_file) as file_data:
            cached_settings = json.load(file_data, object_hook=from_json)
        print('Reusing settings: {0!s}'.format(settings_file))
        device_id = cached_settings.get('device_id')
        api = Client(user_name, password, settings=cached_settings)
except (ClientCookieExpiredError, ClientLoginRequiredError) as e:
    print(
        'ClientCookieExpiredError/ClientLoginRequiredError: {0!s}'.format(e), file=sys.stderr)
    api = Client(user_name, password, device_id=device_id,
                 on_login=lambda x: onlogin_callback(x, settings_file))
except ClientLoginError as e:
    print('ClientLoginError {0!s}'.format(e), file=sys.stderr)
    exit(9)
except ClientError as e:
    print('ClientError {0!s} (Code: {1:d}, Response: {2!s})'.format(
        e.msg, e.code, e.error_response), file=sys.stderr)
    exit(9)
except Exception as e:
    print('Unexpected Exception: {0!s}'.format(e), file=sys.stderr)
    exit(99)

STATUS_NEW = 'new'
STATUS_CACHE = 'cache'
STATUS_FAILED = 'failed'


def save_image_version(base_dir, media_id, image_versions):
    if not image_versions:
        return
    filename = f"{media_id}.jpg"
    path = os.path.join(base_dir, filename)
    if os.path.exists(path):
        print(f"    skip '{path}'")
        return STATUS_CACHE
    candidates = image_versions.get('candidates', [])
    if len(candidates) > 0:
        candidate = candidates[0]
        try:
            candidate_data = requests.get(candidate['url'])
            with open(path, "wb") as f:
                f.write(candidate_data.content)
                print(f"    saved '{path}'")
            return STATUS_NEW
        except Exception as e:
            print(f"    failed media_id={media_id}: {e}", file=sys.stderr)
            return STATUS_FAILED


def save_video_version(base_dir, media_id, video_versions):
    if len(video_versions) > 0:
        version = video_versions[0]
        filename = f"{media_id}.mp4"
        path = os.path.join(base_dir, filename)
        if os.path.exists(path):
            print(f"    skip '{path}'")
            return STATUS_CACHE
        try:
            version_data = requests.get(version['url'])
            with open(path, "wb") as f:
                f.write(version_data.content)
                print(f"    saved '{path}'")
            return STATUS_NEW
        except Exception as e:
            print(f"    failed media_id={media_id}: {e}")
            return STATUS_FAILED


def update_stats(stats, status):
    c = stats.setdefault(status, 0)
    stats[status] = c + 1


def save_saved(saved, stats):
    items = saved.get('items', [])
    for index, item in enumerate(items):
        media = item['media']
        media_id = media['id']
        user = media['user']['username']
        iid = f"{user}/{media_id}"
        print(f"entering {iid} ({index + 1}/{len(items)})...")
        base_dir = os.path.join(saved_dir, user, media_id)
        mkdirs(base_dir)

        caption = media.get('caption', None)
        if caption:
            text = caption.get('text', None)
            if text:
                with open(os.path.join(base_dir, 'caption.txt'), 'wb') as f:
                    f.write(text.encode('utf8'))

        video_versions = media.get('video_versions', [])
        status = save_video_version(base_dir, media_id, video_versions)
        update_stats(stats, status)

        image_versions = media.get('image_versions2', None)
        status = save_image_version(base_dir, media_id, image_versions)
        update_stats(stats, status)

        carousel_medias = media.get('carousel_media', [])
        for index, carousel_media in enumerate(carousel_medias):
            car_image_versions = carousel_media.get('image_versions2', None)
            car_media_id = f"{index + 1}_{carousel_media['id']}"
            status = save_image_version(
                base_dir, car_media_id, car_image_versions)
            update_stats(stats, status)
            car_video_versions = carousel_media.get('video_versions', [])
            status = save_video_version(
                base_dir, car_media_id, car_video_versions)
            update_stats(stats, status)

        print(f"exiting {iid}")
    return len(items)


def saved_from_api():
    mkdirs(saved_json)
    posts = []
    count = 0

    page_size = 250
    next_max_id = None
    saved_json_count = 0
    while True:
        if next_max_id:
            saved = api.saved_feed(count=page_size, max_id=next_max_id)
        else:
            saved = api.saved_feed(count=page_size)
        if not no_cache:
            json_path = os.path.join(
                saved_json, f"page_{saved_json_count}.json")
            with open(json_path, 'w') as f:
                f.write(json.dumps(saved, indent=2))
        saved_json_count = saved_json_count + 1
        count = count + saved.get('num_results', 0)
        posts.append(saved)
        next_max_id = saved.get('next_max_id', None)
        if not next_max_id:
            break
    return (posts, count)


def saved_from_cache():
    posts = []
    count = 0

    json_files = os.listdir(saved_json)
    for json_file in json_files:
        with open(os.path.join(saved_json, json_file)) as f:
            saved = json.loads(f.read())
            count = count + saved.get('num_results', 0)
            posts.append(saved)

    return (posts, count)


if from_cache:
    (saved_posts, saved_posts_count) = saved_from_cache()
else:
    (saved_posts, saved_posts_count) = saved_from_api()

print(f"total posts: {saved_posts_count}")

processed = 0
stats = {}
for saved in saved_posts:
    processed = processed + save_saved(saved, stats)
    print(f"processed {processed}/{saved_posts_count} posts")

print(f"\ntotal posts: {saved_posts_count}")
print(f"new files: {stats.get(STATUS_NEW, 0)}")
print(f"cached files: {stats.get(STATUS_CACHE, 0)}")
print(f"failed files: {stats.get(STATUS_FAILED, 0)}")
