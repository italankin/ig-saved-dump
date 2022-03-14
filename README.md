# Usage

1. Clone this repository
2. (Optional) Create Python virtual environment
3. Install [required packages](./requirements.txt)

```sh
$ pip install -r requirements.txt
```

4. Disable 2FA on your Instagram account
5. Run

```sh
$ python main.py your_username
```

You will be asked for your password. If you have a valid cookie (`cookies/your_username_settings.json`), you can leave the password blank.

6. Wait for data to download

# Structure

```
|-- cookies
+-- saved
    +-- username
        |-- posts
        |   |-- author_username_1
        |   |   |-- post_1_id
        |   |   |   |-- post data, such as photos, videos, captions
        |   |   |-- post_2_id
        |   |   |-- ...
        |   |-- author_username_2
        |   |   |-- post_1_id
        |   |-- ...
        +-- json
            |-- page_0.json
            |-- page_1.json
            |-- ...
```

Cookies are saved in `cookies` directory under user's name, e.g. `cookies/username_settings.json`. They are used for future runs to avoid account block.

All saved data is stored in `saved`, e.g. `saved/username`:

* `posts` - contains actual saved posts data, grouped by author
* `json` - contains raw JSON responses from Instagram API. You can force script to use this data by passing `--from-cache` argument (to avoid calling the API, useful for subsequent runs)
