# Bible lib

## Features

The bible lib can be used query bible texts in a variety of languages.

* Get a list of supported bibles using scripture.api.bible
* Caching of bible.api responses to reduce web traffic
* Get a single or multiple bible verses given a book, chapter and verse.

## Usage

Before being able to connect to the scripture.api.bible API, 
you need to register and request an API key.
Once you have the API key you can set it in the variable `API_KEY`. 
This variable is found in the `settings.py` file.

``` python
from bible_lib import BIBLE_API_KEY

BIBLE_API_KEY = 'abcdefghijklmnopqrstuvwxyz'
```

Once configured, you can use it like this:

``` python
from bible_lib import BibleFactory
from bible_lib import BibleBooks

# For a list of supported bibles using the scripture.api.bible
supported_bibles = Bibles().list()

bible = BibleFactory().create(supported_bibles[0].id)
# or 
bible = BibleFactory().create('ead7b4cc5007389c-01')

text = bible.verse(BibleBooks.John, 3, 16)
```